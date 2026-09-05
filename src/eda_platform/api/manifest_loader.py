"""Load ComponentManifest JSON files from the hardware library."""

import logging
from functools import lru_cache
from pathlib import Path

from eda_platform.schemas import ComponentManifest

logger = logging.getLogger(__name__)

# Repo root: src/eda_platform/api/manifest_loader.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFESTS_DIR = _REPO_ROOT / "hardware_library" / "manifests"


def manifests_directory() -> Path:
    return _MANIFESTS_DIR


def clear_manifest_cache() -> None:
    """Invalidate the in-process manifest cache (e.g. after catalog edits in dev)."""
    load_all_manifests.cache_clear()


@lru_cache(maxsize=1)
def load_all_manifests() -> dict[str, ComponentManifest]:
    """Load every *.json manifest from hardware_library/manifests/.

    Invalid files are skipped with a warning so one bad manifest cannot
    take down the entire catalog. Results are cached in-process until
    ``clear_manifest_cache()`` is called.
    """
    if not _MANIFESTS_DIR.is_dir():
        return {}

    catalog: dict[str, ComponentManifest] = {}
    for path in sorted(_MANIFESTS_DIR.glob("*.json")):
        try:
            manifest = ComponentManifest.model_validate_json(path.read_text())
        except Exception as exc:
            logger.warning("Skipping invalid manifest %s: %s", path.name, exc)
            continue
        catalog[manifest.component_id] = manifest
    return catalog


def load_manifest(component_id: str) -> ComponentManifest | None:
    return load_all_manifests().get(component_id)
