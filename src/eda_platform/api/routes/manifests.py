"""Component manifest catalog API routes."""

from fastapi import APIRouter, HTTPException

from eda_platform.api.manifest_loader import (
    ExampleManifestInvalid,
    ExampleManifestNotFound,
    ProductionManifestExists,
    clear_manifest_cache,
    list_example_manifests,
    load_all_manifests,
    load_manifest,
    promote_example_manifest,
)
from eda_platform.api.schemas import (
    ExampleManifestListResponse,
    ExampleManifestSummary,
    ManifestListResponse,
    PromoteManifestResponse,
)
from eda_platform.schemas import ComponentManifest

router = APIRouter(prefix="/api/v1", tags=["manifests"])


@router.get("/manifests", response_model=ManifestListResponse)
def list_manifests() -> ManifestListResponse:
    catalog = load_all_manifests()
    return ManifestListResponse(manifests=list(catalog.values()))


@router.get("/manifests/examples", response_model=ExampleManifestListResponse)
def list_manifest_examples() -> ExampleManifestListResponse:
    """List ``*.example.json`` templates. These are not in the production catalog."""
    return ExampleManifestListResponse(
        examples=[
            ExampleManifestSummary(
                component_id=item.component_id,
                name=item.name,
                type=item.component_type,
                promoted=item.promoted,
            )
            for item in list_example_manifests()
        ]
    )


@router.post(
    "/manifests/{component_id}/promote",
    response_model=PromoteManifestResponse,
)
def promote_manifest(component_id: str) -> PromoteManifestResponse:
    """Copy ``{component_id}.example.json`` to a production catalog file."""
    try:
        manifest, path = promote_example_manifest(component_id)
    except ExampleManifestNotFound:
        raise HTTPException(
            status_code=404,
            detail=f"Example manifest '{component_id}' not found",
        ) from None
    except ProductionManifestExists:
        raise HTTPException(
            status_code=409,
            detail=f"Production manifest '{component_id}' already exists",
        ) from None
    except ExampleManifestInvalid as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    clear_manifest_cache()
    return PromoteManifestResponse(
        manifest=manifest,
        saved_path=str(path),
        message=f"Promoted '{component_id}' into the catalog",
    )


@router.get("/manifests/{component_id}", response_model=ComponentManifest)
def get_manifest(component_id: str) -> ComponentManifest:
    manifest = load_manifest(component_id)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Manifest '{component_id}' not found")
    return manifest
