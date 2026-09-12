"""Shared pytest fixtures — isolate disk writes from the repository tree."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_SEED_PROJECT = REPO_ROOT / "projects" / "demo_robot"


@pytest.fixture(scope="session")
def isolated_projects_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("projects")
    if _SEED_PROJECT.is_dir():
        shutil.copytree(_SEED_PROJECT, root / "demo_robot")
    return root


@pytest.fixture(scope="session")
def isolated_datasheets_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("datasheets")
    keep = REPO_ROOT / "hardware_library" / "datasheets" / ".gitkeep"
    if keep.is_file():
        shutil.copy(keep, root / ".gitkeep")
    return root


@pytest.fixture(autouse=True)
def _redirect_project_and_datasheet_dirs(
    isolated_projects_dir: Path,
    isolated_datasheets_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import eda_platform.agents.librarian.ingest as ingest
    import eda_platform.api.project_loader as project_loader

    monkeypatch.setattr(project_loader, "_PROJECTS_DIR", isolated_projects_dir)
    monkeypatch.setattr(ingest, "_DATASHEETS_DIR", isolated_datasheets_dir)
