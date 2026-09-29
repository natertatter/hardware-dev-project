"""Tests for datasheet/manifest upload ingestion."""

import json

import pytest

from eda_platform.agents.librarian.ingest import ingest_json_manifest, ingest_upload
from eda_platform.api.manifest_loader import clear_manifest_cache, manifests_directory


@pytest.fixture(autouse=True)
def _cleanup_test_manifests():
    yield
    manifests_dir = manifests_directory()
    for path in manifests_dir.glob("test_upload_*.json"):
        path.unlink(missing_ok=True)
    clear_manifest_cache()


def test_ingest_json_manifest_validates():
    raw = {
        "component_id": "test_upload_sensor",
        "name": "Test Upload Sensor",
        "type": "SENSOR",
        "power_requirements": {
            "min_operating_voltage": 3.0,
            "max_operating_voltage": 3.6,
            "logic_level_voltage": 3.3,
            "max_current_draw_ma": 1.0,
        },
        "pins": [
            {"pin_id": "VCC", "pin_type": "POWER"},
            {"pin_id": "GND", "pin_type": "GND"},
            {"pin_id": "SDA", "pin_type": "I2C_SDA", "supported_features": ["I2C"]},
            {"pin_id": "SCL", "pin_type": "I2C_SCL", "supported_features": ["I2C"]},
        ],
    }
    manifest = ingest_json_manifest(json.dumps(raw).encode())
    assert manifest.component_id == "test_upload_sensor"


def test_ingest_upload_json_saves_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "eda_platform.agents.librarian.ingest._MANIFESTS_DIR",
        tmp_path,
    )
    raw = {
        "component_id": "test_upload_json",
        "name": "JSON Upload",
        "type": "SENSOR",
        "power_requirements": {
            "min_operating_voltage": 3.0,
            "max_operating_voltage": 3.6,
            "logic_level_voltage": 3.3,
            "max_current_draw_ma": 1.0,
        },
        "pins": [
            {"pin_id": "VCC", "pin_type": "POWER"},
            {"pin_id": "GND", "pin_type": "GND"},
            {"pin_id": "SDA", "pin_type": "I2C_SDA", "supported_features": ["I2C"]},
            {"pin_id": "SCL", "pin_type": "I2C_SCL", "supported_features": ["I2C"]},
        ],
    }
    result = ingest_upload("sensor.json", json.dumps(raw).encode())
    assert result.committed is True
    assert result.extraction_source == "json"
    assert result.manifest.component_id == "test_upload_json"
    assert result.saved_path.exists()
    assert "added" in result.message.lower() or "test_upload_json" in result.message
    result.saved_path.unlink(missing_ok=True)


def test_ingest_upload_pdf_without_text_stays_a_draft(tmp_path, monkeypatch):
    monkeypatch.setattr("eda_platform.agents.librarian.ingest._MANIFESTS_DIR", tmp_path)
    result = ingest_upload("bme280_datasheet.pdf", b"%PDF-1.4 fake")
    assert result.committed is False
    assert result.extraction_source == "template"
    assert result.manifest.type.value == "SENSOR"
    assert "I2C" in (result.manifest.protocol_profiles or {})
    assert result.saved_path.suffix == ".pdf"
    assert result.saved_path.exists()
    assert list(tmp_path.glob("*.json")) == []
    assert any(issue.code == "template_fallback" for issue in result.issues)
