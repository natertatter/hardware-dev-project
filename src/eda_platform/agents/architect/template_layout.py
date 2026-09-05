"""Deterministic template layout: MCU + I2C sensor auto-wiring."""

from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    Net,
    NetConnection,
    NetType,
    Node,
    PinType,
    ProjectState,
)

# Standard RP2040 I2C pin mapping used by mock manifests.
MCU_I2C_SDA_PIN = "GPIO4"
MCU_I2C_SCL_PIN = "GPIO5"
MCU_POWER_OUT_PIN = "3V3_OUT"
MCU_GND_PIN = "GND"

SENSOR_POWER_PIN = "VCC"
SENSOR_GND_PIN = "GND"
SENSOR_SDA_PIN = "I2C_SDA"
SENSOR_SCL_PIN = "I2C_SCL"


def _find_mcu(nodes: list[Node], manifests: dict[str, ComponentManifest]) -> Node:
    for node in nodes:
        manifest = manifests.get(node.component_id)
        if manifest and manifest.type == ComponentType.MCU:
            return node
    raise ValueError("No MCU node found — place an MCU before auto-wiring")


def _find_sensors(
    nodes: list[Node], manifests: dict[str, ComponentManifest]
) -> list[Node]:
    sensors = []
    for node in nodes:
        manifest = manifests.get(node.component_id)
        if manifest and manifest.type == ComponentType.SENSOR:
            sensors.append(node)
    return sensors


def _has_pin(manifest: ComponentManifest, pin_id: str) -> bool:
    return any(p.pin_id == pin_id for p in manifest.pins)


def template_i2c_layout(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> tuple[ProjectState, int]:
    """Add standard power/GND/I2C nets between MCU and all sensor nodes.

    Returns updated ProjectState and count of new nets added.
    Does not remove existing nets — appends template wiring.
    """
    mcu = _find_mcu(project.nodes, manifests)
    sensors = _find_sensors(project.nodes, manifests)
    mcu_manifest = manifests[mcu.component_id]

    if not _has_pin(mcu_manifest, MCU_POWER_OUT_PIN):
        raise ValueError(f"MCU '{mcu.component_id}' has no '{MCU_POWER_OUT_PIN}' pin for template wiring")

    existing_net_ids = {n.net_id for n in project.nets}
    new_nets: list[Net] = []
    wires_added = 0

    for i, sensor in enumerate(sensors):
        sensor_manifest = manifests[sensor.component_id]
        prefix = f"auto_{sensor.node_id}"

        net_specs = [
            (f"{prefix}_vcc", NetType.POWER, MCU_POWER_OUT_PIN, SENSOR_POWER_PIN),
            (f"{prefix}_gnd", NetType.GND, MCU_GND_PIN, SENSOR_GND_PIN),
            (f"{prefix}_sda", NetType.BUS, MCU_I2C_SDA_PIN, SENSOR_SDA_PIN),
            (f"{prefix}_scl", NetType.BUS, MCU_I2C_SCL_PIN, SENSOR_SCL_PIN),
        ]

        for net_id, net_type, mcu_pin, sensor_pin in net_specs:
            if net_id in existing_net_ids:
                continue
            if not _has_pin(sensor_manifest, sensor_pin):
                continue
            new_nets.append(
                Net(
                    net_id=net_id,
                    net_type=net_type,
                    connections=[
                        NetConnection(node_id=mcu.node_id, pin_id=mcu_pin),
                        NetConnection(node_id=sensor.node_id, pin_id=sensor_pin),
                    ],
                )
            )
            existing_net_ids.add(net_id)
            wires_added += 1

    if wires_added == 0 and not sensors:
        raise ValueError("No sensor nodes found — place a sensor before auto-wiring")

    return (
        ProjectState(
            project_id=project.project_id,
            nodes=project.nodes,
            nets=[*project.nets, *new_nets],
        ),
        wires_added,
    )
