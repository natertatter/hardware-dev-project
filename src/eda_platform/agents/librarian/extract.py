"""Structured datasheet extraction into a reviewable ComponentManifest.

Deterministic parser handles labeled excerpts and common electrical phrases.
When ANTHROPIC_API_KEY is set, an Anthropic extractor runs first and falls
back to the deterministic parser. Nothing here writes the catalog.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from eda_platform.agents.librarian.pdf_text import extract_pdf_text
from eda_platform.schemas import (
    ComponentManifest,
    ComponentType,
    OperationalConstraints,
    Pin,
    PinType,
    PowerRequirements,
    available_protocols,
)

logger = logging.getLogger(__name__)

_TEMPLATE_MIN_V = 3.0
_TEMPLATE_MAX_V = 3.6
_TEMPLATE_LOGIC_V = 3.3
_TEMPLATE_CURRENT_MA = 5.0

_PIN_FEATURES: dict[str, list[str]] = {
    PinType.I2C_SDA.value: ["I2C"],
    PinType.I2C_SCL.value: ["I2C"],
    PinType.SPI_MOSI.value: ["SPI"],
    PinType.SPI_MISO.value: ["SPI"],
    PinType.SPI_SCK.value: ["SPI"],
    PinType.SPI_CS.value: ["SPI"],
    PinType.UART_TX.value: ["UART"],
    PinType.UART_RX.value: ["UART"],
}

# Token as it appears in a datasheet → (pin_type, features).
_PIN_ALIASES: dict[str, tuple[str, list[str]]] = {
    "VCC": (PinType.POWER.value, []),
    "VDD": (PinType.POWER.value, []),
    "VIN": (PinType.POWER.value, []),
    "3V3": (PinType.POWER.value, []),
    "GND": (PinType.GND.value, []),
    "VSS": (PinType.GND.value, []),
    "SDA": (PinType.I2C_SDA.value, ["I2C"]),
    "SCL": (PinType.I2C_SCL.value, ["I2C"]),
    "SDI": (PinType.SPI_MOSI.value, ["SPI"]),
    "MOSI": (PinType.SPI_MOSI.value, ["SPI"]),
    "SDO": (PinType.SPI_MISO.value, ["SPI"]),
    "MISO": (PinType.SPI_MISO.value, ["SPI"]),
    "SCK": (PinType.SPI_SCK.value, ["SPI"]),
    "SCLK": (PinType.SPI_SCK.value, ["SPI"]),
    "CS": (PinType.SPI_CS.value, ["SPI"]),
    "CSB": (PinType.SPI_CS.value, ["SPI"]),
    "SS": (PinType.SPI_CS.value, ["SPI"]),
    "TX": (PinType.UART_TX.value, ["UART"]),
    "RX": (PinType.UART_RX.value, ["UART"]),
}

_FIELD_KEYS = (
    "name",
    "type",
    "component_id",
    "min_operating_voltage",
    "max_operating_voltage",
    "logic_level_voltage",
    "max_current_draw_ma",
    "default_i2c_address",
    "power_on_delay_ms",
    "conversion_time_ms",
    "i2c_max_clock_hz",
    "pins",
)

_LABELED_LINES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("name", re.compile(r"^(?:component\s+name|part\s+name|name)\s*:\s*(.+)$", re.I)),
    ("component_id", re.compile(r"^component\s+id\s*:\s*([A-Za-z0-9_]+)\s*$", re.I)),
    ("type", re.compile(r"^type\s*:\s*(MCU|SENSOR|MOTOR_DRIVER|ACTUATOR|PASSIVE)\s*$", re.I)),
    (
        "min_operating_voltage",
        re.compile(r"^min(?:imum)?\s+operating\s+voltage\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*v?$", re.I),
    ),
    (
        "max_operating_voltage",
        re.compile(r"^max(?:imum)?\s+operating\s+voltage\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*v?$", re.I),
    ),
    (
        "logic_level_voltage",
        re.compile(r"^logic(?:\s+level)?(?:\s+voltage)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*v?$", re.I),
    ),
    (
        "max_current_draw_ma",
        re.compile(r"^max(?:imum)?\s+current(?:\s+draw)?\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*m?a?$", re.I),
    ),
    ("default_i2c_address", re.compile(r"^i2c\s+address\s*[:=]\s*(0x[0-9a-fA-F]+)\s*$", re.I)),
    ("power_on_delay_ms", re.compile(r"^power[- ]on\s+delay\s*[:=]\s*(\d+)\s*m?s?$", re.I)),
    ("conversion_time_ms", re.compile(r"^conversion\s+time\s*[:=]\s*(\d+)\s*m?s?$", re.I)),
    (
        "i2c_max_clock_hz",
        re.compile(r"^i2c\s+max(?:imum)?\s+clock\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)\s*(mhz|khz|hz)?$", re.I),
    ),
)

_PROSE_VOLTAGE = re.compile(
    r"([0-9]+(?:\.[0-9]+)?)\s*(?:to|–|-)\s*([0-9]+(?:\.[0-9]+)?)\s*v\b",
    re.I,
)
_PROSE_LOGIC = re.compile(
    r"logic(?:\s+level)?(?:\s+voltage)?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*v\b",
    re.I,
)
_PROSE_CURRENT = re.compile(
    r"max(?:imum)?\s+current(?:\s+draw)?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*ma\b",
    re.I,
)
_PROSE_ADDRESS = re.compile(r"i2c\s+address\s*[:=]?\s*(0x[0-9a-fA-F]{1,2})\b", re.I)
_PROSE_POWER_ON = re.compile(r"power[- ]on\s+delay\s*[:=]?\s*(\d+)\s*ms\b", re.I)
_PROSE_CONVERSION = re.compile(r"conversion\s+time\s*[:=]?\s*(\d+)\s*ms\b", re.I)
_PROSE_CLOCK = re.compile(
    r"i2c\s+max(?:imum)?\s+clock\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*(mhz|khz|hz)\b",
    re.I,
)
_PINS_HEADER = re.compile(r"^pins?\s*:?\s*$", re.I)
_ID_RE = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class ExtractionIssue:
    severity: str
    code: str
    message: str
    field: str | None = None


@dataclass
class DatasheetExtraction:
    manifest: ComponentManifest
    issues: list[ExtractionIssue]
    source: str
    message: str


class DatasheetExtractor(Protocol):
    """Turn datasheet text into a partial field dict. Return None to decline."""

    def extract_fields(self, text: str) -> dict[str, Any] | None: ...


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:48] or "component"


def template_sensor_manifest(component_id: str, name: str) -> ComponentManifest:
    """Multi-protocol sensor placeholder used when a datasheet has no fields."""
    return ComponentManifest(
        component_id=component_id,
        name=name,
        type=ComponentType.SENSOR,
        power_requirements=PowerRequirements(
            min_operating_voltage=_TEMPLATE_MIN_V,
            max_operating_voltage=_TEMPLATE_MAX_V,
            logic_level_voltage=_TEMPLATE_LOGIC_V,
            max_current_draw_ma=_TEMPLATE_CURRENT_MA,
        ),
        default_i2c_address="0x76",
        default_protocol="I2C",
        protocol_profiles={
            "I2C": ["VCC", "GND", "SDA", "SCL"],
            "SPI": ["VCC", "GND", "SDI", "SDO", "SCK", "CS"],
        },
        pins=[
            Pin(pin_id="VCC", pin_type=PinType.POWER),
            Pin(pin_id="GND", pin_type=PinType.GND),
            Pin(pin_id="SDA", pin_type=PinType.I2C_SDA, supported_features=["I2C"]),
            Pin(pin_id="SCL", pin_type=PinType.I2C_SCL, supported_features=["I2C"]),
            Pin(pin_id="SDI", pin_type=PinType.SPI_MOSI, supported_features=["SPI"]),
            Pin(pin_id="SDO", pin_type=PinType.SPI_MISO, supported_features=["SPI"]),
            Pin(pin_id="SCK", pin_type=PinType.SPI_SCK, supported_features=["SPI"]),
            Pin(pin_id="CS", pin_type=PinType.SPI_CS, supported_features=["SPI"]),
        ],
    )


def _template_pins() -> list[Pin]:
    return list(template_sensor_manifest("sens_template", "Template").pins)


class DeterministicDatasheetExtractor:
    """Parse labeled lines and a few prose patterns. No network."""

    def extract_fields(self, text: str) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        pins: list[dict[str, Any]] = []
        in_pins = False
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                in_pins = False
                continue
            if _PINS_HEADER.match(line):
                in_pins = True
                continue
            if in_pins:
                pin = _pin_from_line(line)
                if pin is not None:
                    pins.append(pin)
                    continue
                if line.startswith("|") or set(line) <= set("-| :"):
                    continue
                in_pins = False
            for key, pattern in _LABELED_LINES:
                match = pattern.match(line)
                if not match:
                    continue
                if key == "i2c_max_clock_hz":
                    fields[key] = _clock_hz(match.group(1), match.group(2) or "hz")
                else:
                    fields[key] = match.group(1).strip()
                break
        if pins:
            fields["pins"] = pins
        _fill_prose(text, fields)
        return _clean_fields(fields)


def _fill_prose(text: str, fields: dict[str, Any]) -> None:
    if "min_operating_voltage" not in fields or "max_operating_voltage" not in fields:
        match = _PROSE_VOLTAGE.search(text)
        if match:
            fields.setdefault("min_operating_voltage", match.group(1))
            fields.setdefault("max_operating_voltage", match.group(2))
    if "logic_level_voltage" not in fields:
        match = _PROSE_LOGIC.search(text)
        if match:
            fields["logic_level_voltage"] = match.group(1)
    if "max_current_draw_ma" not in fields:
        match = _PROSE_CURRENT.search(text)
        if match:
            fields["max_current_draw_ma"] = match.group(1)
    if "default_i2c_address" not in fields:
        match = _PROSE_ADDRESS.search(text)
        if match:
            fields["default_i2c_address"] = match.group(1)
    if "power_on_delay_ms" not in fields:
        match = _PROSE_POWER_ON.search(text)
        if match:
            fields["power_on_delay_ms"] = match.group(1)
    if "conversion_time_ms" not in fields:
        match = _PROSE_CONVERSION.search(text)
        if match:
            fields["conversion_time_ms"] = match.group(1)
    if "i2c_max_clock_hz" not in fields:
        match = _PROSE_CLOCK.search(text)
        if match:
            fields["i2c_max_clock_hz"] = _clock_hz(match.group(1), match.group(2))
    if not fields.get("pins"):
        prose_pins = _pins_from_prose(text)
        if prose_pins:
            fields["pins"] = prose_pins


def _clock_hz(number: str, unit: str) -> int:
    mult = {"mhz": 1_000_000, "khz": 1_000, "hz": 1}
    return int(round(float(number) * mult[unit.lower()]))


def _pins_from_prose(text: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in re.finditer(r"\b([A-Za-z][A-Za-z0-9]{1,15})\b", text):
        token = match.group(1).upper()
        if token in seen or token not in _PIN_ALIASES:
            continue
        seen.add(token)
        pin_type, features = _PIN_ALIASES[token]
        found.append(
            {"pin_id": token, "pin_type": pin_type, "supported_features": list(features)}
        )
    return found


def _pin_from_line(line: str) -> dict[str, Any] | None:
    if "|" in line:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        cells = [cell for cell in cells if cell and not set(cell) <= set("-: ")]
        if len(cells) >= 2 and cells[0].lower() not in {"pin", "pin_id", "name"}:
            return _pin_dict(cells[0], cells[1], cells[2] if len(cells) > 2 else "")
        return None
    parts = line.split()
    if not parts or parts[0].lower() in {"pin", "pin_id", "name", "type"}:
        return None
    if len(parts) >= 2:
        features = " ".join(parts[2:]) if len(parts) > 2 else ""
        return _pin_dict(parts[0], parts[1], features)
    return _pin_dict(parts[0], "", "")


def _pin_dict(pin_id: str, pin_type: str, features: str) -> dict[str, Any] | None:
    pin_id = pin_id.strip()
    if not pin_id:
        return None
    feature_list = [part.strip() for part in re.split(r"[, ]+", features) if part.strip()]
    explicit = pin_type.strip().upper()
    if explicit in PinType.__members__:
        if not feature_list:
            feature_list = list(_PIN_FEATURES.get(explicit, []))
        return {"pin_id": pin_id, "pin_type": explicit, "supported_features": feature_list}
    alias = _PIN_ALIASES.get(pin_id.upper())
    if alias is None:
        return None
    alias_type, alias_features = alias
    return {
        "pin_id": pin_id.upper(),
        "pin_type": alias_type,
        "supported_features": feature_list or list(alias_features),
    }


def _clean_fields(raw: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key in _FIELD_KEYS:
        if key not in raw:
            continue
        value = raw[key]
        if value is None or value == "" or value == []:
            continue
        cleaned[key] = value
    return cleaned


def parse_llm_field_json(text: str) -> dict[str, Any] | None:
    """Pull a field dict from an LLM response. None when it is not usable JSON."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        raw = json.loads(match.group())
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    cleaned = _clean_fields(raw)
    return cleaned or None


class AnthropicDatasheetExtractor:
    """Ask Anthropic for a field JSON object. Decline on any failure."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self._api_key = api_key
        self._model = model

    def extract_fields(self, text: str) -> dict[str, Any] | None:
        try:
            import anthropic
        except ImportError:
            logger.warning("anthropic package not installed — falling back to deterministic extract")
            return None
        prompt = (
            "Extract a component manifest from the datasheet text. "
            "Return ONLY JSON with any of these keys you can support from the text: "
            "name, type (MCU|SENSOR|MOTOR_DRIVER|ACTUATOR|PASSIVE), component_id, "
            "min_operating_voltage, max_operating_voltage, logic_level_voltage, "
            "max_current_draw_ma, default_i2c_address, power_on_delay_ms, "
            "conversion_time_ms, i2c_max_clock_hz, "
            'pins (list of {pin_id, pin_type, supported_features}). '
            "Do not invent values that are not in the text.\n\n"
            f"Datasheet text:\n{text[:12000]}"
        )
        try:
            client = anthropic.Anthropic(api_key=self._api_key)
            message = client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            content = message.content[0].text if message.content else ""
            return parse_llm_field_json(content)
        except Exception as exc:
            logger.warning("Anthropic datasheet extract failed (%s)", exc)
            return None


def get_datasheet_extractor() -> DatasheetExtractor:
    """Anthropic when ANTHROPIC_API_KEY is set, otherwise the deterministic parser."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
        return AnthropicDatasheetExtractor(api_key=api_key, model=model)
    return DeterministicDatasheetExtractor()


def extract_datasheet(
    filename: str,
    content: bytes,
    *,
    extractor: DatasheetExtractor | None = None,
) -> DatasheetExtraction:
    """Build a draft manifest from PDF bytes. Does not write the catalog."""
    text = extract_pdf_text(content)
    if not text:
        return _template_extraction(filename)

    chosen = extractor if extractor is not None else get_datasheet_extractor()
    llm_declined = False
    source = "structured"
    fields: dict[str, Any] | None
    if isinstance(chosen, DeterministicDatasheetExtractor):
        fields = chosen.extract_fields(text)
    else:
        fields = chosen.extract_fields(text)
        if not fields:
            llm_declined = True
            fields = DeterministicDatasheetExtractor().extract_fields(text)
        else:
            source = "llm"

    extraction = _manifest_from_fields(filename, fields or {}, source)
    if llm_declined:
        extraction.issues.insert(
            0,
            ExtractionIssue(
                severity="warning",
                code="llm_fallback",
                message="LLM extraction was unavailable; used the deterministic parser.",
            ),
        )
    return extraction


def _template_extraction(filename: str) -> DatasheetExtraction:
    name = _display_name(filename, None)
    component_id = _proposed_id(ComponentType.SENSOR, name, None)
    manifest = template_sensor_manifest(component_id, name)
    return DatasheetExtraction(
        manifest=manifest,
        issues=[
            ExtractionIssue(
                severity="warning",
                code="template_fallback",
                message=(
                    "No datasheet text could be read. A template manifest is ready "
                    "for review and has not been added to the catalog."
                ),
            )
        ],
        source="template",
        message=(
            f"No structured fields found in {Path(filename).name}. "
            "Review the template draft and save it to add the part to the catalog."
        ),
    )


def _manifest_from_fields(
    filename: str,
    fields: dict[str, Any],
    source: str,
) -> DatasheetExtraction:
    if not fields:
        return _template_extraction(filename)

    issues: list[ExtractionIssue] = []
    comp_type = _infer_type(filename, fields)
    name = _display_name(filename, fields.get("name"))
    explicit_id = fields.get("component_id")
    explicit = explicit_id.strip().lower() if isinstance(explicit_id, str) else None
    if explicit is not None and not _ID_RE.fullmatch(explicit):
        issues.append(
            ExtractionIssue(
                severity="warning",
                code="invalid_component_id",
                message=f"Ignored component id '{explicit_id}' because it is not a lowercase slug.",
                field="component_id",
            )
        )
        explicit = None
    component_id = _proposed_id(comp_type, name, explicit)

    min_v = _as_float(fields.get("min_operating_voltage"))
    max_v = _as_float(fields.get("max_operating_voltage"))
    logic_v = _as_float(fields.get("logic_level_voltage"))
    current = _as_float(fields.get("max_current_draw_ma"))
    if min_v is None or max_v is None or logic_v is None or current is None:
        issues.append(
            ExtractionIssue(
                severity="warning",
                code="defaulted_field",
                message="One or more power fields were missing; placeholder electrical limits were used.",
                field="power_requirements",
            )
        )
    if min_v is None:
        min_v = _TEMPLATE_MIN_V
    if max_v is None:
        max_v = _TEMPLATE_MAX_V
    if max_v < min_v:
        min_v, max_v = max_v, min_v
        issues.append(
            ExtractionIssue(
                severity="warning",
                code="voltage_order",
                message="Min and max operating voltage were swapped so max is greater than or equal to min.",
                field="power_requirements",
            )
        )
    if logic_v is None:
        logic_v = min(max_v, _TEMPLATE_LOGIC_V)
    if current is None:
        current = _TEMPLATE_CURRENT_MA

    pins = _pins_from_field(fields.get("pins"))
    if not pins:
        pins = _template_pins()
        issues.append(
            ExtractionIssue(
                severity="warning",
                code="defaulted_field",
                message="No pinout was extracted; template I2C/SPI pins were used.",
                field="pins",
            )
        )

    address = _normalize_address(fields.get("default_i2c_address"))
    if fields.get("default_i2c_address") and address is None:
        issues.append(
            ExtractionIssue(
                severity="warning",
                code="invalid_i2c_address",
                message="I2C address was not valid hex (0x..) and was dropped.",
                field="default_i2c_address",
            )
        )

    constraints = _constraints_from_fields(fields)
    if constraints is None:
        issues.append(
            ExtractionIssue(
                severity="warning",
                code="missing_timing",
                message="No datasheet timing (power-on delay, conversion time, or I2C clock) was extracted.",
                field="operational_constraints",
            )
        )

    manifest = ComponentManifest(
        component_id=component_id,
        name=name,
        type=comp_type,
        power_requirements=PowerRequirements(
            min_operating_voltage=min_v,
            max_operating_voltage=max_v,
            logic_level_voltage=logic_v,
            max_current_draw_ma=current,
        ),
        default_i2c_address=address,
        operational_constraints=constraints,
        pins=pins,
    )
    protocols = available_protocols(manifest)
    if not protocols:
        issues.append(
            ExtractionIssue(
                severity="error",
                code="no_protocol",
                message="Manifest has no recognizable communication protocol. Add bus pins before saving.",
                field="pins",
            )
        )
    default = "I2C" if "I2C" in protocols else (protocols[0] if protocols else None)
    manifest = manifest.model_copy(update={"default_protocol": default})

    label = "an LLM extract" if source == "llm" else "datasheet text"
    return DatasheetExtraction(
        manifest=manifest,
        issues=issues,
        source=source,
        message=(
            f"Extracted a draft from {label}. "
            "Review the manifest and save it to add the part to the catalog."
        ),
    )


def _constraints_from_fields(fields: dict[str, Any]) -> OperationalConstraints | None:
    power_on = _as_int(fields.get("power_on_delay_ms"))
    conversion = _as_int(fields.get("conversion_time_ms"))
    clock = _as_int(fields.get("i2c_max_clock_hz"))
    if power_on is None and conversion is None and clock is None:
        return None
    return OperationalConstraints(
        power_on_delay_ms=power_on,
        conversion_time_ms=conversion,
        i2c_max_clock_hz=clock,
    )


def _pins_from_field(raw: Any) -> list[Pin]:
    if not isinstance(raw, list):
        return []
    pins: list[Pin] = []
    seen: set[str] = set()
    for item in raw:
        parsed: dict[str, Any] | None
        if isinstance(item, str):
            parsed = _pin_dict(item, "", "")
        elif isinstance(item, dict):
            features = item.get("supported_features") or []
            if isinstance(features, str):
                feature_text = features
            elif isinstance(features, list):
                feature_text = ",".join(str(part) for part in features)
            else:
                feature_text = ""
            parsed = _pin_dict(str(item.get("pin_id") or ""), str(item.get("pin_type") or ""), feature_text)
        else:
            parsed = None
        if parsed is None or parsed["pin_id"] in seen:
            continue
        seen.add(parsed["pin_id"])
        pins.append(
            Pin(
                pin_id=parsed["pin_id"],
                pin_type=PinType(parsed["pin_type"]),
                supported_features=list(parsed["supported_features"]),
            )
        )
    return pins


def _infer_type(filename: str, fields: dict[str, Any]) -> ComponentType:
    explicit = str(fields.get("type") or "").strip().upper()
    if explicit in ComponentType.__members__:
        return ComponentType[explicit]
    stem = Path(filename).stem.lower()
    if "mcu" in stem or "microcontroller" in stem:
        return ComponentType.MCU
    if "motor" in stem:
        return ComponentType.MOTOR_DRIVER
    return ComponentType.SENSOR


def _display_name(filename: str, explicit: Any) -> str:
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    stem = Path(filename).stem
    display = stem.replace("_", " ").replace("-", " ").strip().title()
    return display or "Component"


def _proposed_id(comp_type: ComponentType, name: str, explicit: str | None) -> str:
    if explicit:
        return explicit[:48]
    prefix = {
        ComponentType.MCU: "mcu",
        ComponentType.SENSOR: "sens",
        ComponentType.MOTOR_DRIVER: "drv",
        ComponentType.ACTUATOR: "act",
        ComponentType.PASSIVE: "pas",
    }[comp_type]
    return _slugify(f"{prefix}_{name}")


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _as_int(value: Any) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    return int(round(number))


def _normalize_address(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text.startswith("0x"):
        return None
    try:
        int(text, 16)
    except ValueError:
        return None
    return text
