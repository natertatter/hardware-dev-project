"""Tests for datasheet-derived timing in operations refinement."""

from eda_platform.agents.operations_refiner import refine_operations
from eda_platform.schemas import (
    FidelityLevel,
    OperationStep,
    OperationsSequence,
    ProvenanceSource,
    TimingConstraint,
)
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


class TestManifestTiming:
    def test_sensor_poll_uses_datasheet_conversion_time(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(step_id="s1", description="Enable power rail"),
                OperationStep(step_id="s2", description="Poll sensor_1 current"),
            ],
        )
        result = refine_operations(seq, project, manifests)
        poll = next(s for s in result.refined.steps if "sensor" in s.description.lower())
        assert poll.timing is not None
        assert poll.timing.period_ms == 20
        assert poll.timing.source == ProvenanceSource.DATASHEET
        assert poll.timing.note == "sens_ina219 operational_constraints.conversion_time_ms"
        assert poll.provenance == ProvenanceSource.DATASHEET

    def test_slower_schedule_overrides_conversion_time_as_inferred(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        manifests["sens_ina219"].operational_constraints.conversion_time_ms = 5
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(step_id="s1", description="Enable power rail"),
                OperationStep(step_id="s2", description="Poll sensor_1 current"),
            ],
        )
        result = refine_operations(seq, project, manifests)
        poll = next(s for s in result.refined.steps if "sensor" in s.description.lower())
        assert poll.timing is not None
        assert poll.timing.period_ms == 20
        assert poll.timing.source == ProvenanceSource.INFERRED
        assert poll.provenance == ProvenanceSource.INFERRED
        assert "5 ms" in (poll.timing.note or "")
        assert "20 ms" in (poll.timing.note or "")

    def test_existing_human_timing_is_preserved(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(
                    step_id="s1",
                    description="Poll sensor_1 current",
                    timing=TimingConstraint(
                        period_ms=250,
                        source=ProvenanceSource.HUMAN,
                        note="operator cadence",
                    ),
                ),
            ],
        )
        result = refine_operations(seq, project, manifests)
        step = result.refined.steps[0]
        assert step.timing is not None
        assert step.timing.period_ms == 250
        assert step.timing.source == ProvenanceSource.HUMAN
        assert step.timing.note == "operator cadence"
        assert step.provenance == ProvenanceSource.INFERRED

    def test_missing_constraints_use_best_practice(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        manifests["sens_ina219"].operational_constraints = None
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(step_id="s1", description="Enable power rail for sensor_1"),
            ],
        )
        result = refine_operations(seq, project, manifests)
        step = result.refined.steps[0]
        assert step.timing is not None
        assert step.timing.delay_ms == 100
        assert step.timing.source == ProvenanceSource.BEST_PRACTICE
        assert step.provenance != ProvenanceSource.DATASHEET

    def test_boot_step_uses_datasheet_power_on_delay(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(step_id="s1", description="Enable power rail for sensor_1"),
            ],
        )
        result = refine_operations(seq, project, manifests)
        step = result.refined.steps[0]
        assert step.timing is not None
        assert step.timing.delay_ms == 100
        assert step.timing.source == ProvenanceSource.DATASHEET
        assert step.timing.note == "sens_ina219 operational_constraints.power_on_delay_ms"
        assert step.provenance == ProvenanceSource.DATASHEET
