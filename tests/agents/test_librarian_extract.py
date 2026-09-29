"""Structured datasheet extraction and the human commit gate."""

import json
import zlib
from pathlib import Path

import pytest

from eda_platform.agents.librarian.extract import (
    AnthropicDatasheetExtractor,
    DeterministicDatasheetExtractor,
    extract_datasheet,
    get_datasheet_extractor,
    parse_llm_field_json,
)
from eda_platform.agents.librarian.ingest import commit_manifest, ingest_upload
from eda_platform.agents.librarian.pdf_text import extract_pdf_text
from eda_platform.schemas import ComponentManifest, ComponentType, Pin, PinType, PowerRequirements


def _pdf(lines: list[str]) -> bytes:
    body = "\n".join(f"({line}) Tj" for line in lines)
    stream = f"BT\n{body}\nET".encode("latin-1")
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream\nendobj\n%%EOF\n"
    )


def _flate_pdf(lines: list[str]) -> bytes:
    body = "\n".join(f"({line}) Tj" for line in lines)
    raw = f"BT\n{body}\nET".encode("latin-1")
    compressed = zlib.compress(raw)
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Filter /FlateDecode /Length "
        + str(len(compressed)).encode()
        + b" >>\nstream\n"
        + compressed
        + b"\nendstream\nendobj\n%%EOF\n"
    )


_LABELED = [
    "Name: BME280 Environmental Sensor",
    "Type: SENSOR",
    "Component ID: sens_bme280_extract",
    "Min Operating Voltage: 1.71 V",
    "Max Operating Voltage: 3.6 V",
    "Logic Level Voltage: 1.8 V",
    "Max Current: 0.4 mA",
    "I2C Address: 0x76",
    "Power-on Delay: 2 ms",
    "Conversion Time: 10 ms",
    "I2C Max Clock: 3.4 MHz",
    "Pins:",
    "VCC POWER",
    "GND GND",
    "SDA I2C_SDA I2C",
    "SCL I2C_SCL I2C",
]


def test_extract_pdf_text_reads_literal_and_flate_streams():
    assert "Name: BME280 Environmental Sensor" in extract_pdf_text(_pdf(_LABELED))
    assert "Conversion Time: 10 ms" in extract_pdf_text(_flate_pdf(_LABELED))


def test_structured_extract_fills_manifest_and_timing():
    result = extract_datasheet("bme280.pdf", _pdf(_LABELED))
    manifest = result.manifest
    assert result.source == "structured"
    assert manifest.component_id == "sens_bme280_extract"
    assert manifest.name == "BME280 Environmental Sensor"
    assert manifest.type == ComponentType.SENSOR
    assert manifest.power_requirements.min_operating_voltage == 1.71
    assert manifest.power_requirements.max_operating_voltage == 3.6
    assert manifest.power_requirements.logic_level_voltage == 1.8
    assert manifest.power_requirements.max_current_draw_ma == 0.4
    assert manifest.default_i2c_address == "0x76"
    assert manifest.default_protocol == "I2C"
    assert manifest.operational_constraints is not None
    assert manifest.operational_constraints.power_on_delay_ms == 2
    assert manifest.operational_constraints.conversion_time_ms == 10
    assert manifest.operational_constraints.i2c_max_clock_hz == 3_400_000
    pin_ids = [pin.pin_id for pin in manifest.pins]
    assert pin_ids == ["VCC", "GND", "SDA", "SCL"]
    assert all(issue.severity != "error" for issue in result.issues)


def test_prose_extract_finds_voltage_address_and_pins():
    text = (
        "Supply voltage 1.71 to 3.6 V. Logic level 1.8 V. Maximum current 0.72 mA. "
        "I2C address 0x77. Power-on delay 2 ms. "
        "Connect VCC, GND, SDA and SCL."
    )
    result = extract_datasheet("env_sensor.pdf", _pdf([text]))
    assert result.source == "structured"
    assert result.manifest.power_requirements.min_operating_voltage == 1.71
    assert result.manifest.power_requirements.max_operating_voltage == 3.6
    assert result.manifest.default_i2c_address == "0x77"
    assert result.manifest.operational_constraints is not None
    assert result.manifest.operational_constraints.power_on_delay_ms == 2
    assert {pin.pin_id for pin in result.manifest.pins} == {"VCC", "GND", "SDA", "SCL"}


def test_empty_pdf_is_template_draft():
    result = extract_datasheet("mystery.pdf", b"%PDF-1.4 fake")
    assert result.source == "template"
    assert any(issue.code == "template_fallback" for issue in result.issues)
    assert result.manifest.operational_constraints is None
    assert "I2C" in (result.manifest.protocol_profiles or {})


def test_voltage_order_is_swapped_with_a_warning():
    class _Swap:
        def extract_fields(self, text: str) -> dict:
            return {
                "name": "Swap",
                "min_operating_voltage": 5,
                "max_operating_voltage": 1.8,
                "logic_level_voltage": 1.8,
                "max_current_draw_ma": 1,
                "pins": [
                    {"pin_id": "VCC", "pin_type": "POWER"},
                    {"pin_id": "GND", "pin_type": "GND"},
                    {"pin_id": "SDA", "pin_type": "I2C_SDA"},
                    {"pin_id": "SCL", "pin_type": "I2C_SCL"},
                ],
            }

    result = extract_datasheet("swap.pdf", _pdf(["datasheet"]), extractor=_Swap())
    assert result.manifest.power_requirements.min_operating_voltage == 1.8
    assert result.manifest.power_requirements.max_operating_voltage == 5
    assert any(issue.code == "voltage_order" for issue in result.issues)


def test_power_only_pins_are_an_error():
    class _Power:
        def extract_fields(self, text: str) -> dict:
            return {
                "name": "Bare",
                "min_operating_voltage": 3.3,
                "max_operating_voltage": 3.3,
                "logic_level_voltage": 3.3,
                "max_current_draw_ma": 1,
                "pins": [
                    {"pin_id": "VCC", "pin_type": "POWER"},
                    {"pin_id": "GND", "pin_type": "GND"},
                ],
            }

    result = extract_datasheet("bare.pdf", _pdf(["datasheet"]), extractor=_Power())
    assert any(issue.code == "no_protocol" and issue.severity == "error" for issue in result.issues)


def test_llm_fields_win_and_decline_falls_back():
    class _Llm:
        def extract_fields(self, text: str) -> dict:
            return {
                "name": "LLM Sensor",
                "type": "SENSOR",
                "min_operating_voltage": 1.8,
                "max_operating_voltage": 3.3,
                "logic_level_voltage": 3.3,
                "max_current_draw_ma": 1.2,
                "default_i2c_address": "0x40",
                "power_on_delay_ms": 5,
                "pins": [
                    {"pin_id": "VCC", "pin_type": "POWER"},
                    {"pin_id": "GND", "pin_type": "GND"},
                    {"pin_id": "SDA", "pin_type": "I2C_SDA"},
                    {"pin_id": "SCL", "pin_type": "I2C_SCL"},
                ],
            }

    class _Decline:
        def extract_fields(self, text: str) -> None:
            return None

    llm = extract_datasheet("part.pdf", _pdf(["ignored"]), extractor=_Llm())
    assert llm.source == "llm"
    assert llm.manifest.name == "LLM Sensor"
    assert llm.manifest.operational_constraints is not None
    assert llm.manifest.operational_constraints.power_on_delay_ms == 5

    fallback = extract_datasheet("bme.pdf", _pdf(_LABELED), extractor=_Decline())
    assert fallback.source == "structured"
    assert fallback.manifest.component_id == "sens_bme280_extract"
    assert any(issue.code == "llm_fallback" for issue in fallback.issues)


def test_parse_llm_field_json_keeps_known_keys():
    raw = '{"name": "X", "pins": [{"pin_id": "SDA", "pin_type": "I2C_SDA"}], "nope": 1}'
    parsed = parse_llm_field_json(f"here you go {raw}")
    assert parsed is not None
    assert parsed["name"] == "X"
    assert "nope" not in parsed
    assert parse_llm_field_json("no json") is None


def test_extractor_selection_follows_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_datasheet_extractor(), DeterministicDatasheetExtractor)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    selected = get_datasheet_extractor()
    assert isinstance(selected, AnthropicDatasheetExtractor)


def test_pdf_upload_does_not_commit_until_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("eda_platform.agents.librarian.ingest._MANIFESTS_DIR", tmp_path)
    result = ingest_upload("env.pdf", _pdf(_LABELED))
    assert result.committed is False
    assert result.manifest.component_id == "sens_bme280_extract"
    assert list(tmp_path.glob("*.json")) == []

    edited = result.manifest.model_copy(update={"name": "Reviewed BME280"})
    path = commit_manifest(edited)
    assert path.exists()
    saved = json.loads(path.read_text())
    assert saved["name"] == "Reviewed BME280"
    assert saved["operational_constraints"]["conversion_time_ms"] == 10

    with pytest.raises(ValueError, match="already exists"):
        commit_manifest(edited)


def test_commit_rejects_manifest_without_a_protocol(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("eda_platform.agents.librarian.ingest._MANIFESTS_DIR", tmp_path)
    manifest = ComponentManifest(
        component_id="test_extract_power_only",
        name="Power Only",
        type=ComponentType.PASSIVE,
        power_requirements=PowerRequirements(
            min_operating_voltage=3.3,
            max_operating_voltage=3.3,
            logic_level_voltage=3.3,
            max_current_draw_ma=0,
        ),
        pins=[Pin(pin_id="VCC", pin_type=PinType.POWER)],
    )
    with pytest.raises(ValueError, match="no recognizable communication protocols"):
        commit_manifest(manifest)
    assert list(tmp_path.glob("*.json")) == []
