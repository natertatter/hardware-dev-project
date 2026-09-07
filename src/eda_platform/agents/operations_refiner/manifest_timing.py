"""Extract timing values from ComponentManifest operational constraints."""

from eda_platform.agents.operations_refiner.best_practices import (
    I2C_SENSOR_POLL_PERIOD_MS,
    POWER_ON_SETTLE_MS,
)
from eda_platform.schemas import ComponentManifest, ComponentType, ProvenanceSource, TimingConstraint


def power_on_delay_ms(manifest: ComponentManifest | None) -> tuple[int, ProvenanceSource, str]:
    if manifest and manifest.operational_constraints:
        delay = manifest.operational_constraints.power_on_delay_ms
        if delay is not None:
            return delay, ProvenanceSource.DATASHEET, f"{manifest.component_id} power_on_delay_ms"
    return POWER_ON_SETTLE_MS, ProvenanceSource.BEST_PRACTICE, "Generic power rail settle"


def sensor_poll_period_ms(manifest: ComponentManifest | None) -> tuple[int, ProvenanceSource, str]:
    if manifest and manifest.operational_constraints:
        conv = manifest.operational_constraints.conversion_time_ms
        if conv is not None:
            return conv, ProvenanceSource.DATASHEET, f"{manifest.component_id} conversion_time_ms"
    return I2C_SENSOR_POLL_PERIOD_MS, ProvenanceSource.BEST_PRACTICE, "Default I2C sensor poll interval"


def timing_for_step(
    description: str,
    component_type: ComponentType | None,
    manifest: ComponentManifest | None,
    poll_period_ms: int,
    *,
    estop_delay_ms: int,
    motor_ramp_ms: int,
    motor_direction_ms: int,
    is_boot: bool,
    is_peripheral: bool,
) -> TimingConstraint | None:
    """Resolve timing for a step using datasheet constraints when available."""
    lower = description.lower()

    if "estop" in lower or "e-stop" in lower:
        return TimingConstraint(
            delay_ms=estop_delay_ms,
            source=ProvenanceSource.BEST_PRACTICE,
            note="Safety delay after estop release",
        )

    if is_boot or "power" in lower or "enable" in lower:
        delay, source, note = power_on_delay_ms(manifest)
        return TimingConstraint(delay_ms=delay, source=source, note=note)

    if "pause" in lower or "wait" in lower or "delay" in lower:
        if "motor" in lower or "ramp" in lower:
            return TimingConstraint(
                delay_ms=motor_ramp_ms,
                source=ProvenanceSource.BEST_PRACTICE,
                note="Motor ramp settling time",
            )
        if "direction" in lower:
            return TimingConstraint(
                delay_ms=motor_direction_ms,
                source=ProvenanceSource.BEST_PRACTICE,
                note="Pause before reversing motor direction",
            )
        delay, source, note = power_on_delay_ms(manifest)
        return TimingConstraint(delay_ms=delay, source=source, note=note)

    if component_type == ComponentType.SENSOR and is_peripheral:
        period, source, note = sensor_poll_period_ms(manifest)
        # Scheduling plan may override poll period when faster bus is available
        effective = max(period, poll_period_ms) if source == ProvenanceSource.DATASHEET else poll_period_ms
        return TimingConstraint(period_ms=effective, source=source, note=note)

    return None
