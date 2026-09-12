"""Load and persist per-project artifacts (schematic, operations, metadata)."""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from eda_platform.api.schemas import SchematicDraft
from eda_platform.api.schematic_file import strip_draft_nets
from eda_platform.schemas import (
    OperationsSequence,
    ProjectMetadata,
    ProjectState,
)

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PROJECTS_DIR = _REPO_ROOT / "projects"

PROJECT_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


def validate_project_id(project_id: str) -> str:
    if not project_id or not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError("invalid project_id")
    return project_id


def projects_directory() -> Path:
    return _PROJECTS_DIR


def project_directory(project_id: str) -> Path:
    safe_id = validate_project_id(project_id)
    return _PROJECTS_DIR / safe_id


def operations_directory(project_id: str) -> Path:
    return project_directory(project_id) / "operations"


def _ensure_project_dirs(project_id: str) -> Path:
    ops_dir = operations_directory(project_id)
    ops_dir.mkdir(parents=True, exist_ok=True)
    (ops_dir / "drafts").mkdir(exist_ok=True)
    (ops_dir / "refined").mkdir(exist_ok=True)
    return ops_dir


def load_schematic_draft(project_id: str) -> SchematicDraft | None:
    """Load schematic.json as a draft (nets may be empty)."""
    path = project_directory(project_id) / "schematic.json"
    if not path.is_file():
        return None
    draft = SchematicDraft.model_validate_json(path.read_text())
    return strip_draft_nets(draft)


def load_project_state(project_id: str) -> ProjectState | None:
    """Load a wired schematic as ProjectState, or None if missing or placement-only."""
    draft = load_schematic_draft(project_id)
    if draft is None or not draft.nets:
        return None
    return ProjectState(
        project_id=draft.project_id,
        nodes=draft.nodes,
        nets=draft.nets,
    )


def save_schematic_draft(draft: SchematicDraft) -> Path:
    """Persist schematic.json (placement-only drafts keep nets: [])."""
    clean = strip_draft_nets(draft)
    proj_dir = project_directory(clean.project_id)
    proj_dir.mkdir(parents=True, exist_ok=True)
    path = proj_dir / "schematic.json"
    path.write_text(clean.model_dump_json(indent=2))
    return path


def save_project_state(project: ProjectState) -> Path:
    """Persist a fully wired ProjectState as schematic.json."""
    return save_schematic_draft(
        SchematicDraft(
            project_id=project.project_id,
            nodes=project.nodes,
            nets=project.nets,
        )
    )


def load_project_metadata(project_id: str) -> ProjectMetadata:
    """Load metadata.json or return defaults for a new project."""
    path = project_directory(project_id) / "metadata.json"
    if path.is_file():
        return ProjectMetadata.model_validate_json(path.read_text())
    return ProjectMetadata(project_id=project_id)


def save_project_metadata(metadata: ProjectMetadata) -> Path:
    """Persist project metadata with updated timestamp."""
    proj_dir = project_directory(metadata.project_id)
    proj_dir.mkdir(parents=True, exist_ok=True)
    metadata.updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path = proj_dir / "metadata.json"
    path.write_text(metadata.model_dump_json(indent=2))
    return path


def load_operations_master(project_id: str) -> OperationsSequence | None:
    """Load operations/master.json for a project."""
    path = operations_directory(project_id) / "master.json"
    if not path.is_file():
        return None
    return OperationsSequence.model_validate_json(path.read_text())


def save_operations_master(sequence: OperationsSequence) -> Path:
    """Persist canonical operations sequence."""
    _ensure_project_dirs(sequence.project_id)
    path = operations_directory(sequence.project_id) / "master.json"
    path.write_text(sequence.model_dump_json(indent=2))
    return path


def save_operations_draft(sequence: OperationsSequence) -> Path:
    """Append a timestamped draft under operations/drafts/."""
    _ensure_project_dirs(sequence.project_id)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = operations_directory(sequence.project_id) / "drafts" / f"draft_{ts}.json"
    path.write_text(sequence.model_dump_json(indent=2))
    return path


def save_operations_refined(sequence: OperationsSequence, version: int | None = None) -> Path:
    """Persist refined output under operations/refined/."""
    _ensure_project_dirs(sequence.project_id)
    ver = version if version is not None else sequence.version
    path = operations_directory(sequence.project_id) / "refined" / f"refined_v{ver}.json"
    path.write_text(sequence.model_dump_json(indent=2))
    return path


def list_operations_drafts(project_id: str) -> list[Path]:
    drafts_dir = operations_directory(project_id) / "drafts"
    if not drafts_dir.is_dir():
        return []
    return sorted(drafts_dir.glob("draft_*.json"))


def list_operations_refined(project_id: str) -> list[Path]:
    refined_dir = operations_directory(project_id) / "refined"
    if not refined_dir.is_dir():
        return []
    return sorted(refined_dir.glob("refined_v*.json"))


def list_project_ids() -> list[str]:
    """Return sorted project ids that have a schematic.json on disk."""
    if not _PROJECTS_DIR.is_dir():
        return []
    ids: list[str] = []
    for child in sorted(_PROJECTS_DIR.iterdir()):
        if child.is_dir() and (child / "schematic.json").is_file():
            ids.append(child.name)
    return ids
