"""Per-project metadata (approvals, fidelity stage)."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from eda_platform.schemas.operations_sequence import FidelityLevel


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ProjectMetadata(BaseModel):
    """Tracks approval state and operations fidelity for a project."""

    project_id: str = Field(..., min_length=1)
    schematic_approved: bool = False
    operations_approved: bool = False
    operations_fidelity: FidelityLevel = FidelityLevel.NARRATIVE
    updated_at: str = Field(default_factory=_utc_now_iso)
