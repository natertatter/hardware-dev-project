"""Structured models for operations refinement."""

from pydantic import BaseModel, Field

from eda_platform.schemas import FidelityLevel, OperationsSequence


class RefineWarning(BaseModel):
    step_id: str | None = None
    message: str


class RefineResult(BaseModel):
    refined: OperationsSequence
    fidelity_promoted: bool = False
    previous_fidelity: FidelityLevel
    warnings: list[RefineWarning] = Field(default_factory=list)
    steps_bound: int = 0
    questions_added: int = 0
