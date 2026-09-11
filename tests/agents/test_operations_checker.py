"""Unit tests for the Operations Checker agent."""

from eda_platform.agents.operations_checker import validate_operations_collect
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def _refined_sequence() -> OperationsSequence:
    return OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="s1",
                description="Enable power rail",
                target_node_id="mcu_1",
            ),
            OperationStep(
                step_id="s2",
                description="Poll sensor_1 current",
                target_node_id="sensor_1",
                depends_on=["s1"],
                timing={"period_ms": 20, "source": "best_practice"},
            ),
        ],
    )


class TestOperationsChecker:
    def test_valid_sequence_passes(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        result = validate_operations_collect(_refined_sequence(), project, manifests)
        assert result.valid is True
        assert result.errors == []

    def test_unknown_node_reference_fails(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        seq = _refined_sequence()
        seq.steps[1].target_node_id = "ghost_node"
        result = validate_operations_collect(seq, project, manifests)
        assert result.valid is False
        assert any(e.rule == "check_node_references" for e in result.errors)

    def test_dependency_cycle_fails(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(step_id="a", description="A", depends_on=["b"]),
                OperationStep(step_id="b", description="B", depends_on=["a"]),
            ],
        )
        result = validate_operations_collect(seq, project, manifests)
        assert result.valid is False
        assert any(e.rule == "check_dependency_integrity" for e in result.errors)

    def test_boot_order_warning(self):
        project = _valid_project_state()
        manifests = mock_manifests()
        seq = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(
                    step_id="s1",
                    description="Poll sensor_1",
                    target_node_id="sensor_1",
                ),
                OperationStep(step_id="s2", description="Enable power rail"),
            ],
        )
        result = validate_operations_collect(seq, project, manifests)
        assert any(e.rule == "check_boot_order" for e in result.errors)
