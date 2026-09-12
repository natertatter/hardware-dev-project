"""Agent routing, pipeline coordination, and state handoff."""

from enum import Enum

from pathlib import Path

from pydantic import BaseModel, Field

from eda_platform.agents.firmware_engineer import FirmwareEngineerError, generate_firmware
from eda_platform.agents.firmware_engineer.scheduling import plan_from_project
from eda_platform.agents.logic_checker import validate_project_collect
from eda_platform.agents.operations_checker import validate_operations_collect
from eda_platform.agents.operations_checker.errors import OperationsValidationResult
from eda_platform.agents.operations_refiner import refine_operations
from eda_platform.agents.operations_refiner.models import RefineResult
from eda_platform.api.project_loader import (
    load_operations_master,
    load_project_metadata,
    save_operations_master,
    save_operations_refined,
    save_project_metadata,
)
from eda_platform.schemas import ComponentManifest, OperationsSequence, ProjectMetadata, ProjectState


class PipelineStage(str, Enum):
    SCHEMATIC_VALIDATE = "schematic_validate"
    SCHEMATIC_APPROVE = "schematic_approve"
    OPERATIONS_REFINE = "operations_refine"
    OPERATIONS_VALIDATE = "operations_validate"
    OPERATIONS_APPROVE = "operations_approve"
    FIRMWARE_GENERATE = "firmware_generate"


class PipelineResult(BaseModel):
    stage: PipelineStage
    success: bool
    message: str = ""
    refine_result: RefineResult | None = None
    validation_result: OperationsValidationResult | None = None


class PipelineRunResult(BaseModel):
    """End-to-end staged run (Horizon B4)."""

    success: bool
    stages: list[PipelineResult]
    firmware_output_dir: str | None = None
    firmware_files_written: list[str] = Field(default_factory=list)
    message: str = ""


def merge_refined_to_master(
    refined: OperationsSequence,
    *,
    bump_version: bool = True,
) -> OperationsSequence:
    """Promote refined sequence into master, optionally bumping version."""
    master = load_operations_master(refined.project_id)
    new_version = (master.version + 1) if (master and bump_version) else refined.version

    merged = OperationsSequence(
        project_id=refined.project_id,
        fidelity=refined.fidelity,
        version=new_version,
        narrative=refined.narrative or (master.narrative if master else None),
        steps=refined.steps,
        open_questions=refined.open_questions,
    )
    save_operations_master(merged)

    metadata = load_project_metadata(refined.project_id)
    metadata.operations_fidelity = merged.fidelity
    save_project_metadata(metadata)

    return merged


def run_operations_refine(
    sequence: OperationsSequence,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    *,
    persist: bool = True,
) -> PipelineResult:
    result = refine_operations(sequence, project, manifests)
    if persist:
        save_operations_refined(result.refined, version=result.refined.version)
    return PipelineResult(
        stage=PipelineStage.OPERATIONS_REFINE,
        success=True,
        message=(
            f"refined {result.steps_bound} step(s), "
            f"fidelity {result.previous_fidelity.value} → {result.refined.fidelity.value}"
        ),
        refine_result=result,
    )


def run_operations_validate(
    sequence: OperationsSequence,
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
) -> PipelineResult:
    scheduling = None
    try:
        scheduling = plan_from_project(project, manifests)
    except Exception:
        pass

    validation = validate_operations_collect(sequence, project, manifests, scheduling)
    return PipelineResult(
        stage=PipelineStage.OPERATIONS_VALIDATE,
        success=validation.valid,
        message="operations valid" if validation.valid else "operations validation failed",
        validation_result=validation,
    )


def approve_operations_metadata(project_id: str, sequence: OperationsSequence) -> ProjectMetadata:
    """Update metadata after operations approval."""
    metadata = load_project_metadata(project_id)
    metadata.operations_approved = True
    metadata.operations_fidelity = sequence.fidelity
    save_project_metadata(metadata)
    return metadata


def run_staged_pipeline(
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    *,
    operations: OperationsSequence | None = None,
    schematic_approved: bool = True,
    operations_approved: bool = False,
    output_root: Path | None = None,
) -> PipelineRunResult:
    """Validate schematic → operations (optional) → generate firmware."""
    stages: list[PipelineResult] = []

    schematic_validation = validate_project_collect(project, manifests)
    stages.append(
        PipelineResult(
            stage=PipelineStage.SCHEMATIC_VALIDATE,
            success=schematic_validation.valid,
            message="schematic valid" if schematic_validation.valid else "schematic validation failed",
        )
    )
    if not schematic_validation.valid:
        return PipelineRunResult(
            success=False,
            stages=stages,
            message="pipeline stopped at schematic validation",
        )

    if not schematic_approved:
        stages.append(
            PipelineResult(
                stage=PipelineStage.SCHEMATIC_APPROVE,
                success=False,
                message="schematic not approved",
            )
        )
        return PipelineRunResult(success=False, stages=stages, message="schematic approval required")

    if operations is not None:
        ops_result = run_operations_validate(operations, project, manifests)
        stages.append(ops_result)
        if not ops_result.success:
            return PipelineRunResult(
                success=False,
                stages=stages,
                message="pipeline stopped at operations validation",
            )
        if not operations_approved:
            stages.append(
                PipelineResult(
                    stage=PipelineStage.OPERATIONS_APPROVE,
                    success=False,
                    message="operations not approved",
                )
            )
            return PipelineRunResult(
                success=False, stages=stages, message="operations approval required"
            )

    try:
        fw = generate_firmware(
            project,
            manifests,
            approved=True,
            operations=operations,
            operations_approved=operations_approved,
            output_root=output_root,
        )
    except FirmwareEngineerError as exc:
        stages.append(
            PipelineResult(
                stage=PipelineStage.FIRMWARE_GENERATE,
                success=False,
                message=str(exc),
            )
        )
        return PipelineRunResult(success=False, stages=stages, message=str(exc))

    stages.append(
        PipelineResult(
            stage=PipelineStage.FIRMWARE_GENERATE,
            success=True,
            message=fw.message,
        )
    )
    return PipelineRunResult(
        success=True,
        stages=stages,
        firmware_output_dir=fw.output_dir,
        firmware_files_written=fw.files_written,
        message=fw.message,
    )
