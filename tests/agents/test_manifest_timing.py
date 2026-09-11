"""Tests for datasheet-derived timing in operations refinement."""

from eda_platform.agents.operations_refiner import refine_operations
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence, ProvenanceSource
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
