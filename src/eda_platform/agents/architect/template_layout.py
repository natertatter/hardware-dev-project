"""Deterministic template layout: MCU + peripheral auto-wiring by protocol."""

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
from eda_platform.schemas.protocols import default_protocol

# Pin type groups per communication protocol for auto-wire template matching.
_PROTOCOL_BUS_PINS: dict[str, list[PinType]] = {
    "I2C": [PinType.I2C_SDA, PinType.I2C_SCL],
    "SPI": [PinType.SPI_MOSI, PinType.SPI_MISO, PinType.SPI_SCK, PinType.SPI_CS],
    "UART": [PinType.UART_TX, PinType.UART_RX],
    "PWM": [PinType.GPIO_OUT],
}


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


def _pin_by_type_optional(manifest: ComponentManifest, pin_type: PinType) -> Pin | None:
    matches = [p for p in manifest.pins if p.pin_type == pin_type]
    return matches[0] if matches else None


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


def _peripheral_nodes(
    nodes: list[Node], manifests: dict[str, ComponentManifest]
) -> list[Node]:
    peripherals: list[Node] = []
    for node in nodes:
        manifest = _manifest_for_node(node, manifests)
        if manifest.type in (ComponentType.SENSOR, ComponentType.MOTOR_DRIVER, ComponentType.ACTUATOR):
            peripherals.append(node)
    return peripherals


def _effective_protocol(
    node: Node, manifest: ComponentManifest
) -> str | None:
    if node.selected_protocol:
        return node.selected_protocol
    return default_protocol(manifest)


def _pwm_pin(manifest: ComponentManifest) -> Pin | None:
    for pin in manifest.pins:
        if pin.pin_type == PinType.GPIO_OUT and "PWM" in (pin.supported_features or []):
            return pin
    return None


def _bus_pin_pairs(
    mcu_manifest: ComponentManifest,
    peripheral_manifest: ComponentManifest,
    protocol: str,
) -> list[tuple[PinType, str]]:
    """Return (pin_type, net_suffix) pairs to wire for the given protocol."""
    if protocol == "PWM":
        mcu_pwm = _pwm_pin(mcu_manifest)
        periph_pwm = _pwm_pin(peripheral_manifest)
        if mcu_pwm is None or periph_pwm is None:
            return []
        return [(PinType.GPIO_OUT, "pwm")]

    pin_types = _PROTOCOL_BUS_PINS.get(protocol, [])
    pairs: list[tuple[PinType, str]] = []
    for pt in pin_types:
        if protocol == "SPI" and pt == PinType.SPI_CS:
            if _pin_by_type_optional(peripheral_manifest, pt) is None:
                continue
        if _pin_by_type_optional(mcu_manifest, pt) and _pin_by_type_optional(peripheral_manifest, pt):
            suffix = pt.value.lower()
            pairs.append((pt, suffix))
    return pairs


def template_auto_wire(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> tuple[ProjectState, int]:
    """Add power/GND/bus nets between MCU and peripheral nodes by selected protocol.

    Each peripheral's ``selected_protocol`` (or manifest default) determines which
    bus pins are wired. POWER and GND are always connected.

    Returns updated ProjectState and count of new nets added.
    Does not remove existing nets — appends template wiring.
    """
    mcu = _find_mcu(project.nodes, manifests)
    peripherals = _peripheral_nodes(project.nodes, manifests)
    mcu_manifest = _manifest_for_node(mcu, manifests)

    mcu_power_pin = _mcu_power_out_pin(mcu_manifest)
    mcu_gnd_pin = _pin_by_type(mcu_manifest, PinType.GND)

    existing_net_ids = {n.net_id for n in project.nets}
    new_nets: list[Net] = []
    wires_added = 0

    for peripheral in peripherals:
        peripheral_manifest = _manifest_for_node(peripheral, manifests)
        protocol = _effective_protocol(peripheral, peripheral_manifest)
        if protocol is None:
            continue

        prefix = f"auto_{peripheral.node_id}"

        try:
            peripheral_power_pin = _pin_by_type(peripheral_manifest, PinType.POWER)
            peripheral_gnd_pin = _pin_by_type(peripheral_manifest, PinType.GND)
        except ValueError:
            continue

        net_specs: list[tuple[str, NetType, str, str]] = [
            (f"{prefix}_vcc", NetType.POWER, mcu_power_pin.pin_id, peripheral_power_pin.pin_id),
            (f"{prefix}_gnd", NetType.GND, mcu_gnd_pin.pin_id, peripheral_gnd_pin.pin_id),
        ]

        bus_pairs = _bus_pin_pairs(mcu_manifest, peripheral_manifest, protocol)
        for pin_type, suffix in bus_pairs:
            if protocol == "PWM":
                mcu_pin = _pwm_pin(mcu_manifest)
                periph_pin = _pwm_pin(peripheral_manifest)
                if mcu_pin and periph_pin:
                    net_specs.append(
                        (f"{prefix}_{suffix}", NetType.SIGNAL, mcu_pin.pin_id, periph_pin.pin_id)
                    )
            else:
                mcu_pin = _pin_by_type_optional(mcu_manifest, pin_type)
                periph_pin = _pin_by_type_optional(peripheral_manifest, pin_type)
                if mcu_pin and periph_pin:
                    net_type = NetType.BUS if protocol in ("I2C", "SPI", "UART") else NetType.SIGNAL
                    net_specs.append(
                        (f"{prefix}_{suffix}", net_type, mcu_pin.pin_id, periph_pin.pin_id)
                    )

        for net_id, net_type, mcu_pin_id, peripheral_pin_id in net_specs:
            if net_id in existing_net_ids:
                continue
            new_nets.append(
                Net(
                    net_id=net_id,
                    net_type=net_type,
                    connections=[
                        NetConnection(node_id=mcu.node_id, pin_id=mcu_pin_id),
                        NetConnection(node_id=peripheral.node_id, pin_id=peripheral_pin_id),
                    ],
                )
            )
            existing_net_ids.add(net_id)
            wires_added += 1

    if wires_added == 0 and not peripherals:
        raise ValueError("No peripheral nodes found — place a sensor or actuator before auto-wiring")

    return (
        ProjectState(
            project_id=project.project_id,
            nodes=project.nodes,
            nets=[*project.nets, *new_nets],
        ),
        wires_added,
    )


def template_i2c_layout(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> tuple[ProjectState, int]:
    """Backward-compatible alias: auto-wire using each node's protocol (defaults to I2C)."""
    return template_auto_wire(project, manifests)
