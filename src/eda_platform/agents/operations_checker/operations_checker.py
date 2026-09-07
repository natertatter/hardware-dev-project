"""Individual validation rules for operations sequences."""

from eda_platform.agents.operations_checker.errors import OperationsValidationIssue
from eda_platform.agents.operations_refiner.best_practices import is_boot_step, is_peripheral_step
from eda_platform.agents.firmware_engineer.models import SchedulingPlan
from eda_platform.schemas import (
    ComponentManifest,
    FidelityLevel,
    OperationsSequence,
    ProjectState,
)


def check_node_references(
    sequence: OperationsSequence, project: ProjectState, _manifests: dict
) -> list[OperationsValidationIssue]:
    issues: list[OperationsValidationIssue] = []
    node_ids = {n.node_id for n in project.nodes}
    for step in sequence.steps:
        if step.target_node_id and step.target_node_id not in node_ids:
            issues.append(
                OperationsValidationIssue(
                    rule="check_node_references",
                    severity="fatal",
                    message=(
                        f"step '{step.step_id}' references unknown node "
                        f"'{step.target_node_id}'"
                    ),
                    step_id=step.step_id,
                    node_id=step.target_node_id,
                )
            )
    return issues


def check_dependency_integrity(
    sequence: OperationsSequence, _project: ProjectState, _manifests: dict
) -> list[OperationsValidationIssue]:
    issues: list[OperationsValidationIssue] = []
    step_ids = {s.step_id for s in sequence.steps}

    for step in sequence.steps:
        for dep in step.depends_on:
            if dep not in step_ids:
                issues.append(
                    OperationsValidationIssue(
                        rule="check_dependency_integrity",
                        severity="fatal",
                        message=f"step '{step.step_id}' depends on unknown step '{dep}'",
                        step_id=step.step_id,
                    )
                )

    # Cycle detection via DFS
    adjacency = {s.step_id: s.depends_on for s in sequence.steps}
    visited: set[str] = set()
    stack: set[str] = set()

    def has_cycle(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for neighbor in adjacency.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in stack:
                return True
        stack.remove(node)
        return False

    for sid in step_ids:
        if sid not in visited and has_cycle(sid):
            issues.append(
                OperationsValidationIssue(
                    rule="check_dependency_integrity",
                    severity="fatal",
                    message="dependency cycle detected in operations sequence",
                )
            )
            break

    return issues


def check_hal_binding(
    sequence: OperationsSequence,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
) -> list[OperationsValidationIssue]:
    issues: list[OperationsValidationIssue] = []
    for step in sequence.steps:
        if not step.hal_call or not step.target_node_id:
            continue
        expected_prefix = f"hal_{step.target_node_id.replace('-', '_')}"
        if not step.hal_call.startswith(expected_prefix):
            issues.append(
                OperationsValidationIssue(
                    rule="check_hal_binding",
                    severity="warning",
                    message=(
                        f"step '{step.step_id}' hal_call '{step.hal_call}' "
                        f"does not match expected prefix '{expected_prefix}'"
                    ),
                    step_id=step.step_id,
                    node_id=step.target_node_id,
                )
            )
    return issues


def check_timing_bounds(
    sequence: OperationsSequence,
    _project: ProjectState,
    _manifests: dict,
    scheduling: SchedulingPlan | None = None,
) -> list[OperationsValidationIssue]:
    if scheduling is None:
        return []

    issues: list[OperationsValidationIssue] = []
    min_period = min((t.period_ms for t in scheduling.tasks), default=1)

    for step in sequence.steps:
        if step.timing and step.timing.period_ms is not None:
            if step.timing.period_ms < min_period:
                issues.append(
                    OperationsValidationIssue(
                        rule="check_timing_bounds",
                        severity="warning",
                        message=(
                            f"step '{step.step_id}' period {step.timing.period_ms}ms "
                            f"is below scheduling minimum {min_period}ms"
                        ),
                        step_id=step.step_id,
                    )
                )
    return issues


def check_boot_order(
    sequence: OperationsSequence, _project: ProjectState, _manifests: dict
) -> list[OperationsValidationIssue]:
    issues: list[OperationsValidationIssue] = []
    boot_indices = [
        i for i, s in enumerate(sequence.steps) if is_boot_step(s.description)
    ]
    if not boot_indices:
        return issues

    first_boot = boot_indices[0]
    for i, step in enumerate(sequence.steps):
        if i < first_boot and is_peripheral_step(step.description):
            issues.append(
                OperationsValidationIssue(
                    rule="check_boot_order",
                    severity="warning",
                    message=(
                        f"peripheral step '{step.step_id}' appears before boot/power "
                        f"step '{sequence.steps[first_boot].step_id}'"
                    ),
                    step_id=step.step_id,
                )
            )
    return issues


def check_open_questions(
    sequence: OperationsSequence, _project: ProjectState, _manifests: dict
) -> list[OperationsValidationIssue]:
    issues: list[OperationsValidationIssue] = []
    if sequence.fidelity == FidelityLevel.EXECUTABLE and sequence.open_questions:
        for q in sequence.open_questions:
            issues.append(
                OperationsValidationIssue(
                    rule="check_open_questions",
                    severity="question",
                    message=f"unresolved question: {q.text}",
                    step_id=q.related_step_id,
                )
            )
    for step in sequence.steps:
        if sequence.fidelity == FidelityLevel.EXECUTABLE and step.needs_refinement:
            issues.append(
                OperationsValidationIssue(
                    rule="check_open_questions",
                    severity="question",
                    message=f"step '{step.step_id}' still needs refinement for executable fidelity",
                    step_id=step.step_id,
                )
            )
    return issues


def check_schematic_prerequisite(
    sequence: OperationsSequence,
    project: ProjectState,
    _manifests: dict,
    schematic_valid: bool | None = None,
) -> list[OperationsValidationIssue]:
    if schematic_valid is None or schematic_valid:
        return []
    return [
        OperationsValidationIssue(
            rule="check_schematic_prerequisite",
            severity="warning",
            message=(
                "schematic has not passed Logic Checker — operations validation "
                "may reference invalid wiring"
            ),
        )
    ]
