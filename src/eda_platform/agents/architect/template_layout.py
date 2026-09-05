"""Deterministic template layout: MCU + I2C sensor auto-wiring."""

from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    Net,
    NetConnection,
    NetType,
    Node,
    Pin,
    PinType,
    ProjectState,
)


def _manifest_for_node(
    node: Node, manifests: dict[str, ComponentManifest]
) -> ComponentManifest:
    manifest = manifests.get(node.component_id)
    if manifest is None:
        raise ValueError(
            f"node '{node.node_id}' references unknown component_id '{node.component_id}'"
        )
    return manifest


def _pin_by_type(manifest: ComponentManifest, pin_type: PinType) -> Pin:
    matches = [p for p in manifest.pins if p.pin_type == pin_type]
    if not matches:
        raise ValueError(
            f"component '{manifest.component_id}' has no pin with type '{pin_type.value}'"
        )
    return matches[0]


def _mcu_power_out_pin(manifest: ComponentManifest) -> Pin:
    """MCU regulated output rail — prefer a POWER pin that can source current."""
    power_pins = [p for p in manifest.pins if p.pin_type == PinType.POWER]
    if not power_pins:
        raise ValueError(
            f"MCU '{manifest.component_id}' has no POWER pin for template wiring"
        )
    sourcing = [p for p in power_pins if p.max_current_source_ma is not None]
    if len(sourcing) == 1:
        return sourcing[0]
    if len(sourcing) > 1:
        raise ValueError(
            f"MCU '{manifest.component_id}' has multiple source POWER pins — "
            "template auto-wire cannot choose unambiguously"
        )
    return power_pins[0]


def _find_mcu(nodes: list[Node], manifests: dict[str, ComponentManifest]) -> Node:
    for node in nodes:
        manifest = _manifest_for_node(node, manifests)
        if manifest.type == ComponentType.MCU:
            return node
    raise ValueError("No MCU node found — place an MCU before auto-wiring")


def _find_sensors(
    nodes: list[Node], manifests: dict[str, ComponentManifest]
) -> list[Node]:
    sensors: list[Node] = []
    for node in nodes:
        manifest = _manifest_for_node(node, manifests)
        if manifest.type == ComponentType.SENSOR:
            sensors.append(node)
    return sensors


def template_i2c_layout(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> tuple[ProjectState, int]:
    """Add standard power/GND/I2C nets between MCU and all sensor nodes.

    Pin endpoints are resolved by ``pin_type`` from each manifest — never by
    hardcoded pin_id strings — so auto-wire works across MCU/sensor families.

    Returns updated ProjectState and count of new nets added.
    Does not remove existing nets — appends template wiring.
    """
    mcu = _find_mcu(project.nodes, manifests)
    sensors = _find_sensors(project.nodes, manifests)
    mcu_manifest = _manifest_for_node(mcu, manifests)

    mcu_power_pin = _mcu_power_out_pin(mcu_manifest)
    mcu_gnd_pin = _pin_by_type(mcu_manifest, PinType.GND)
    mcu_sda_pin = _pin_by_type(mcu_manifest, PinType.I2C_SDA)
    mcu_scl_pin = _pin_by_type(mcu_manifest, PinType.I2C_SCL)

    existing_net_ids = {n.net_id for n in project.nets}
    new_nets: list[Net] = []
    wires_added = 0

    for sensor in sensors:
        sensor_manifest = _manifest_for_node(sensor, manifests)
        prefix = f"auto_{sensor.node_id}"

        sensor_power_pin = _pin_by_type(sensor_manifest, PinType.POWER)
        sensor_gnd_pin = _pin_by_type(sensor_manifest, PinType.GND)
        sensor_sda_pin = _pin_by_type(sensor_manifest, PinType.I2C_SDA)
        sensor_scl_pin = _pin_by_type(sensor_manifest, PinType.I2C_SCL)

        net_specs = [
            (f"{prefix}_vcc", NetType.POWER, mcu_power_pin.pin_id, sensor_power_pin.pin_id),
            (f"{prefix}_gnd", NetType.GND, mcu_gnd_pin.pin_id, sensor_gnd_pin.pin_id),
            (f"{prefix}_sda", NetType.BUS, mcu_sda_pin.pin_id, sensor_sda_pin.pin_id),
            (f"{prefix}_scl", NetType.BUS, mcu_scl_pin.pin_id, sensor_scl_pin.pin_id),
        ]

        for net_id, net_type, mcu_pin_id, sensor_pin_id in net_specs:
            if net_id in existing_net_ids:
                continue
            new_nets.append(
                Net(
                    net_id=net_id,
                    net_type=net_type,
                    connections=[
                        NetConnection(node_id=mcu.node_id, pin_id=mcu_pin_id),
                        NetConnection(node_id=sensor.node_id, pin_id=sensor_pin_id),
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
