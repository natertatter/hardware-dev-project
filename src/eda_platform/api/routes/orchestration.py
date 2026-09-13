"""Staged pipeline API (Horizon B4)."""

from fastapi import APIRouter, HTTPException

from eda_platform.api.manifest_loader import load_all_manifests
from eda_platform.api.schemas import PipelineRunRequest, PipelineRunResponse, PipelineStageResult
from eda_platform.orchestration.pipeline import run_staged_pipeline

router = APIRouter(prefix="/api/v1", tags=["orchestration"])


@router.post("/pipeline/run", response_model=PipelineRunResponse)
def run_pipeline(body: PipelineRunRequest) -> PipelineRunResponse:
    manifests = body.manifests if body.manifests is not None else load_all_manifests()
    if not manifests:
        raise HTTPException(status_code=422, detail="no component manifests available")

    result = run_staged_pipeline(
        body.project_state,
        manifests,
        operations=body.operations,
        schematic_approved=body.schematic_approved,
        operations_approved=body.operations_approved,
    )

    return PipelineRunResponse(
        success=result.success,
        message=result.message,
        firmware_output_dir=result.firmware_output_dir,
        firmware_files_written=result.firmware_files_written,
        stages=[
            PipelineStageResult(
                stage=s.stage.value,
                success=s.success,
                message=s.message,
            )
            for s in result.stages
        ],
    )
