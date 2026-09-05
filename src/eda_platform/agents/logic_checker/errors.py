"""Structured validation results from the Logic Checker."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ValidationIssue:
    rule: str
    severity: Literal["fatal", "warning"]
    message: str
    net_id: str | None = None
    node_id: str | None = None
    pin_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[ValidationIssue]
