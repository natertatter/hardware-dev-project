"""Electrical validation engine for ProjectState against ComponentManifests."""

from __future__ import annotations

from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    Net,
    NetType,
    PinType,
    ProjectState,
)

# POWER pin_ids with fixed rail voltages (volts). All other POWER pins use logic_level_voltage.
#
# LIMITATION: ComponentManifest.Pin has no per-pin voltage field, so a component with
# multiple POWER pins at different rails (e.g. a 5V VBUS input alongside a 3.3V regulated
# output) cannot be fully described by the schema alone. This lookup table is a pragmatic
# stand-in keyed by common pin-naming conventions. Any POWER pin_id not listed here falls
# back to the component's single `logic_level_voltage`, which is only correct when a
# component exposes just one power rail. A more robust fix would add an optional
# `nominal_voltage` field to `Pin` itself; tracked as a future schema enhancement.
POWER_PIN_NOMINAL_VOLTAGES: dict[str, float] = {
    "VBUS": 5.0,
    "5V": 5.0,
    "3V3_OUT": 3.3,
    "3V3": 3.3,
}


class LogicCheckerError(Exception):
    """Fatal electrical validation error raised by the Logic Checker."""


def _manifest_for_node(
    node_id: str, project: ProjectState, manifests: dict[str, ComponentManifest]
) -> ComponentManifest:
    node = next(n for n in project.nodes if n.node_id == node_id)
    manifest = manifests.get(node.component_id)
    if manifest is None:
        raise LogicCheckerError(
            f"node '{node_id}' references unknown component_id '{node.component_id}'"
        )
    return manifest


def _find_pin(manifest: ComponentManifest, pin_id: str):
    for pin in manifest.pins:
        if pin.pin_id == pin_id:
            return pin
    return None


def _logic_level_voltage(manifest: ComponentManifest, pin_id: str, pin_type: PinType) -> float:
    """Resolve the logic/supply voltage (V) for a pin on a net."""
    if pin_type == PinType.GND:
        raise ValueError("GND pins have no logic level voltage")

    if pin_type == PinType.POWER:
        if pin_id in POWER_PIN_NOMINAL_VOLTAGES:
            return POWER_PIN_NOMINAL_VOLTAGES[pin_id]
        return manifest.power_requirements.logic_level_voltage

    return manifest.power_requirements.logic_level_voltage


def _node_i2c_address(
    node_id: str, project: ProjectState, manifests: dict[str, ComponentManifest]
) -> str | None:
    node = next(n for n in project.nodes if n.node_id == node_id)
    if node.assigned_i2c_address is not None:
        return node.assigned_i2c_address
    manifest = manifests.get(node.component_id)
    if manifest is None:
        return None
    return manifest.default_i2c_address


def check_voltage_levels(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Ensure connected pins share the same logic_level_voltage on each net."""
    for net in project.nets:
        if net.net_type == NetType.GND:
            continue

        voltages: list[tuple[str, str, float]] = []
        for conn in net.connections:
            manifest = _manifest_for_node(conn.node_id, project, manifests)
            pin = _find_pin(manifest, conn.pin_id)
            if pin is None:
                raise LogicCheckerError(
                    f"net '{net.net_id}': node '{conn.node_id}' has no pin '{conn.pin_id}'"
                )
            if pin.pin_type == PinType.GND:
                continue

            voltage = _logic_level_voltage(manifest, conn.pin_id, pin.pin_type)
            voltages.append((conn.node_id, conn.pin_id, voltage))

        if len(voltages) < 2:
            continue

        reference = voltages[0][2]
        for node_id, pin_id, voltage in voltages[1:]:
            if voltage != reference:
                raise LogicCheckerError(
                    f"voltage mismatch on net '{net.net_id}': "
                    f"'{voltages[0][1]}' ({reference}V) vs '{pin_id}' on '{node_id}' ({voltage}V)"
                )


def check_pin_exclusivity(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Ensure each MCU pin is wired into exactly one distinct net.

    A single net may legitimately contain many connections — e.g. an I2C/SPI bus
    net where the MCU's bus pin and several peripheral pins all share one net_id.
    That is not a collision: it is one net with multiple endpoints. What IS a
    collision is the same physical MCU pin appearing in two *different* net_ids,
    since a pin is a single electrical node and cannot belong to two nets without
    shorting them together. This applies uniformly to every pin type — including
    I2C/SPI bus pins — because a bus pin spanning two distinct bus nets (e.g. two
    separate I2C buses) is just as invalid as a GPIO pin wired into two nets.
    """
    pin_nets: dict[tuple[str, str], dict[str, None]] = {}

    for net in project.nets:
        for conn in net.connections:
            manifest = _manifest_for_node(conn.node_id, project, manifests)
            if manifest.type != ComponentType.MCU:
                continue

            pin = _find_pin(manifest, conn.pin_id)
            if pin is None:
                raise LogicCheckerError(
                    f"net '{net.net_id}': MCU node '{conn.node_id}' has no pin '{conn.pin_id}'"
                )

            key = (conn.node_id, conn.pin_id)
            # dict used as an insertion-ordered set (net_id -> None) to dedup
            # repeated appearances of this pin within the same net.
            pin_nets.setdefault(key, {})[net.net_id] = None

    for (node_id, pin_id), net_ids in pin_nets.items():
        unique_nets = list(net_ids)
        if len(unique_nets) > 1:
            raise LogicCheckerError(
                f"pin collision: MCU '{node_id}' pin '{pin_id}' assigned to multiple nets: "
                f"{', '.join(unique_nets)}"
            )


def check_i2c_collisions(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Ensure no duplicate I2C addresses on the same bus net."""
    for net in project.nets:
        if not _net_is_i2c_bus(net, project, manifests):
            continue

        addresses: dict[str, str] = {}
        for conn in net.connections:
            manifest = _manifest_for_node(conn.node_id, project, manifests)
            pin = _find_pin(manifest, conn.pin_id)
            if pin is None:
                raise LogicCheckerError(
                    f"net '{net.net_id}': node '{conn.node_id}' has no pin '{conn.pin_id}'"
                )
            if pin.pin_type not in (PinType.I2C_SDA, PinType.I2C_SCL):
                continue

            address = _node_i2c_address(conn.node_id, project, manifests)
            if address is None:
                continue

            if address in addresses and addresses[address] != conn.node_id:
                raise LogicCheckerError(
                    f"I2C address collision on bus net '{net.net_id}': "
                    f"address {address} used by '{addresses[address]}' and '{conn.node_id}'"
                )
            addresses[address] = conn.node_id


def _nodes_on_net(net: Net) -> set[str]:
    return {c.node_id for c in net.connections}


def _node_has_power_connection(
    node_id: str, project: ProjectState, manifests: dict[str, ComponentManifest]
) -> bool:
    for net in project.nets:
        if net.net_type != NetType.POWER:
            continue
        for conn in net.connections:
            if conn.node_id != node_id:
                continue
            manifest = _manifest_for_node(conn.node_id, project, manifests)
            pin = _find_pin(manifest, conn.pin_id)
            if pin and pin.pin_type == PinType.POWER:
                return True
    return False


def _node_has_gnd_connection(node_id: str, project: ProjectState) -> bool:
    for net in project.nets:
        if net.net_type != NetType.GND:
            continue
        if node_id in _nodes_on_net(net):
            return True
    return False


def check_common_gnd(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Every powered node must share a common GND net."""
    powered_nodes = [
        n.node_id
        for n in project.nodes
        if _node_has_power_connection(n.node_id, project, manifests)
    ]
    if not powered_nodes:
        return

    gnd_nodes: set[str] = set()
    for net in project.nets:
        if net.net_type == NetType.GND:
            gnd_nodes.update(_nodes_on_net(net))

    for node_id in powered_nodes:
        if node_id not in gnd_nodes:
            raise LogicCheckerError(
                f"powered node '{node_id}' is not connected to a GND net"
            )

    if len(gnd_nodes) < len(powered_nodes):
        ungrounded = [n for n in powered_nodes if n not in gnd_nodes]
        if ungrounded:
            raise LogicCheckerError(
                f"nodes missing GND connection: {', '.join(ungrounded)}"
            )


def check_current_budget(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Sum of peripheral current draw on a POWER net must not exceed MCU source limit."""
    for net in project.nets:
        if net.net_type != NetType.POWER:
            continue

        total_draw_ma = 0.0
        source_limit_ma: float | None = None
        source_pin_id: str | None = None
        source_node_id: str | None = None

        for conn in net.connections:
            manifest = _manifest_for_node(conn.node_id, project, manifests)
            pin = _find_pin(manifest, conn.pin_id)
            if pin is None:
                raise LogicCheckerError(
                    f"net '{net.net_id}': node '{conn.node_id}' has no pin '{conn.pin_id}'"
                )

            if manifest.type == ComponentType.MCU and pin.pin_type == PinType.POWER:
                if pin.max_current_source_ma is not None:
                    source_limit_ma = pin.max_current_source_ma
                    source_pin_id = conn.pin_id
                    source_node_id = conn.node_id
            else:
                total_draw_ma += manifest.power_requirements.max_current_draw_ma

        if source_limit_ma is not None and total_draw_ma > source_limit_ma:
            raise LogicCheckerError(
                f"current budget exceeded on net '{net.net_id}': "
                f"total draw {total_draw_ma}mA exceeds MCU pin '{source_pin_id}' "
                f"on '{source_node_id}' limit of {source_limit_ma}mA"
            )


def check_output_conflicts(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Output pins (GPIO_OUT) cannot connect to other output pins on the same net."""
    for net in project.nets:
        output_pins: list[tuple[str, str]] = []
        for conn in net.connections:
            manifest = _manifest_for_node(conn.node_id, project, manifests)
            pin = _find_pin(manifest, conn.pin_id)
            if pin is None:
                raise LogicCheckerError(
                    f"net '{net.net_id}': node '{conn.node_id}' has no pin '{conn.pin_id}'"
                )
            if pin.pin_type == PinType.GPIO_OUT:
                output_pins.append((conn.node_id, conn.pin_id))

        if len(output_pins) > 1:
            pins_desc = ", ".join(f"{nid}:{pid}" for nid, pid in output_pins)
            raise LogicCheckerError(
                f"output-to-output conflict on net '{net.net_id}': {pins_desc}"
            )


def check_uart_polarity(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """UART TX pins may only share a net with UART RX pins (and vice versa)."""
    for net in project.nets:
        pin_types_on_net: list[tuple[str, str, PinType]] = []
        for conn in net.connections:
            manifest = _manifest_for_node(conn.node_id, project, manifests)
            pin = _find_pin(manifest, conn.pin_id)
            if pin is None:
                raise LogicCheckerError(
                    f"net '{net.net_id}': node '{conn.node_id}' has no pin '{conn.pin_id}'"
                )
            if pin.pin_type in (PinType.UART_TX, PinType.UART_RX):
                pin_types_on_net.append((conn.node_id, conn.pin_id, pin.pin_type))

        if len(pin_types_on_net) < 2:
            continue

        types = {pt for _, _, pt in pin_types_on_net}
        if types == {PinType.UART_TX} or types == {PinType.UART_RX}:
            raise LogicCheckerError(
                f"UART polarity violation on net '{net.net_id}': "
                f"TX must connect to RX, not to another TX or RX"
            )


def _net_is_i2c_bus(
    net: Net, project: ProjectState, manifests: dict[str, ComponentManifest]
) -> bool:
    """True if the net carries I2C SDA or SCL connections."""
    for conn in net.connections:
        manifest = _manifest_for_node(conn.node_id, project, manifests)
        pin = _find_pin(manifest, conn.pin_id)
        if pin is None:
            raise LogicCheckerError(
                f"net '{net.net_id}': node '{conn.node_id}' has no pin '{conn.pin_id}'"
            )
        if pin.pin_type in (PinType.I2C_SDA, PinType.I2C_SCL):
            return True
    return False


def validate_project(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Run all Logic Checker rules. Raises LogicCheckerError on first fatal violation."""
    check_voltage_levels(project, manifests)
    check_common_gnd(project, manifests)
    check_current_budget(project, manifests)
    check_pin_exclusivity(project, manifests)
    check_output_conflicts(project, manifests)
    check_uart_polarity(project, manifests)
    check_i2c_collisions(project, manifests)
