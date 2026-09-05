"""Classify ProjectState nodes into execution tiers (T0–T3)."""

from eda_platform.agents.firmware_engineer.errors import FirmwareEngineerError
from eda_platform.agents.firmware_engineer.models import ExecutionTier, NodeClassification
from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    PinType,
    ProjectState,
)

_TIER_ORDER = {
    ExecutionTier.T3: 0,
    ExecutionTier.T2: 1,
    ExecutionTier.T1: 2,
    ExecutionTier.T0: 3,
}

_BUS_PIN_TYPES = {
    PinType.I2C_SDA,
    PinType.I2C_SCL,
    PinType.SPI_MOSI,
    PinType.SPI_MISO,
    PinType.SPI_SCK,
}
_UART_PIN_TYPES = {PinType.UART_TX, PinType.UART_RX}


def _max_tier(a: ExecutionTier, b: ExecutionTier) -> ExecutionTier:
    return a if _TIER_ORDER[a] >= _TIER_ORDER[b] else b


def _connected_pin_info(
    node_id: str, project: ProjectState, manifest: ComponentManifest
) -> tuple[set[PinType], set[str]]:
    pin_ids_on_nets: set[str] = set()
    for net in project.nets:
        for conn in net.connections:
            if conn.node_id == node_id:
                pin_ids_on_nets.add(conn.pin_id)

    pin_types: set[PinType] = set()
    features: set[str] = set()
    for pin in manifest.pins:
        if pin.pin_id in pin_ids_on_nets:
            pin_types.add(pin.pin_type)
            features.update(pin.supported_features or [])
    return pin_types, features


def _default_tier_for_type(component_type: ComponentType) -> ExecutionTier | None:
    if component_type in (ComponentType.MCU, ComponentType.PASSIVE):
        return None
    if component_type == ComponentType.MOTOR_DRIVER:
        return ExecutionTier.T0
    if component_type == ComponentType.ACTUATOR:
        return ExecutionTier.T1
    if component_type == ComponentType.SENSOR:
        return ExecutionTier.T1
    raise FirmwareEngineerError(f"unsupported component type '{component_type}'")


def _tier_from_pins(pin_types: set[PinType], features: set[str]) -> ExecutionTier:
    tier = ExecutionTier.T3

    if PinType.ANALOG_IN in pin_types and "ADC" in features:
        tier = _max_tier(tier, ExecutionTier.T0)
    if pin_types & _BUS_PIN_TYPES:
        tier = _max_tier(tier, ExecutionTier.T2)
    if pin_types & _UART_PIN_TYPES:
        tier = _max_tier(tier, ExecutionTier.T2)
    if PinType.GPIO_OUT in pin_types and "PWM" in features:
        tier = _max_tier(tier, ExecutionTier.T0)
    if PinType.GPIO_IN in pin_types:
        tier = _max_tier(tier, ExecutionTier.T1)
    if pin_types & {PinType.I2C_SDA, PinType.I2C_SCL}:
        tier = _max_tier(tier, ExecutionTier.T1)

    return tier


def _hal_module_name(node_id: str) -> str:
    return f"hal_{node_id.replace('-', '_')}"


def classify_nodes(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> list[NodeClassification]:
    """Classify every schedulable node into exactly one execution tier."""
    results: list[NodeClassification] = []

    for node in project.nodes:
        manifest = manifests.get(node.component_id)
        if manifest is None:
            raise FirmwareEngineerError(
                f"node '{node.node_id}' references unknown component '{node.component_id}'"
            )

        base_tier = _default_tier_for_type(manifest.type)
        if base_tier is None:
            continue

        pin_types, features = _connected_pin_info(node.node_id, project, manifest)
        if not pin_types:
            raise FirmwareEngineerError(
                f"node '{node.node_id}' has no connected pins — cannot classify for firmware"
            )

        pin_tier = _tier_from_pins(pin_types, features)
        final_tier = _max_tier(base_tier, pin_tier)

        results.append(
            NodeClassification(
                node_id=node.node_id,
                component_id=node.component_id,
                tier=final_tier,
                hal_module=_hal_module_name(node.node_id),
            )
        )

    if not results:
        raise FirmwareEngineerError(
            "no schedulable peripheral nodes found — place at least one sensor or actuator"
        )

    return results
