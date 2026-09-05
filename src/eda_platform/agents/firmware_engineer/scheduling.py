"""Build a pthread scheduling plan from classified nodes."""

from eda_platform.agents.firmware_engineer.classifier import classify_nodes
from eda_platform.agents.firmware_engineer.models import (
    BusLock,
    ExecutionTier,
    NodeClassification,
    SchedulingPlan,
    TaskSpec,
)
from eda_platform.schemas import ComponentManifest, ProjectState

I2C_DEVICE_PATH = "/dev/i2c-1"


def _i2c_nodes_on_bus(project: ProjectState) -> dict[str, list[str]]:
    """Group node_ids that share an I2C SDA or SCL net."""
    bus_members: dict[str, set[str]] = {}

    for net in project.nets:
        has_i2c = False
        nodes_on_net: set[str] = set()
        for conn in net.connections:
            nodes_on_net.add(conn.node_id)
        for conn in net.connections:
            # Detect I2C by pin naming convention on the net
            if conn.pin_id in ("I2C_SDA", "I2C_SCL", "GPIO4", "GPIO5"):
                has_i2c = True
                break
        if has_i2c:
            bus_key = f"i2c_bus_{len(bus_members)}"
            bus_members.setdefault(bus_key, set()).update(nodes_on_net)

    if not bus_members:
        return {"i2c_bus_0": []}

    # Merge all I2C nets into bus 0 for v1 (single Pi I2C controller)
    all_nodes: set[str] = set()
    for members in bus_members.values():
        all_nodes.update(members)

    # Exclude MCU host nodes
    mcu_ids = {n.node_id for n in project.nodes if n.component_id.startswith("mcu_")}
    peripherals = sorted(nid for nid in all_nodes if nid not in mcu_ids)
    return {"i2c_bus_0": peripherals}


def build_scheduling_plan(
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    classifications: list[NodeClassification],
) -> SchedulingPlan:
    """Allocate pthread tasks and bus mutexes per CONCURRENCY_STRATEGY.md."""
    i2c_groups = _i2c_nodes_on_bus(project)
    bus_locks: list[BusLock] = []
    tasks: list[TaskSpec] = []

    for bus_id, node_ids in i2c_groups.items():
        if not node_ids:
            continue
        bus_locks.append(
            BusLock(bus_id=bus_id, i2c_device_path=I2C_DEVICE_PATH, nodes=node_ids)
        )

        t1_nodes = [
            c.node_id
            for c in classifications
            if c.node_id in node_ids and c.tier in (ExecutionTier.T1, ExecutionTier.T2)
        ]
        if t1_nodes:
            hal_modules = ["hal_i2c_bus_0"] + [
                c.hal_module for c in classifications if c.node_id in t1_nodes
            ]
            tasks.append(
                TaskSpec(
                    task_id="task_sensor_poll",
                    tier=ExecutionTier.T1,
                    priority=5,
                    period_ms=20,
                    nodes=t1_nodes,
                    hal_modules=hal_modules,
                )
            )

    t0_nodes = [c for c in classifications if c.tier == ExecutionTier.T0]
    for c in t0_nodes:
        tasks.append(
            TaskSpec(
                task_id=f"task_{c.node_id}_control",
                tier=ExecutionTier.T0,
                priority=10,
                period_ms=1,
                nodes=[c.node_id],
                hal_modules=[c.hal_module],
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
