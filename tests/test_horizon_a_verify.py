"""Smoke-test the Horizon A verification helpers."""

import importlib.util
import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "horizon_a_verify",
    REPO_ROOT / "scripts" / "horizon_a_verify.py",
)
_ha = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_ha)

VerifyError = _ha.VerifyError
verify_pipeline = _ha.verify_pipeline
verify_project_api = _ha.verify_project_api


def test_horizon_a_verify_project_api():
    verify_project_api()


def test_horizon_a_verify_pipeline_write_firmware(tmp_path: Path):
    compiled = verify_pipeline(True, tmp_path, require_toolchain=shutil.which("gcc") is not None)
    if shutil.which("gcc") and shutil.which("make"):
        assert compiled is True
    else:
        assert compiled is False


def test_horizon_a_verify_requires_toolchain(tmp_path: Path):
    if shutil.which("gcc") and shutil.which("make"):
        pytest.skip("toolchain present")
    with pytest.raises(VerifyError, match="gcc/make required"):
        verify_pipeline(True, tmp_path, require_toolchain=True)
