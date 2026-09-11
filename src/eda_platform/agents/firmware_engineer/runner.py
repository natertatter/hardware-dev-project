"""Firmware generation orchestration."""

from pathlib import Path

from eda_platform.agents.firmware_engineer.codegen.emitter import emit_firmware_tree
from eda_platform.agents.firmware_engineer.errors import FirmwareEngineerError
from eda_platform.agents.firmware_engineer.models import FirmwareGenerationResult
from eda_platform.agents.firmware_engineer.scheduling import plan_from_project
from eda_platform.agents.logic_checker import validate_project_collect
from eda_platform.agents.operations_docs import emit_operating_docs
from eda_platform.schemas import ComponentManifest, OperationsSequence, ProjectState

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_OUTPUT_ROOT = _REPO_ROOT / "generated" / "firmware"


def generate_firmware(
    project: ProjectState,
    manifests: dict[str, ComponentManifest],
    *,
    approved: bool,
    operations: OperationsSequence | None = None,
    operations_approved: bool = False,
    output_root: Path | None = None,
) -> FirmwareGenerationResult:
    """Validate, classify, schedule, and emit pthreads C firmware for Raspberry Pi 4."""
    if not approved:
        raise FirmwareEngineerError(
            "schematic not approved — approve the schematic before generating firmware"
        )

    if operations is not None and not operations_approved:
        raise FirmwareEngineerError(
            "operations not approved — approve the operations sequence before generating firmware"
        )

    validation = validate_project_collect(project, manifests)
    if not validation.valid:
        issues = "; ".join(e.message for e in validation.errors[:3])
        raise FirmwareEngineerError(f"validation failed: {issues}")

    plan = plan_from_project(project, manifests)
    out_root = output_root or _DEFAULT_OUTPUT_ROOT
    output_dir = out_root / project.project_id

    files_written = emit_firmware_tree(
        output_dir, project, manifests, plan, operations=operations
    )

    if operations is not None:
        doc_files = emit_operating_docs(output_dir, operations, project)
        files_written.extend(doc_files)

    try:
        rel_output = str(output_dir.relative_to(_REPO_ROOT))
    except ValueError:
        rel_output = str(output_dir)

    return FirmwareGenerationResult(
        success=True,
        project_id=project.project_id,
        output_dir=rel_output,
        files_written=files_written,
        scheduling_plan=plan,
        message=f"Generated {len(files_written)} files for Raspberry Pi 4",
    )
