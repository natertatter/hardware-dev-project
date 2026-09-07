"""Pydantic models for the ComponentManifest schema (Hardware Librarian output)."""

from pydantic import BaseModel, Field, field_validator

from eda_platform.schemas.enums import ActiveState, ComponentType, PinType


class OperationalConstraints(BaseModel):
    """Timing and protocol constraints extracted from datasheets (Librarian output)."""

    power_on_delay_ms: int | None = Field(
        default=None, ge=0, description="Required delay after power rail enable (ms)"
    )
    conversion_time_ms: int | None = Field(
        default=None, ge=0, description="Minimum time between sensor conversions (ms)"
    )
    i2c_max_clock_hz: int | None = Field(
        default=None, ge=0, description="Maximum I2C clock frequency (Hz)"
    )


class PowerRequirements(BaseModel):
    """Operating power envelope extracted from Recommended Operating Conditions."""

    min_operating_voltage: float = Field(..., ge=0, description="Minimum supply voltage (V)")
    max_operating_voltage: float = Field(..., ge=0, description="Maximum supply voltage (V)")
    logic_level_voltage: float = Field(..., ge=0, description="Logic I/O voltage (VDD/VCC/VIO)")
    max_current_draw_ma: float = Field(..., ge=0, description="Maximum current draw (mA)")

    @field_validator("max_operating_voltage")
    @classmethod
    def max_gte_min(cls, v: float, info) -> float:
        min_v = info.data.get("min_operating_voltage")
        if min_v is not None and v < min_v:
            raise ValueError("max_operating_voltage must be >= min_operating_voltage")
        return v


class Pin(BaseModel):
    """Single pin definition from a component datasheet pinout table."""

    pin_id: str = Field(..., min_length=1, description="Pin identifier (e.g., GPIO12, VCC)")
    pin_type: PinType
    supported_features: list[str] = Field(default_factory=list)
    max_current_source_ma: float | None = Field(
        default=None, ge=0, description="Max source current for MCU GPIO pins (mA)"
    )
    internal_pullup_enabled: bool = False
    active_state: ActiveState = ActiveState.NONE


class ComponentManifest(BaseModel):
    """Canonical hardware description produced by the Hardware Librarian agent."""

    component_id: str = Field(
        ..., min_length=1, pattern=r"^[a-z0-9_]+$", description="Unique component key"
    )
    name: str = Field(..., min_length=1)
    type: ComponentType
    power_requirements: PowerRequirements
    default_i2c_address: str | None = Field(
        default=None, description="Default 7-bit I2C address in hex (e.g., 0x40)"
    )
    operational_constraints: OperationalConstraints | None = Field(
        default=None, description="Datasheet-derived timing and protocol limits"
    )
    pins: list[Pin] = Field(..., min_length=1)

    @field_validator("default_i2c_address")
    @classmethod
    def validate_i2c_address(cls, v: str | None) -> str | None:
        if v is None:
            return v
        normalized = v.strip().lower()
        if not normalized.startswith("0x"):
            raise ValueError("I2C address must be hex prefixed with 0x")
        int(normalized, 16)  # raises ValueError on invalid hex
        return normalized
