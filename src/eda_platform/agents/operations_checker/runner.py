"""Run all Operations Checker rules and collect structured results."""

from eda_platform.agents.firmware_engineer.models import SchedulingPlan
from eda_platform.agents.logic_checker import validate_project_collect
from eda_platform.agents.operations_checker.errors import (
    OperationsValidationIssue,
    OperationsValidationResult,
)
from eda_platform.agents.operations_checker.operations_checker import (
    check_boot_order,
    check_dependency_integrity,
    check_hal_binding,
    check_node_references,
    check_open_questions,
    check_schematic_prerequisite,
    check_timing_bounds,
)
from eda_platform.schemas import ComponentManifest, OperationsSequence, ProjectState

_RULE_CHECKS = [
    ("check_node_references", check_node_references),
    ("check_dependency_integrity", check_dependency_integrity),
    ("check_hal_binding", check_hal_binding),
    ("check_boot_order", check_boot_order),
    ("check_open_questions", check_open_questions),
]


def validate_operations_collect(
    sequence: OperationsSequence,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    scheduling: SchedulingPlan | None = None,
) -> OperationsValidationResult:
    """Run every operations rule and return all issues."""
    schematic_result = validate_project_collect(project, manifests)
    schematic_valid = schematic_result.valid

    issues: list[OperationsValidationIssue] = []
    seen: set[tuple[str, str, str | None]] = set()

    def _add(issue: OperationsValidationIssue) -> None:
        key = (issue.rule, issue.message, issue.step_id)
        if key in seen:
            return
        seen.add(key)
        issues.append(issue)

    for _name, check_fn in _RULE_CHECKS:
        for issue in check_fn(sequence, project, manifests):
            _add(issue)

    for issue in check_schematic_prerequisite(
        sequence, project, manifests, schematic_valid=schematic_valid
    ):
        _add(issue)

    for issue in check_timing_bounds(sequence, project, manifests, scheduling=scheduling):
        _add(issue)

    has_fatal = any(i.severity == "fatal" for i in issues)
    has_blocking_question = any(i.severity == "question" for i in issues)
    valid = not has_fatal and not has_blocking_question

    return OperationsValidationResult(valid=valid, errors=issues)
