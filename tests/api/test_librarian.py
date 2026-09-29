"""Tests for librarian upload API."""

import json

import pytest
from fastapi.testclient import TestClient

from eda_platform.api.main import app
from eda_platform.api.manifest_loader import clear_manifest_cache, manifests_directory

client = TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup():
    yield
    for path in manifests_directory().glob("test_api_upload_*.json"):
        path.unlink(missing_ok=True)
    clear_manifest_cache()


def _labeled_pdf() -> bytes:
    lines = [
        "Name: API Extract Sensor",
        "Type: SENSOR",
        "Component ID: test_api_extract_sensor",
        "Min Operating Voltage: 1.8 V",
        "Max Operating Voltage: 3.3 V",
        "Logic Level Voltage: 3.3 V",
        "Max Current: 1.0 mA",
        "I2C Address: 0x48",
        "Power-on Delay: 4 ms",
        "Pins:",
        "VCC POWER",
        "GND GND",
        "SDA I2C_SDA I2C",
        "SCL I2C_SCL I2C",
    ]
    body = "\n".join(f"({line}) Tj" for line in lines)
    stream = f"BT\n{body}\nET".encode("latin-1")
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream\nendobj\n%%EOF\n"
    )


def test_upload_json_manifest():
    payload = {
        "component_id": "test_api_upload_sensor",
        "name": "API Upload Sensor",
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
    response = client.post(
        "/api/v1/librarian/upload",
        files={"file": ("sensor.json", json.dumps(payload), "application/json")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["manifest"]["component_id"] == "test_api_upload_sensor"
    assert data["committed"] is True
    assert data["extraction_source"] == "json"
    assert "message" in data


def test_pdf_upload_is_reviewed_then_committed(tmp_path, monkeypatch):
    monkeypatch.setattr("eda_platform.agents.librarian.ingest._MANIFESTS_DIR", tmp_path)
    monkeypatch.setattr("eda_platform.api.manifest_loader._MANIFESTS_DIR", tmp_path)
    clear_manifest_cache()

    upload = client.post(
        "/api/v1/librarian/upload",
        files={"file": ("sensor.pdf", _labeled_pdf(), "application/pdf")},
    )
    assert upload.status_code == 200
    draft = upload.json()
    assert draft["committed"] is False
    assert draft["extraction_source"] == "structured"
    assert draft["manifest"]["component_id"] == "test_api_extract_sensor"
    assert draft["manifest"]["operational_constraints"]["power_on_delay_ms"] == 4
    assert list(tmp_path.glob("*.json")) == []

    catalog = client.get("/api/v1/manifests")
    assert catalog.status_code == 200
    assert catalog.json()["manifests"] == []

    draft["manifest"]["name"] = "Reviewed API Sensor"
    commit = client.post("/api/v1/librarian/manifests", json={"manifest": draft["manifest"]})
    assert commit.status_code == 200
    assert commit.json()["manifest"]["name"] == "Reviewed API Sensor"
    assert (tmp_path / "test_api_extract_sensor.json").exists()

    catalog_after = client.get("/api/v1/manifests")
    ids = [item["component_id"] for item in catalog_after.json()["manifests"]]
    assert ids == ["test_api_extract_sensor"]

    duplicate = client.post("/api/v1/librarian/manifests", json={"manifest": draft["manifest"]})
    assert duplicate.status_code == 400

    clear_manifest_cache()
