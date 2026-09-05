"""Component manifest catalog API routes."""

from fastapi import APIRouter, HTTPException

from eda_platform.api.manifest_loader import load_all_manifests, load_manifest
from eda_platform.api.schemas import ManifestListResponse
from eda_platform.schemas import ComponentManifest

router = APIRouter(prefix="/api/v1", tags=["manifests"])


@router.get("/manifests", response_model=ManifestListResponse)
def list_manifests() -> ManifestListResponse:
    catalog = load_all_manifests()
    return ManifestListResponse(manifests=list(catalog.values()))


@router.get("/manifests/{component_id}", response_model=ComponentManifest)
def get_manifest(component_id: str) -> ComponentManifest:
    manifest = load_manifest(component_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Manifest '{component_id}' not found")
    return manifest
