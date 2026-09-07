"""Pydantic models for operations sequences (behavioral intent alongside ProjectState)."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ExecutionTier = Literal["T0", "T1", "T2", "T3"]


class FidelityLevel(str, Enum):
    """Progressive fidelity for operations sequences."""

    NARRATIVE = "narrative"
    STEPS = "steps"
    TIMED = "timed"
    EXECUTABLE = "executable"


class ProvenanceSource(str, Enum):
    """Where a timing constraint or binding originated."""

    HUMAN = "human"
    DATASHEET = "datasheet"
    BEST_PRACTICE = "best_practice"
    INFERRED = "inferred"


class TimingConstraint(BaseModel):
    """Explicit timing on a step (delay before/after, or periodic execution)."""

    delay_ms: int | None = Field(default=None, ge=0, description="One-shot delay before step")
    period_ms: int | None = Field(default=None, ge=1, description="Repeat interval for polling")
    source: ProvenanceSource = ProvenanceSource.HUMAN
    note: str | None = Field(default=None, description="Human-readable provenance detail")


class OpenQuestion(BaseModel):
    """Unresolved ambiguity surfaced during refinement or validation."""

    question_id: str = Field(..., min_length=1)
    related_step_id: str | None = None
    text: str = Field(..., min_length=1)


class OperationStep(BaseModel):
    """Single step in an operations sequence."""

    step_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    target_node_id: str | None = Field(
        default=None, description="Bound ProjectState node (higher fidelity)"
    )
    hal_call: str | None = Field(
        default=None, description="Semantic HAL operation (executable fidelity)"
    )
    tier: ExecutionTier | None = None
    timing: TimingConstraint | None = None
    condition: str | None = Field(
        default=None, description="Natural-language guard (e.g. estop released)"
    )
    depends_on: list[str] = Field(
        default_factory=list, description="step_ids that must complete first"
    )
    needs_refinement: bool = False
    provenance: ProvenanceSource = ProvenanceSource.HUMAN


class OperationsSequence(BaseModel):
    """Behavioral sequence for a project — light vibe to executable fidelity."""

    project_id: str = Field(..., min_length=1)
    fidelity: FidelityLevel = FidelityLevel.NARRATIVE
    version: int = Field(default=1, ge=1)
    narrative: str | None = Field(
        default=None, description="Free-form vibe capture at narrative fidelity"
    )
    steps: list[OperationStep] = Field(default_factory=list)
    open_questions: list[OpenQuestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def steps_or_narrative_required(self) -> "OperationsSequence":
        if not self.steps and not self.narrative:
            raise ValueError("operations sequence requires at least one step or narrative text")
        return self
