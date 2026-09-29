"""Datasheet ingestion: PDF/JSON upload to ComponentManifest."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from eda_platform.agents.librarian.extract import (
    DatasheetExtraction,
    ExtractionIssue,
    extract_datasheet,
)
from eda_platform.schemas import ComponentManifest
from eda_platform.schemas.protocols import available_protocols, default_protocol

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DATASHEETS_DIR = _REPO_ROOT / "hardware_library" / "datasheets"
_MANIFESTS_DIR = _REPO_ROOT / "hardware_library" / "manifests"


@dataclass
class IngestResult:
    manifest: ComponentManifest
    saved_path: Path
    message: str
    committed: bool
    extraction_source: str
    issues: list[ExtractionIssue]


def _unique_component_id(base: str) -> str:
    if not (_MANIFESTS_DIR / f"{base}.json").exists():
        return base
    counter = 1
    while (_MANIFESTS_DIR / f"{base}_{counter}.json").exists():
        counter += 1
    return f"{base}_{counter}"


def ingest_json_manifest(content: bytes) -> ComponentManifest:
    """Validate and return a ComponentManifest from raw JSON bytes."""
    manifest = ComponentManifest.model_validate_json(content)
    # Ensure protocol profiles are derivable
    if not available_protocols(manifest):
        raise ValueError(
            f"Manifest '{manifest.component_id}' has no recognizable communication protocols"
        )
    return manifest


def save_pdf_datasheet(filename: str, content: bytes) -> Path:
    """Store the uploaded PDF. Does not write a catalog manifest."""
    _DATASHEETS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(filename).name)
    datasheet_path = _DATASHEETS_DIR / safe_name
    datasheet_path.write_bytes(content)
    return datasheet_path


def _with_unique_id(extraction: DatasheetExtraction) -> DatasheetExtraction:
    original = extraction.manifest.component_id
    unique = _unique_component_id(original)
    if unique == original:
        return extraction
    extraction.manifest = extraction.manifest.model_copy(update={"component_id": unique})
    extraction.issues.append(
        ExtractionIssue(
            severity="warning",
            code="component_id_taken",
            message=(
                f"Component id '{original}' is already in the catalog; the draft uses '{unique}'."
            ),
            field="component_id",
        )
    )
    return extraction


def save_manifest(manifest: ComponentManifest) -> Path:
    """Write manifest JSON to hardware_library/manifests/ and return the path."""
    _MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _MANIFESTS_DIR / f"{manifest.component_id}.json"
    path.write_text(manifest.model_dump_json(indent=2))
    return path


def commit_manifest(manifest: ComponentManifest) -> Path:
    """Validate protocols and write a human-approved manifest into the catalog."""
    if not available_protocols(manifest):
        raise ValueError(
            f"Manifest '{manifest.component_id}' has no recognizable communication protocols"
        )
    if (_MANIFESTS_DIR / f"{manifest.component_id}.json").exists():
        raise ValueError(
            f"Component '{manifest.component_id}' already exists in the catalog"
        )
    return save_manifest(manifest)


def ingest_upload(filename: str, content: bytes) -> IngestResult:
    """Route upload by extension: JSON manifests or PDF datasheets.

    JSON is validated and committed. PDF is stored and returned as a draft
    the caller must commit after review.
    """
    lower = filename.lower()
    if lower.endswith(".json"):
        manifest = ingest_json_manifest(content)
        path = commit_manifest(manifest)
        proto = default_protocol(manifest)
        return IngestResult(
            manifest=manifest,
            saved_path=path,
            message=f"Manifest '{manifest.component_id}' added (protocol: {proto})",
            committed=True,
            extraction_source="json",
            issues=[],
        )

    if lower.endswith(".pdf"):
        datasheet_path = save_pdf_datasheet(filename, content)
        extraction = _with_unique_id(extract_datasheet(filename, content))
        return IngestResult(
            manifest=extraction.manifest,
            saved_path=datasheet_path,
            message=extraction.message,
            committed=False,
            extraction_source=extraction.source,
            issues=list(extraction.issues),
        )

    raise ValueError("Unsupported file type — upload a .json manifest or .pdf datasheet")
