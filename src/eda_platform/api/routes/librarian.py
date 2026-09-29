"""Hardware Librarian API routes — datasheet and manifest upload."""

from dataclasses import asdict

from fastapi import APIRouter, File, HTTPException, UploadFile

from eda_platform.agents.librarian.ingest import commit_manifest, ingest_upload
from eda_platform.api.manifest_loader import clear_manifest_cache
from eda_platform.api.schemas import (
    CommitManifestRequest,
    CommitManifestResponse,
    ExtractionIssueResponse,
    UploadManifestResponse,
)
from eda_platform.schemas.protocols import default_protocol

router = APIRouter(prefix="/api/v1", tags=["librarian"])


@router.post("/librarian/upload", response_model=UploadManifestResponse)
async def upload_datasheet(file: UploadFile = File(...)) -> UploadManifestResponse:
    """Upload a JSON manifest or PDF datasheet.

    JSON files are validated and saved directly. PDF files are stored under
    hardware_library/datasheets/ and returned as a draft manifest. The draft
    is not added to the catalog until POST /librarian/manifests.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        result = ingest_upload(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to process upload: {exc}") from exc

    if result.committed:
        clear_manifest_cache()

    return UploadManifestResponse(
        manifest=result.manifest,
        saved_path=str(result.saved_path),
        message=result.message,
        committed=result.committed,
        extraction_source=result.extraction_source,
        issues=[ExtractionIssueResponse(**asdict(issue)) for issue in result.issues],
    )


@router.post("/librarian/manifests", response_model=CommitManifestResponse)
def commit_librarian_manifest(body: CommitManifestRequest) -> CommitManifestResponse:
    """Save a reviewed ComponentManifest into the hardware catalog."""
    try:
        path = commit_manifest(body.manifest)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clear_manifest_cache()
    proto = default_protocol(body.manifest)
    protocol_note = f" (protocol: {proto})" if proto else ""
    return CommitManifestResponse(
        manifest=body.manifest,
        saved_path=str(path),
        message=f"Manifest '{body.manifest.component_id}' added to catalog{protocol_note}",
    )
