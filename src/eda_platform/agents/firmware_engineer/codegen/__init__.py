"""C source code generation for Raspberry Pi 4 pthreads firmware."""

from eda_platform.agents.firmware_engineer.codegen.emitter import emit_firmware_tree
from eda_platform.agents.firmware_engineer.models import SchedulingPlan
from eda_platform.schemas import ComponentManifest, ProjectState

__all__ = ["emit_firmware_tree", "generate_source_files"]
