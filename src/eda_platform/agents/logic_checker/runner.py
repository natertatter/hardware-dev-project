"""Run all Logic Checker rules and collect structured results."""

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
)
from eda_platform.schemas import ComponentManifest, ProjectState

# Order: power/safety first, then pins, then protocols.
_ALL_CHECKS = [
    ("check_voltage_levels", check_voltage_levels),
    ("check_common_gnd", check_common_gnd),
    ("check_current_budget", check_current_budget),
    ("check_pin_exclusivity", check_pin_exclusivity),
    ("check_output_conflicts", check_output_conflicts),
    ("check_uart_polarity", check_uart_polarity),
    ("check_i2c_collisions", check_i2c_collisions),
]


def validate_project_collect(
    project: ProjectState, manifests: dict[str, ComponentManifest]
) -> ValidationResult:
    """Run every rule and return all fatal issues (does not stop at first failure)."""
    issues: list[ValidationIssue] = []

    for rule_name, check_fn in _ALL_CHECKS:
        try:
            check_fn(project, manifests)
        except LogicCheckerError as exc:
            issues.append(
                ValidationIssue(
                    rule=rule_name,
                    severity="fatal",
                    message=str(exc),
                )
            )

    return ValidationResult(valid=len(issues) == 0, errors=issues)
