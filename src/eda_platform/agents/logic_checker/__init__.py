"""Logic Checker agent — ProjectState validation against ComponentManifests."""

from eda_platform.agents.logic_checker.errors import ValidationIssue, ValidationResult
from eda_platform.agents.logic_checker.logic_checker import (
    LogicCheckerError,
    check_common_gnd,
    check_current_budget,
    check_i2c_collisions,
    check_output_conflicts,
    check_pin_exclusivity,
    check_uart_polarity,
    check_voltage_levels,
    validate_project,
)
from eda_platform.agents.logic_checker.runner import validate_project_collect

__all__ = [
    "LogicCheckerError",
    "ValidationIssue",
    "ValidationResult",
    "check_common_gnd",
    "check_current_budget",
    "check_i2c_collisions",
    "check_output_conflicts",
    "check_pin_exclusivity",
    "check_uart_polarity",
    "check_voltage_levels",
    "validate_project",
    "validate_project_collect",
]
