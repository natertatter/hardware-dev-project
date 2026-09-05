"""Load ComponentManifest JSON files from the hardware library."""

from pathlib import Path

from eda_platform.schemas import ComponentManifest

# Repo root: src/eda_platform/api/manifest_loader.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANIFESTS_DIR = _REPO_ROOT / "hardware_library" / "manifests"


def manifests_directory() -> Path:
    return _MANIFESTS_DIR


def load_all_manifests() -> dict[str, ComponentManifest]:
    """Load every *.json manifest from hardware_library/manifests/."""
    if not _MANIFESTS_DIR.is_dir():
        return {}

    catalog: dict[str, ComponentManifest] = {}
    for path in sorted(_MANIFESTS_DIR.glob("*.json")):
        manifest = ComponentManifest.model_validate_json(path.read_text())
        catalog[manifest.component_id] = manifest
    return catalog


def load_manifest(component_id: str) -> ComponentManifest | None:
    return load_all_manifests().get(component_id)
