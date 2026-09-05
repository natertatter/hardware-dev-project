"""Electrical validation engine for ProjectState against ComponentManifests."""

from __future__ import annotations

from eda_platform.schemas import ComponentManifest, ComponentType, NetType, PinType, ProjectState
from eda_platform.schemas.project_state import Net

# Pin types that form shared peripheral buses (exempt from MCU pin-exclusivity).
BUS_PIN_TYPES = frozenset(
    {
        PinType.I2C_SDA,
        PinType.I2C_SCL,
        PinType.SPI_MOSI,
        PinType.SPI_MISO,
        PinType.SPI_SCK,
        PinType.SPI_CS,
    }
)

# POWER pin_ids with fixed rail voltages (volts). All other POWER pins use logic_level_voltage.
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
    """Ensure each MCU pin appears on at most one net (I2C/SPI bus nets exempt)."""
    pin_nets: dict[tuple[str, str], list[str]] = {}

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

            # I2C/SPI bus pins on BUS nets are shared across devices — not exclusive.
            if pin.pin_type in BUS_PIN_TYPES and net.net_type == NetType.BUS:
                continue

            key = (conn.node_id, conn.pin_id)
            pin_nets.setdefault(key, []).append(net.net_id)

    for (node_id, pin_id), net_ids in pin_nets.items():
        unique_nets = list(dict.fromkeys(net_ids))
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
            if pin is None or pin.pin_type not in (PinType.I2C_SDA, PinType.I2C_SCL):
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


def _net_is_i2c_bus(
    net: Net, project: ProjectState, manifests: dict[str, ComponentManifest]
) -> bool:
    """True if the net carries I2C SDA or SCL connections."""
    for conn in net.connections:
        manifest = _manifest_for_node(conn.node_id, project, manifests)
        pin = _find_pin(manifest, conn.pin_id)
        if pin is not None and pin.pin_type in (PinType.I2C_SDA, PinType.I2C_SCL):
            return True
    return False


def validate_project(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> None:
    """Run all Logic Checker rules. Raises LogicCheckerError on fatal violations."""
    check_voltage_levels(project, manifests)
    check_pin_exclusivity(project, manifests)
    check_i2c_collisions(project, manifests)
