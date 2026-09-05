"""Load ComponentManifest JSON files from the hardware library."""

import logging
from pathlib import Path

from eda_platform.schemas import ComponentManifest

logger = logging.getLogger(__name__)

# Repo root: src/eda_platform/api/manifest_loader.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFESTS_DIR = _REPO_ROOT / "hardware_library" / "manifests"

_cached_catalog: dict[str, ComponentManifest] | None = None
_cached_mtime: float = -1.0


def manifests_directory() -> Path:
    return _MANIFESTS_DIR


def _manifests_dir_mtime() -> float:
    """Latest modification time across catalog JSON files (0 if dir missing/empty)."""
    if not _MANIFESTS_DIR.is_dir():
        return 0.0
    mtimes = [p.stat().st_mtime for p in _MANIFESTS_DIR.glob("*.json")]
    return max(mtimes) if mtimes else 0.0


def clear_manifest_cache() -> None:
    """Invalidate the in-process manifest cache (e.g. in tests)."""
    global _cached_catalog, _cached_mtime
    _cached_catalog = None
    _cached_mtime = -1.0


def load_all_manifests() -> dict[str, ComponentManifest]:
    """Load every *.json manifest from hardware_library/manifests/.

    Invalid files are skipped with a warning so one bad manifest cannot
    take down the entire catalog. Results are cached until the catalog
    directory's newest file mtime changes (so Docker volume edits are
    picked up without a process restart).
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
    for path in sorted(_MANIFESTS_DIR.glob("*.json")):
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
