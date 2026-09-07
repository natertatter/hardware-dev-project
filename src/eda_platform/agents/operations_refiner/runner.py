"""Operations Refiner — promote fidelity and bind steps to schematic + manifests."""

from eda_platform.agents.firmware_engineer.classifier import classify_nodes
from eda_platform.agents.firmware_engineer.scheduling import plan_from_project
from eda_platform.agents.operations_refiner.best_practices import (
    ESTOP_RELEASE_DELAY_MS,
    I2C_SENSOR_POLL_PERIOD_MS,
    MOTOR_DIRECTION_CHANGE_PAUSE_MS,
    MOTOR_RAMP_DELAY_MS,
    POWER_ON_SETTLE_MS,
    is_boot_step,
    is_peripheral_step,
    suggest_hal_call,
)
from eda_platform.agents.operations_refiner.binder import (
    classification_for_node,
    match_node_for_step,
)
from eda_platform.agents.operations_refiner.errors import OperationsRefinerError
from eda_platform.agents.operations_refiner.models import RefineResult, RefineWarning
from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    FidelityLevel,
    OpenQuestion,
    OperationStep,
    OperationsSequence,
    ProvenanceSource,
    ProjectState,
    TimingConstraint,
)

_FIDELITY_ORDER = [
    FidelityLevel.NARRATIVE,
    FidelityLevel.STEPS,
    FidelityLevel.TIMED,
    FidelityLevel.EXECUTABLE,
]


def _next_fidelity(current: FidelityLevel) -> FidelityLevel:
    idx = _FIDELITY_ORDER.index(current)
    if idx >= len(_FIDELITY_ORDER) - 1:
        return current
    return _FIDELITY_ORDER[idx + 1]


def _narrative_to_steps(sequence: OperationsSequence) -> list[OperationStep]:
    """Split narrative text into coarse steps (one per non-empty line or sentence)."""
    if sequence.steps:
        return list(sequence.steps)
    if not sequence.narrative:
        return []

    raw_lines = sequence.narrative.replace(".", ".\n").splitlines()
    steps: list[OperationStep] = []
    for i, line in enumerate(raw_lines):
        text = line.strip()
        if not text:
            continue
        steps.append(
            OperationStep(
                step_id=f"step_{i + 1}",
                description=text,
                provenance=ProvenanceSource.HUMAN,
            )
        )
    return steps


def _timing_for_step(
    step: OperationStep,
    component_type: ComponentType | None,
    poll_period_ms: int,
) -> TimingConstraint | None:
    lower = step.description.lower()
    if "estop" in lower or "e-stop" in lower:
        return TimingConstraint(
            delay_ms=ESTOP_RELEASE_DELAY_MS,
            source=ProvenanceSource.BEST_PRACTICE,
            note="Safety delay after estop release",
        )
    if "pause" in lower or "wait" in lower or "delay" in lower:
        if "motor" in lower or "ramp" in lower:
            return TimingConstraint(
                delay_ms=MOTOR_RAMP_DELAY_MS,
                source=ProvenanceSource.BEST_PRACTICE,
                note="Motor ramp settling time",
            )
        if "direction" in lower:
            return TimingConstraint(
                delay_ms=MOTOR_DIRECTION_CHANGE_PAUSE_MS,
                source=ProvenanceSource.BEST_PRACTICE,
                note="Pause before reversing motor direction",
            )
        return TimingConstraint(
            delay_ms=POWER_ON_SETTLE_MS,
            source=ProvenanceSource.BEST_PRACTICE,
            note="Generic settle delay",
        )
    if is_boot_step(step.description):
        return TimingConstraint(
            delay_ms=POWER_ON_SETTLE_MS,
            source=ProvenanceSource.BEST_PRACTICE,
            note="Power rail settle after enable",
        )
    if component_type == ComponentType.SENSOR and is_peripheral_step(step.description):
        return TimingConstraint(
            period_ms=poll_period_ms,
            source=ProvenanceSource.BEST_PRACTICE,
            note="I2C sensor poll interval (matches scheduling plan default)",
        )
    return None


def refine_operations(
    sequence: OperationsSequence,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
) -> RefineResult:
    """Refine an operations sequence: bind nodes, add timing, promote fidelity."""
    if sequence.project_id != project.project_id:
        raise OperationsRefinerError(
            f"project_id mismatch: sequence={sequence.project_id}, "
            f"project_state={project.project_id}"
        )

    previous_fidelity = sequence.fidelity
    warnings: list[RefineWarning] = []
    open_questions = list(sequence.open_questions)
    steps_bound = 0
    questions_added = 0

    try:
        classifications = classify_nodes(project, manifests)
        scheduling = plan_from_project(project, manifests)
    except Exception as exc:
        raise OperationsRefinerError(f"cannot classify nodes for refinement: {exc}") from exc

    poll_period = I2C_SENSOR_POLL_PERIOD_MS
    for task in scheduling.tasks:
        if "sensor" in task.task_id or "poll" in task.task_id:
            poll_period = task.period_ms
            break

    base_steps = _narrative_to_steps(sequence)
    if not base_steps:
        raise OperationsRefinerError("no steps to refine — provide steps or narrative text")

    refined_steps: list[OperationStep] = []
    target_fidelity = _next_fidelity(previous_fidelity)

    for step in base_steps:
        updated = step.model_copy(deep=True)
        node_id = updated.target_node_id or match_node_for_step(
            updated.description, project, manifests
        )

        if node_id:
            if updated.target_node_id is None:
                steps_bound += 1
            updated.target_node_id = node_id
            updated.needs_refinement = False

            node = next(n for n in project.nodes if n.node_id == node_id)
            manifest = manifests[node.component_id]
            classification = classification_for_node(node_id, classifications)

            if classification:
                updated.tier = classification.tier.value
                hal_call = suggest_hal_call(
                    updated.description, manifest.type, classification.hal_module
                )
                if hal_call:
                    updated.hal_call = hal_call
                    updated.provenance = ProvenanceSource.INFERRED
        else:
            updated.needs_refinement = True
            qid = f"q_bind_{updated.step_id}"
            if not any(q.question_id == qid for q in open_questions):
                open_questions.append(
                    OpenQuestion(
                        question_id=qid,
                        related_step_id=updated.step_id,
                        text=(
                            f"Which node should '{updated.description}' target? "
                            "No confident match in schematic."
                        ),
                    )
                )
                questions_added += 1

        if target_fidelity in (FidelityLevel.TIMED, FidelityLevel.EXECUTABLE):
            manifest = None
            if updated.target_node_id:
                node = next(
                    (n for n in project.nodes if n.node_id == updated.target_node_id), None
                )
                if node:
                    manifest = manifests.get(node.component_id)
            component_type = manifest.type if manifest else None
            if updated.timing is None:
                timing = _timing_for_step(updated, component_type, poll_period)
                if timing:
                    updated.timing = timing

        if target_fidelity == FidelityLevel.EXECUTABLE:
            if updated.target_node_id and updated.hal_call and updated.tier:
                updated.needs_refinement = False
            else:
                updated.needs_refinement = True

        refined_steps.append(updated)

    # Infer boot-order dependencies: peripheral steps depend on earliest boot step.
    boot_ids = [s.step_id for s in refined_steps if is_boot_step(s.description)]
    if boot_ids:
        first_boot = boot_ids[0]
        for step in refined_steps:
            if step.step_id != first_boot and is_peripheral_step(step.description):
                if first_boot not in step.depends_on:
                    step.depends_on = list(step.depends_on) + [first_boot]

    all_bound = all(s.target_node_id for s in refined_steps)
    all_executable = all(
        s.target_node_id and s.hal_call and s.tier and not s.needs_refinement
        for s in refined_steps
    )
    if all_executable and not open_questions:
        target_fidelity = FidelityLevel.EXECUTABLE
    elif all_bound and target_fidelity == FidelityLevel.STEPS:
        target_fidelity = FidelityLevel.TIMED

    refined = OperationsSequence(
        project_id=sequence.project_id,
        fidelity=target_fidelity,
        version=sequence.version,
        narrative=sequence.narrative,
        steps=refined_steps,
        open_questions=open_questions,
    )

    return RefineResult(
        refined=refined,
        fidelity_promoted=target_fidelity != previous_fidelity,
        previous_fidelity=previous_fidelity,
        warnings=warnings,
        steps_bound=steps_bound,
        questions_added=questions_added,
    )
