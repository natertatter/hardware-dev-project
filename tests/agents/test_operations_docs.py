"""Tests for operating document generation."""

from eda_platform.agents.operations_docs import (
    generate_bringup_checklist,
    generate_operating_procedure,
)
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence, TimingConstraint
from tests.test_logic_checker import _valid_project_state


def _timed_sequence() -> OperationsSequence:
    return OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="s1",
                description="Enable power rail",
                timing=TimingConstraint(delay_ms=100, source="datasheet"),
            ),
            OperationStep(
                step_id="s2",
                description="Poll sensor_1",
                target_node_id="sensor_1",
                timing=TimingConstraint(period_ms=20, source="datasheet"),
            ),
        ],
    )


class TestOperationsDocs:
    def test_operating_procedure_contains_steps(self):
        project = _valid_project_state()
        doc = generate_operating_procedure(_timed_sequence(), project)
        assert "Enable power rail" in doc
        assert "sensor_1" in doc
        assert "20 ms" in doc

    def test_bringup_checklist_has_checkboxes(self):
        project = _valid_project_state()
        doc = generate_bringup_checklist(_timed_sequence(), project)
        assert "- [ ] Enable power rail" in doc
        assert "wait 100 ms" in doc
