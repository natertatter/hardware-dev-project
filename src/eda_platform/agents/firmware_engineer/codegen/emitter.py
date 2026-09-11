"""Emit all firmware source files for a scheduling plan."""

from pathlib import Path

from eda_platform.agents.firmware_engineer.codegen import templates
from eda_platform.agents.firmware_engineer.models import SchedulingPlan
from eda_platform.agents.operations_refiner.best_practices import is_boot_step
from eda_platform.schemas import ComponentManifest, ComponentType, OperationsSequence, PinType, ProjectState


def _node_address(node_id: str, project: ProjectState, manifest: ComponentManifest) -> int:
    node = next(n for n in project.nodes if n.node_id == node_id)
    addr = node.assigned_i2c_address or manifest.default_i2c_address or "0x40"
    return int(addr, 16)


def _sensor_nodes(
    plan: SchedulingPlan, project: ProjectState, manifests: dict[str, ComponentManifest]
) -> list[dict]:
    sensors = []
    for c in plan.classifications:
        manifest = manifests.get(c.component_id)
        if manifest is None:
            continue
        if manifest.type != ComponentType.SENSOR:
            continue
        sensors.append(
            {
                "node_id": c.node_id,
                "component_id": c.component_id,
                "hal_module": c.hal_module,
                "i2c_address": _node_address(c.node_id, project, manifest),
            }
        )
    return sensors


def _mcu_i2c_pins(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> tuple[str | None, str | None]:
    """Find the MCU's logical SDA/SCL pin_ids actually wired in this schematic."""
    sda_pin_id: str | None = None
    scl_pin_id: str | None = None

    for node in project.nodes:
        manifest = manifests.get(node.component_id)
        if manifest is None or manifest.type != ComponentType.MCU:
            continue

        wired_pin_ids = {
            conn.pin_id
            for net in project.nets
            for conn in net.connections
            if conn.node_id == node.node_id
        }
        for pin in manifest.pins:
            if pin.pin_id not in wired_pin_ids:
                continue
            if pin.pin_type == PinType.I2C_SDA:
                sda_pin_id = pin.pin_id
            elif pin.pin_type == PinType.I2C_SCL:
                scl_pin_id = pin.pin_id

    return sda_pin_id, scl_pin_id


def _boot_delays_from_operations(
    operations: OperationsSequence | None,
) -> list[tuple[int, str]]:
    """One-shot delays to run sequentially in main() before threads spawn.

    Only genuine boot/init steps qualify. A step with a one-shot delay that
    is NOT part of boot (e.g. "pause before reversing motor direction",
    an estop-release safety delay) describes a *runtime* pause that recurs
    during normal operation — baking it into main()'s one-time startup
    sequence would execute it once at boot and never again, silently
    producing firmware that does not match the operations sequence.
    """
    if operations is None:
        return []
    delays: list[tuple[int, str]] = []
    for step in operations.steps:
        if not (step.timing and step.timing.delay_ms):
            continue
        if not is_boot_step(step.description):
            continue
        delays.append((step.timing.delay_ms, step.description))
    return delays


def generate_source_files(
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    plan: SchedulingPlan,
    operations: OperationsSequence | None = None,
) -> dict[str, str]:
    """Return relative path → file contents for the full firmware tree."""
    sensors = _sensor_nodes(plan, project, manifests)
    sda_pin_id, scl_pin_id = _mcu_i2c_pins(project, manifests)
    files: dict[str, str] = {}

    files["platform/board_config.h"] = templates.board_config_h(plan, sda_pin_id, scl_pin_id)
    files["hal/hal_i2c_bus_0.h"] = templates.hal_i2c_bus_0_h()
    files["hal/hal_i2c_bus_0.c"] = templates.hal_i2c_bus_0_c()

    for sensor in sensors:
        hal = sensor["hal_module"]
        files[f"hal/{hal}.h"] = templates.hal_ina219_h(sensor)
        files[f"hal/{hal}.c"] = templates.hal_ina219_c(sensor)

    files["tasks/task_sensor_poll.c"] = templates.task_sensor_poll_c(sensors)
    files["tasks/task_background.c"] = templates.task_background_c()
    files["main.c"] = templates.main_c(
        plan, sensors, boot_delays=_boot_delays_from_operations(operations)
    )
    files["Makefile"] = templates.makefile(project.project_id, sensors)

    return files


def emit_firmware_tree(
    output_dir: Path,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    plan: SchedulingPlan,
    operations: OperationsSequence | None = None,
) -> list[str]:
    """Write generated files to disk; return list of relative paths written."""
    files = generate_source_files(project, manifests, plan, operations=operations)
    written: list[str] = []

    for rel_path, content in files.items():
        dest = output_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        written.append(rel_path)

    return written
