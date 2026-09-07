"""Hardware Librarian API routes — datasheet and manifest upload."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from eda_platform.agents.librarian.ingest import ingest_upload
from eda_platform.api.manifest_loader import clear_manifest_cache
from eda_platform.api.schemas import UploadManifestResponse
from eda_platform.schemas import ComponentManifest

router = APIRouter(prefix="/api/v1", tags=["librarian"])


@router.post("/librarian/upload", response_model=UploadManifestResponse)
async def upload_datasheet(file: UploadFile = File(...)) -> UploadManifestResponse:
    """Upload a JSON manifest or PDF datasheet to add a component to the catalog.

    JSON files are validated and saved directly. PDF files are stored under
    hardware_library/datasheets/ and a multi-protocol template manifest is
    generated for placement on the schematic canvas.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        manifest, saved_path, message = ingest_upload(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to process upload: {exc}") from exc

    clear_manifest_cache()

    return UploadManifestResponse(
        manifest=manifest,
        saved_path=str(saved_path),
        message=message or f"Component '{manifest.component_id}' added to catalog",
    )
