"""Operations sequence API routes."""

from fastapi import APIRouter, HTTPException

from eda_platform.agents.operations_docs import (
    generate_bringup_checklist,
    generate_operating_procedure,
)
from eda_platform.api.manifest_loader import load_all_manifests
from eda_platform.api.project_loader import (
    load_operations_master,
    save_operations_draft,
    save_operations_master,
)
from eda_platform.agents.operations_refiner import OperationsRefinerError
from eda_platform.api.schemas import (
    GenerateOperatingDocsRequest,
    GenerateOperatingDocsResponse,
    MergeOperationsRequest,
    MergeOperationsResponse,
    OperationsValidationIssueResponse,
    RefineOperationsRequest,
    RefineOperationsResponse,
    SaveOperationsDraftRequest,
    SaveOperationsDraftResponse,
    ValidateOperationsRequest,
    ValidateOperationsResponse,
)
from eda_platform.orchestration import (
    approve_operations_metadata,
    merge_refined_to_master,
    run_operations_refine,
    run_operations_validate,
)
from eda_platform.schemas import OperationsSequence

router = APIRouter(prefix="/api/v1", tags=["operations"])


def _resolve_manifests(body_manifests):
    return body_manifests if body_manifests is not None else load_all_manifests()


@router.get("/projects/{project_id}/operations/master")
def get_operations_master(project_id: str) -> OperationsSequence:
    master = load_operations_master(project_id)
    if master is None:
        raise HTTPException(status_code=404, detail=f"no operations master for '{project_id}'")
    return master


@router.put("/projects/{project_id}/operations/master")
def put_operations_master(project_id: str, body: OperationsSequence) -> OperationsSequence:
    if body.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=f"project_id mismatch: path={project_id}, body={body.project_id}",
        )
    save_operations_master(body)
    return body


@router.post("/projects/{project_id}/operations/drafts", response_model=SaveOperationsDraftResponse)
def post_operations_draft(
    project_id: str, body: SaveOperationsDraftRequest
) -> SaveOperationsDraftResponse:
    if body.operations.project_id != project_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"project_id mismatch: path={project_id}, "
                f"body={body.operations.project_id}"
            ),
        )
    path = save_operations_draft(body.operations)
    return SaveOperationsDraftResponse(saved_path=str(path))


@router.post("/operations/refine", response_model=RefineOperationsResponse)
def refine_operations_endpoint(body: RefineOperationsRequest) -> RefineOperationsResponse:
    manifests = _resolve_manifests(body.manifests)
    if not manifests:
        raise HTTPException(status_code=422, detail="no component manifests available")

    try:
        result = run_operations_refine(
            body.operations,
            body.project_state,
            manifests,
            persist=body.persist,
        )
    except OperationsRefinerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    refine = result.refine_result
    assert refine is not None
    return RefineOperationsResponse(
        refined=refine.refined,
        fidelity_promoted=refine.fidelity_promoted,
        previous_fidelity=refine.previous_fidelity.value,
        steps_bound=refine.steps_bound,
        questions_added=refine.questions_added,
        warnings=[w.message for w in refine.warnings],
    )


@router.post("/operations/validate", response_model=ValidateOperationsResponse)
def validate_operations_endpoint(body: ValidateOperationsRequest) -> ValidateOperationsResponse:
    manifests = _resolve_manifests(body.manifests)
    if not manifests:
        return ValidateOperationsResponse(
            valid=False,
            errors=[
                OperationsValidationIssueResponse(
                    rule="manifest_loader",
                    severity="fatal",
                    message="No component manifests available on server",
                )
            ],
        )

    result = run_operations_validate(body.operations, body.project_state, manifests)
    validation = result.validation_result
    assert validation is not None
    return ValidateOperationsResponse(
        valid=validation.valid,
        errors=[
            OperationsValidationIssueResponse(
                rule=e.rule,
                severity=e.severity,
                message=e.message,
                step_id=e.step_id,
                node_id=e.node_id,
            )
            for e in validation.errors
        ],
    )


@router.post("/operations/generate-docs", response_model=GenerateOperatingDocsResponse)
def generate_operating_docs_endpoint(
    body: GenerateOperatingDocsRequest,
) -> GenerateOperatingDocsResponse:
    return GenerateOperatingDocsResponse(
        operating_procedure=generate_operating_procedure(body.operations, body.project_state),
        bringup_checklist=generate_bringup_checklist(body.operations, body.project_state),
    )


@router.post("/operations/merge", response_model=MergeOperationsResponse)
def merge_operations_endpoint(body: MergeOperationsRequest) -> MergeOperationsResponse:
    schematic = body.project_state or _load_schematic_or_400(body.operations.project_id)
    validation = run_operations_validate(body.operations, schematic, load_all_manifests())
    if not validation.success:
        raise HTTPException(
            status_code=422,
            detail="cannot merge — operations validation failed",
        )

    master = merge_refined_to_master(body.operations, bump_version=body.bump_version)
    return MergeOperationsResponse(
        master=master,
        message=f"merged to master v{master.version} at fidelity {master.fidelity.value}",
    )


@router.post("/projects/{project_id}/operations/approve")
def approve_operations_endpoint(project_id: str) -> dict:
    master = load_operations_master(project_id)
    if master is None:
        raise HTTPException(status_code=404, detail=f"no operations master for '{project_id}'")

    from eda_platform.api.project_loader import load_project_state

    schematic = load_project_state(project_id)
    if schematic is None:
        raise HTTPException(status_code=422, detail="schematic required before operations approval")

    result = run_operations_validate(master, schematic, load_all_manifests())
    if not result.success:
        raise HTTPException(status_code=422, detail="operations must pass validation before approval")

    metadata = approve_operations_metadata(project_id, master)
    return {
        "project_id": project_id,
        "operations_approved": metadata.operations_approved,
        "operations_fidelity": metadata.operations_fidelity.value,
    }


def _load_schematic_or_400(project_id: str):
    from eda_platform.api.project_loader import load_project_state

    schematic = load_project_state(project_id)
    if schematic is None:
        raise HTTPException(
            status_code=422,
            detail=f"schematic required for project '{project_id}' — save schematic.json first",
        )
    return schematic
