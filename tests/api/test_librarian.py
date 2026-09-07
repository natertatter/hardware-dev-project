"""Tests for librarian upload API."""

import json
from pathlib import Path

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
    assert "message" in data
