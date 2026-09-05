"""Emit all firmware source files for a scheduling plan."""

from pathlib import Path

from eda_platform.agents.firmware_engineer.codegen import templates
from eda_platform.agents.firmware_engineer.models import SchedulingPlan
from eda_platform.schemas import ComponentManifest, ProjectState


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
        if manifest.type.value != "SENSOR":
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


def generate_source_files(
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    plan: SchedulingPlan,
) -> dict[str, str]:
    """Return relative path → file contents for the full firmware tree."""
    sensors = _sensor_nodes(plan, project, manifests)
    files: dict[str, str] = {}

    files["platform/board_config.h"] = templates.board_config_h(plan)
    files["hal/hal_i2c_bus_0.h"] = templates.hal_i2c_bus_0_h()
    files["hal/hal_i2c_bus_0.c"] = templates.hal_i2c_bus_0_c()

    for sensor in sensors:
        hal = sensor["hal_module"]
        files[f"hal/{hal}.h"] = templates.hal_ina219_h(sensor)
        files[f"hal/{hal}.c"] = templates.hal_ina219_c(sensor)

    files["tasks/task_sensor_poll.c"] = templates.task_sensor_poll_c(sensors)
    files["tasks/task_background.c"] = templates.task_background_c()
    files["main.c"] = templates.main_c(plan, sensors)
    files["Makefile"] = templates.makefile(project.project_id, sensors)

    return files


def emit_firmware_tree(
    output_dir: Path,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    plan: SchedulingPlan,
) -> list[str]:
    """Write generated files to disk; return list of relative paths written."""
    files = generate_source_files(project, manifests, plan)
    written: list[str] = []

    for rel_path, content in files.items():
        dest = output_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)
        written.append(rel_path)

    return written
