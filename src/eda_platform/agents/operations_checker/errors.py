"""Structured validation results from the Operations Checker."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class OperationsValidationIssue:
    rule: str
    severity: Literal["fatal", "warning", "question"]
    message: str
    step_id: str | None = None
    node_id: str | None = None


@dataclass(frozen=True)
class OperationsValidationResult:
    valid: bool
    errors: list[OperationsValidationIssue]
