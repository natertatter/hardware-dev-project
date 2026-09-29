"""Load ComponentManifest JSON files from the hardware library.

Production catalog files are ``{component_id}.json``. Files named
``{component_id}.example.json`` are templates and are not loaded until
``promote_example_manifest`` copies one into the production name.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from eda_platform.schemas import ComponentManifest

logger = logging.getLogger(__name__)

_EXAMPLE_SUFFIX = ".example.json"

# Repo root: src/eda_platform/api/manifest_loader.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFESTS_DIR = _REPO_ROOT / "hardware_library" / "manifests"

_cached_catalog: dict[str, ComponentManifest] | None = None
_cached_mtime: float = -1.0


class ExampleManifestNotFound(Exception):
    """No ``{component_id}.example.json`` template exists."""


class ExampleManifestInvalid(Exception):
    """An example file is not a valid manifest or its id does not match the filename."""


class ProductionManifestExists(Exception):
    """A production ``{component_id}.json`` file is already in the catalog."""


@dataclass(frozen=True)
class ExampleManifestInfo:
    component_id: str
    name: str
    component_type: str
    promoted: bool


def manifests_directory() -> Path:
    return _MANIFESTS_DIR


def _is_example_manifest(path: Path) -> bool:
    return path.name.endswith(_EXAMPLE_SUFFIX)


def _example_component_id(path: Path) -> str | None:
    if not _is_example_manifest(path):
        return None
    return path.name[: -len(_EXAMPLE_SUFFIX)]


def _production_manifest_paths() -> list[Path]:
    if not _MANIFESTS_DIR.is_dir():
        return []
    return sorted(
        path
        for path in _MANIFESTS_DIR.glob("*.json")
        if path.is_file() and not _is_example_manifest(path)
    )


def _manifests_dir_mtime() -> float:
    """Latest modification time across production catalog files (0 if none)."""
    mtimes = [path.stat().st_mtime for path in _production_manifest_paths()]
    return max(mtimes) if mtimes else 0.0


def clear_manifest_cache() -> None:
    """Invalidate the in-process manifest cache (e.g. in tests)."""
    global _cached_catalog, _cached_mtime
    _cached_catalog = None
    _cached_mtime = -1.0


def load_all_manifests() -> dict[str, ComponentManifest]:
    """Load every production ``*.json`` manifest from hardware_library/manifests/.

    ``*.example.json`` templates are skipped. Invalid files are skipped with
    a warning so one bad manifest cannot take down the entire catalog.
    Results are cached until the newest production file mtime changes (so
    Docker volume edits are picked up without a process restart).
    """
    global _cached_catalog, _cached_mtime

    current_mtime = _manifests_dir_mtime()
    if _cached_catalog is not None and current_mtime == _cached_mtime:
        return _cached_catalog

    if not _MANIFESTS_DIR.is_dir():
        _cached_catalog = {}
        _cached_mtime = current_mtime
        return _cached_catalog

    catalog: dict[str, ComponentManifest] = {}
    for path in _production_manifest_paths():
        try:
            manifest = ComponentManifest.model_validate_json(path.read_text())
        except Exception as exc:
            logger.warning("Skipping invalid manifest %s: %s", path.name, exc)
            continue
        catalog[manifest.component_id] = manifest

    _cached_catalog = catalog
    _cached_mtime = current_mtime
    return _cached_catalog


def load_manifest(component_id: str) -> ComponentManifest | None:
    return load_all_manifests().get(component_id)


def list_example_manifests() -> list[ExampleManifestInfo]:
    """List template manifests and whether each already has a production file."""
    if not _MANIFESTS_DIR.is_dir():
        return []

    found: list[ExampleManifestInfo] = []
    for path in sorted(_MANIFESTS_DIR.glob(f"*{_EXAMPLE_SUFFIX}")):
        component_id = _example_component_id(path)
        if not component_id:
            continue
        try:
            manifest = ComponentManifest.model_validate_json(path.read_text())
        except Exception as exc:
            logger.warning("Skipping invalid example manifest %s: %s", path.name, exc)
            continue
        if manifest.component_id != component_id:
            logger.warning(
                "Skipping example %s: component_id is %s",
                path.name,
                manifest.component_id,
            )
            continue
        found.append(
            ExampleManifestInfo(
                component_id=component_id,
                name=manifest.name,
                component_type=manifest.type.value,
                promoted=(_MANIFESTS_DIR / f"{component_id}.json").is_file(),
            )
        )
    return found


def promote_example_manifest(component_id: str) -> tuple[ComponentManifest, Path]:
    """Copy a validated example template to ``{component_id}.json``.

    Does not overwrite an existing production file.
    """
    example = _MANIFESTS_DIR / f"{component_id}{_EXAMPLE_SUFFIX}"
    if not example.is_file():
        raise ExampleManifestNotFound(component_id)

    try:
        manifest = ComponentManifest.model_validate_json(example.read_text())
    except Exception as exc:
        raise ExampleManifestInvalid(
            f"Example '{component_id}' is not a valid manifest: {exc}"
        ) from exc

    if manifest.component_id != component_id:
        raise ExampleManifestInvalid(
            f"Example file '{example.name}' declares component_id '{manifest.component_id}'"
        )

    destination = _MANIFESTS_DIR / f"{component_id}.json"
    if destination.exists():
        raise ProductionManifestExists(component_id)

    destination.write_bytes(example.read_bytes())
    return manifest, destination
