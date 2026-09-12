"""Project persistence API routes (schematic + metadata on disk)."""

from fastapi import APIRouter, Depends, HTTPException

from eda_platform.api.deps import project_id_path
from eda_platform.api.project_loader import (
    list_project_ids,
    load_project_metadata,
    load_schematic_draft,
    save_project_metadata,
    save_schematic_draft,
)
from eda_platform.api.schematic_file import draft_content_key, strip_draft_nets
from eda_platform.api.schemas import (
    ProjectListResponse,
    ProjectMetadataResponse,
    ProjectSchematicResponse,
    SaveProjectMetadataRequest,
    SchematicDraft,
)

router = APIRouter(prefix="/api/v1", tags=["projects"])


@router.get("/projects", response_model=ProjectListResponse)
def list_projects() -> ProjectListResponse:
    return ProjectListResponse(project_ids=list_project_ids())


@router.get(
    "/projects/{project_id}/schematic",
    response_model=ProjectSchematicResponse,
)
def get_project_schematic(
    project_id: str = Depends(project_id_path),
) -> ProjectSchematicResponse:
    schematic = load_schematic_draft(project_id)
    if schematic is None:
        raise HTTPException(
            status_code=404,
            detail=f"no schematic for project '{project_id}'",
        )
    return ProjectSchematicResponse(schematic=schematic)


@router.put(
    "/projects/{project_id}/schematic",
    response_model=ProjectSchematicResponse,
)
def put_project_schematic(
    body: SchematicDraft,
    project_id: str = Depends(project_id_path),
) -> ProjectSchematicResponse:
    if body.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"project_id mismatch: path={project_id}, body={body.project_id}",
        )
    incoming = strip_draft_nets(body)
    existing = load_schematic_draft(project_id)
    changed = existing is None or draft_content_key(incoming) != draft_content_key(existing)

    save_schematic_draft(incoming)

    if changed:
        metadata = load_project_metadata(project_id)
        metadata.schematic_approved = False
        metadata.operations_approved = False
        save_project_metadata(metadata)

    return ProjectSchematicResponse(schematic=incoming)


@router.get(
    "/projects/{project_id}/metadata",
    response_model=ProjectMetadataResponse,
)
def get_project_metadata(
    project_id: str = Depends(project_id_path),
) -> ProjectMetadataResponse:
    return ProjectMetadataResponse(metadata=load_project_metadata(project_id))


@router.put(
    "/projects/{project_id}/metadata",
    response_model=ProjectMetadataResponse,
)
def put_project_metadata(
    body: SaveProjectMetadataRequest,
    project_id: str = Depends(project_id_path),
) -> ProjectMetadataResponse:
    if body.metadata.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"project_id mismatch: path={project_id}, body={body.metadata.project_id}",
        )
    save_project_metadata(body.metadata)
    return ProjectMetadataResponse(metadata=body.metadata)
