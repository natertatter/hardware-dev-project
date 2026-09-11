"""Domain best-practice defaults for operations refinement."""

from eda_platform.schemas import ComponentType

# Timing defaults (ms) — overridden by manifest fields when Phase 3 adds them.
POWER_ON_SETTLE_MS = 100
I2C_BUS_SETTLE_MS = 10
I2C_SENSOR_POLL_PERIOD_MS = 20
MOTOR_RAMP_DELAY_MS = 200
MOTOR_DIRECTION_CHANGE_PAUSE_MS = 500
ESTOP_RELEASE_DELAY_MS = 1000

# Keywords in step descriptions → suggested HAL call suffixes per component type.
_HAL_CALL_HINTS: dict[ComponentType, list[tuple[str, str]]] = {
    ComponentType.SENSOR: [
        ("read", "read"),
        ("current", "read_current_ma"),
        ("poll", "read"),
        ("sample", "read"),
        ("monitor", "read"),
    ],
    ComponentType.MOTOR_DRIVER: [
        ("enable", "enable"),
        ("disable", "disable"),
        ("speed", "set_speed"),
        ("ramp", "set_speed"),
        ("stop", "stop"),
        ("home", "home"),
    ],
    ComponentType.ACTUATOR: [
        ("enable", "enable"),
        ("disable", "disable"),
        ("actuate", "actuate"),
    ],
}

# Boot-order keywords that should precede peripheral operations.
_BOOT_KEYWORDS = ("power", "rail", "enable", "boot", "init", "reset")
_PERIPHERAL_KEYWORDS = ("read", "poll", "sample", "motor", "actuate", "sensor")


def suggest_hal_call(description: str, component_type: ComponentType, hal_module: str) -> str | None:
    """Map natural-language step to a HAL call name."""
    lower = description.lower()
    hints = _HAL_CALL_HINTS.get(component_type, [])
    for keyword, suffix in hints:
        if keyword in lower:
            return f"{hal_module}_{suffix}"
    return None


def is_boot_step(description: str) -> bool:
    lower = description.lower()
    return any(kw in lower for kw in _BOOT_KEYWORDS)


def is_peripheral_step(description: str) -> bool:
    lower = description.lower()
    return any(kw in lower for kw in _PERIPHERAL_KEYWORDS)
