"""Build a pthread scheduling plan from classified nodes."""

from eda_platform.agents.firmware_engineer.classifier import classify_nodes
from eda_platform.agents.firmware_engineer.models import (
    BusLock,
    ExecutionTier,
    NodeClassification,
    SchedulingPlan,
    TaskSpec,
)
from eda_platform.schemas import ComponentManifest, ComponentType, PinType, ProjectState

I2C_DEVICE_PATH = "/dev/i2c-1"

_I2C_PIN_TYPES = {PinType.I2C_SDA, PinType.I2C_SCL}


def _i2c_peripheral_nodes(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> list[str]:
    """Return peripheral node_ids wired to an I2C SDA/SCL pin on some net.

    Detection is driven by ``Pin.pin_type`` from the manifest — never by
    pin_id naming convention — so it generalizes to any MCU or sensor
    regardless of how its datasheet-derived pins happen to be named.
    """
    node_by_id = {n.node_id: n for n in project.nodes}
    i2c_node_ids: set[str] = set()

    for net in project.nets:
        for conn in net.connections:
            node = node_by_id.get(conn.node_id)
            if node is None:
                continue
            manifest = manifests.get(node.component_id)
            if manifest is None:
                continue
            pin = next((p for p in manifest.pins if p.pin_id == conn.pin_id), None)
            if pin is not None and pin.pin_type in _I2C_PIN_TYPES:
                i2c_node_ids.add(conn.node_id)

    # MCU is the bus host, not a schedulable bus member.
    peripherals = [
        nid
        for nid in i2c_node_ids
        if manifests.get(node_by_id[nid].component_id) is not None
        and manifests[node_by_id[nid].component_id].type != ComponentType.MCU
    ]
    return sorted(peripherals)


def build_scheduling_plan(
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    classifications: list[NodeClassification],
) -> SchedulingPlan:
    """Allocate pthread tasks and bus mutexes per CONCURRENCY_STRATEGY.md."""
    i2c_peripherals = _i2c_peripheral_nodes(project, manifests)
    bus_locks: list[BusLock] = []
    tasks: list[TaskSpec] = []

    if i2c_peripherals:
        bus_locks.append(
            BusLock(bus_id="i2c_bus_0", i2c_device_path=I2C_DEVICE_PATH, nodes=i2c_peripherals)
        )

        # T0 nodes get their own dedicated control task below even if they
        # also share this bus; everything else polls together on one task.
        poll_nodes = [
            c.node_id
            for c in classifications
            if c.node_id in i2c_peripherals and c.tier != ExecutionTier.T0
        ]
        if poll_nodes:
            hal_modules = ["hal_i2c_bus_0"] + [
                c.hal_module for c in classifications if c.node_id in poll_nodes
            ]
            tasks.append(
                TaskSpec(
                    task_id="task_sensor_poll",
                    tier=ExecutionTier.T1,
                    priority=5,
                    period_ms=20,
                    nodes=poll_nodes,
                    hal_modules=hal_modules,
                )
            )

    t0_nodes = [c for c in classifications if c.tier == ExecutionTier.T0]
    for c in t0_nodes:
        # A T0 node that also shares the I2C bus (e.g. a motor driver with
        # an I2C config interface) still needs the bus mutex in its task.
        hal_modules = [c.hal_module]
        if c.node_id in i2c_peripherals:
            hal_modules.insert(0, "hal_i2c_bus_0")
        tasks.append(
            TaskSpec(
                task_id=f"task_{c.node_id}_control",
                tier=ExecutionTier.T0,
                priority=10,
                period_ms=1,
                nodes=[c.node_id],
                hal_modules=hal_modules,
            )
        )

    t3_nodes = [c.node_id for c in classifications if c.tier == ExecutionTier.T3]
    if t3_nodes:
        tasks.append(
            TaskSpec(
                task_id="task_background",
                tier=ExecutionTier.T3,
                priority=1,
                period_ms=1000,
                nodes=t3_nodes,
                hal_modules=[c.hal_module for c in classifications if c.node_id in t3_nodes],
            )
        )

    if not tasks:
        raise ValueError("scheduling plan has no tasks — check node classifications")

    return SchedulingPlan(
        project_id=project.project_id,
        platform="rpi4",
        tasks=tasks,
        bus_locks=bus_locks,
        classifications=classifications,
    )


def plan_from_project(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> SchedulingPlan:
    classifications = classify_nodes(project, manifests)
    return build_scheduling_plan(project, manifests, classifications)
