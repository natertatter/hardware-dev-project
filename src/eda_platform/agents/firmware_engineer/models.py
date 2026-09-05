"""Structured models for firmware generation."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ExecutionTier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class NodeClassification(BaseModel):
    node_id: str
    component_id: str
    tier: ExecutionTier
    hal_module: str


class BusLock(BaseModel):
    bus_id: str
    i2c_device_path: str
    nodes: list[str] = Field(..., min_length=1)


class TaskSpec(BaseModel):
    task_id: str
    tier: ExecutionTier
    priority: int
    period_ms: int
    nodes: list[str] = Field(..., min_length=1)
    hal_modules: list[str] = Field(..., min_length=1)


class SchedulingPlan(BaseModel):
    project_id: str
    platform: str = "rpi4"
    tasks: list[TaskSpec] = Field(default_factory=list)
    bus_locks: list[BusLock] = Field(default_factory=list)
    classifications: list[NodeClassification] = Field(default_factory=list)


class FirmwareGenerationResult(BaseModel):
    success: bool
    project_id: str
    output_dir: str
    files_written: list[str] = Field(default_factory=list)
    scheduling_plan: SchedulingPlan | None = None
    message: str = ""
