"""Logic Checker agent — ProjectState validation against ComponentManifests."""

from eda_platform.agents.logic_checker.logic_checker import (
    LogicCheckerError,
    check_i2c_collisions,
    check_pin_exclusivity,
    check_voltage_levels,
    validate_project,
)

__all__ = [
    "LogicCheckerError",
    "check_i2c_collisions",
    "check_pin_exclusivity",
    "check_voltage_levels",
    "validate_project",
]
