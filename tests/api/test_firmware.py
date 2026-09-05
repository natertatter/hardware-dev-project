"""API tests for firmware generation."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eda_platform.api.main import app
from tests.test_logic_checker import _valid_project_state

client = TestClient(app)


def _valid_payload(approved: bool = True) -> dict:
    return {
        "project_state": _valid_project_state().model_dump(),
        "approved": approved,
    }


class TestFirmwareAPI:
    def test_generate_requires_approval(self):
        res = client.post("/api/v1/firmware/generate", json=_valid_payload(approved=False))
        assert res.status_code == 400

    def test_generate_valid_approved_project(self, tmp_path: Path, monkeypatch):
        from eda_platform.agents.firmware_engineer import runner

        monkeypatch.setattr(runner, "_DEFAULT_OUTPUT_ROOT", tmp_path)

        res = client.post("/api/v1/firmware/generate", json=_valid_payload())
        assert res.status_code == 200
        body = res.json()
        assert body["success"] is True
        assert body["project_id"] == "valid_i2c_wiring"
        assert "main.c" in body["files_written"]
        assert (tmp_path / "valid_i2c_wiring" / "main.c").is_file()

    def test_generate_invalid_project_returns_422(self):
        payload = _valid_payload()
        payload["project_state"]["nets"][0]["connections"][0]["pin_id"] = "VBUS"
        res = client.post("/api/v1/firmware/generate", json=payload)
        assert res.status_code == 422
