"""C source code generation for Raspberry Pi 4 pthreads firmware."""

from eda_platform.agents.firmware_engineer.codegen.emitter import (
    emit_firmware_tree,
    generate_source_files,
)

__all__ = ["emit_firmware_tree", "generate_source_files"]
