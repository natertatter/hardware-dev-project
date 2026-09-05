"""Validation API routes."""

from fastapi import APIRouter

from eda_platform.agents.logic_checker import validate_project_collect
from eda_platform.api.manifest_loader import load_all_manifests
from eda_platform.api.schemas import (
    ValidateRequest,
    ValidateResponse,
    ValidationIssueResponse,
)

router = APIRouter(prefix="/api/v1", tags=["validation"])


@router.post("/validate", response_model=ValidateResponse)
def validate_schematic(body: ValidateRequest) -> ValidateResponse:
    manifests = body.manifests if body.manifests is not None else load_all_manifests()
    if not manifests:
        return ValidateResponse(
            valid=False,
            errors=[
                ValidationIssueResponse(
                    rule="manifest_loader",
                    severity="fatal",
                    message="No component manifests available on server",
                )
            ],
        )

    result = validate_project_collect(body.project_state, manifests)
    return ValidateResponse(
        valid=result.valid,
        errors=[
            ValidationIssueResponse(
                rule=e.rule,
                severity=e.severity,
                message=e.message,
                net_id=e.net_id,
                node_id=e.node_id,
                pin_id=e.pin_id,
            )
            for e in result.errors
        ],
    )
