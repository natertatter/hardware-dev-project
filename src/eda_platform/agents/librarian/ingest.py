"""Datasheet ingestion: PDF/JSON upload to ComponentManifest."""

import json
import re
from pathlib import Path

from eda_platform.schemas import ComponentManifest, ComponentType, Pin, PinType, PowerRequirements
from eda_platform.schemas.protocols import available_protocols, default_protocol

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DATASHEETS_DIR = _REPO_ROOT / "hardware_library" / "datasheets"
_MANIFESTS_DIR = _REPO_ROOT / "hardware_library" / "manifests"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:48] or "component"


def _unique_component_id(base: str) -> str:
    candidate = base
    counter = 1
    while (_MANIFESTS_DIR / f"{candidate}.json").exists():
        counter += 1
        candidate = f"{base}_{counter}"
    return candidate


def _template_sensor_manifest(component_id: str, name: str) -> ComponentManifest:
    """Generate a multi-protocol sensor template from a datasheet filename."""
    return ComponentManifest(
        component_id=component_id,
        name=name,
        type=ComponentType.SENSOR,
        power_requirements=PowerRequirements(
            min_operating_voltage=3.0,
            max_operating_voltage=3.6,
            logic_level_voltage=3.3,
            max_current_draw_ma=5.0,
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


def ingest_json_manifest(content: bytes) -> ComponentManifest:
    """Validate and return a ComponentManifest from raw JSON bytes."""
    manifest = ComponentManifest.model_validate_json(content)
    # Ensure protocol profiles are derivable
    if not available_protocols(manifest):
        raise ValueError(
            f"Manifest '{manifest.component_id}' has no recognizable communication protocols"
        )
    return manifest


def ingest_pdf_datasheet(filename: str, content: bytes) -> tuple[ComponentManifest, Path]:
    """Save a PDF datasheet and produce a template manifest.

    Full LLM-based extraction is deferred; this stub saves the PDF and creates
    a multi-protocol sensor template keyed off the filename.
    """
    _DATASHEETS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", Path(filename).name)
    datasheet_path = _DATASHEETS_DIR / safe_name
    datasheet_path.write_bytes(content)

    stem = Path(filename).stem
    display_name = stem.replace("_", " ").replace("-", " ").strip().title()
    base_id = _slugify(f"sens_{stem}")
    component_id = _unique_component_id(base_id)

    manifest = _template_sensor_manifest(component_id, display_name or component_id)
    return manifest, datasheet_path


def save_manifest(manifest: ComponentManifest) -> Path:
    """Write manifest JSON to hardware_library/manifests/ and return the path."""
    _MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _MANIFESTS_DIR / f"{manifest.component_id}.json"
    path.write_text(manifest.model_dump_json(indent=2))
    return path


def ingest_upload(filename: str, content: bytes) -> tuple[ComponentManifest, Path, str | None]:
    """Route upload by extension: JSON manifests or PDF datasheets.

    Returns (manifest, saved_path, message).
    """
    lower = filename.lower()
    if lower.endswith(".json"):
        manifest = ingest_json_manifest(content)
        if (_MANIFESTS_DIR / f"{manifest.component_id}.json").exists():
            raise ValueError(
                f"Component '{manifest.component_id}' already exists in the catalog"
            )
        path = save_manifest(manifest)
        proto = default_protocol(manifest)
        return manifest, path, f"Manifest '{manifest.component_id}' added (protocol: {proto})"

    if lower.endswith(".pdf"):
        manifest, datasheet_path = ingest_pdf_datasheet(filename, content)
        manifest_path = save_manifest(manifest)
        protos = ", ".join(available_protocols(manifest))
        return (
            manifest,
            manifest_path,
            f"Datasheet saved to {datasheet_path.name}; template manifest created "
            f"with protocols: {protos}",
        )

    raise ValueError("Unsupported file type — upload a .json manifest or .pdf datasheet")
