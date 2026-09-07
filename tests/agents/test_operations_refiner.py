"""Unit tests for the Operations Refiner agent."""

from eda_platform.agents.operations_refiner import refine_operations
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def _narrative_sequence() -> OperationsSequence:
    return OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.NARRATIVE,
        narrative=(
            "Enable power rail and wait.\n"
            "Poll sensor_1 current reading."
        ),
    )


class TestOperationsRefiner:
    def test_narrative_promoted_to_steps_with_bindings(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        result = refine_operations(_narrative_sequence(), project, manifests)

        assert result.fidelity_promoted is True
        assert result.refined.fidelity in (FidelityLevel.STEPS, FidelityLevel.TIMED)
        assert len(result.refined.steps) >= 2
        bound = [s for s in result.refined.steps if s.target_node_id == "sensor_1"]
        assert len(bound) >= 1

    def test_sensor_step_gets_timing(self):
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
        poll_steps = [s for s in result.refined.steps if "sensor" in s.description.lower()]
        assert any(s.timing and s.timing.period_ms for s in poll_steps)

    def test_unbound_step_surfaces_question(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(step_id="s1", description="Do something mysterious on widget_x"),
            ],
        )
        result = refine_operations(seq, project, manifests)
        assert result.questions_added >= 1
        assert result.refined.steps[0].needs_refinement is True
