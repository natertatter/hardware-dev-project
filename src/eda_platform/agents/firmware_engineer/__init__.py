"""Firmware Engineer agent — validated ProjectState to HAL and threaded firmware."""

from eda_platform.agents.firmware_engineer.classifier import classify_nodes
from eda_platform.agents.firmware_engineer.errors import FirmwareEngineerError
from eda_platform.agents.firmware_engineer.models import (
    FirmwareGenerationResult,
    NodeClassification,
    SchedulingPlan,
)
from eda_platform.agents.firmware_engineer.runner import generate_firmware
from eda_platform.agents.firmware_engineer.scheduling import build_scheduling_plan, plan_from_project

__all__ = [
    "FirmwareEngineerError",
    "FirmwareGenerationResult",
    "NodeClassification",
    "SchedulingPlan",
    "build_scheduling_plan",
    "classify_nodes",
    "generate_firmware",
    "plan_from_project",
]
