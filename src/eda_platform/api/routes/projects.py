"""Project persistence API routes (schematic + metadata on disk)."""

from fastapi import APIRouter, HTTPException

from eda_platform.api.manifest_loader import load_all_manifests
from eda_platform.api.project_loader import (
    list_project_ids,
    load_project_metadata,
    load_project_state,
    save_project_metadata,
    save_project_state,
)
from eda_platform.api.routes.architect import _draft_to_project_state
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


@router.get("/projects/{project_id}/schematic", response_model=ProjectSchematicResponse)
def get_project_schematic(project_id: str) -> ProjectSchematicResponse:
    schematic = load_project_state(project_id)
    if schematic is None:
        raise HTTPException(
            status_code=404,
            detail=f"no schematic for project '{project_id}'",
        )
    return ProjectSchematicResponse(schematic=schematic)


@router.put("/projects/{project_id}/schematic", response_model=ProjectSchematicResponse)
def put_project_schematic(project_id: str, body: SchematicDraft) -> ProjectSchematicResponse:
    if body.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"project_id mismatch: path={project_id}, body={body.project_id}",
        )
    manifests = load_all_manifests()
    try:
        state = _draft_to_project_state(body, manifests)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    save_project_state(state)
    metadata = load_project_metadata(project_id)
    metadata.schematic_approved = False
    save_project_metadata(metadata)
    return ProjectSchematicResponse(schematic=state)


@router.get("/projects/{project_id}/metadata", response_model=ProjectMetadataResponse)
def get_project_metadata(project_id: str) -> ProjectMetadataResponse:
    return ProjectMetadataResponse(metadata=load_project_metadata(project_id))


@router.put("/projects/{project_id}/metadata", response_model=ProjectMetadataResponse)
def put_project_metadata(
    project_id: str, body: SaveProjectMetadataRequest
) -> ProjectMetadataResponse:
    if body.metadata.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"project_id mismatch: path={project_id}, body={body.metadata.project_id}",
        )
    save_project_metadata(body.metadata)
    return ProjectMetadataResponse(metadata=body.metadata)
