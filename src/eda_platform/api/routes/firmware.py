"""Firmware generation API routes."""

from fastapi import APIRouter, HTTPException

from eda_platform.agents.firmware_engineer import FirmwareEngineerError, generate_firmware
from eda_platform.api.manifest_loader import load_all_manifests
from eda_platform.api.schemas import GenerateFirmwareRequest, GenerateFirmwareResponse

router = APIRouter(prefix="/api/v1", tags=["firmware"])


@router.post("/firmware/generate", response_model=GenerateFirmwareResponse)
def generate_firmware_endpoint(body: GenerateFirmwareRequest) -> GenerateFirmwareResponse:
    if not body.approved:
        raise HTTPException(
            status_code=400,
            detail="Schematic must be approved before generating firmware",
        )

    manifests = body.manifests if body.manifests is not None else load_all_manifests()
    if not manifests:
        raise HTTPException(status_code=500, detail="No manifests loaded on server")

    try:
        result = generate_firmware(
            body.project_state,
            manifests,
            approved=body.approved,
        )
    except FirmwareEngineerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return GenerateFirmwareResponse(
        success=result.success,
        project_id=result.project_id,
        output_dir=result.output_dir,
        files_written=result.files_written,
        message=result.message,
    )
