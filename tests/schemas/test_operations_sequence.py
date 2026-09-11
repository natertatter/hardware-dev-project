"""Schema validation tests for operations sequence models."""

import pytest

from eda_platform.schemas import (
    FidelityLevel,
    OperationStep,
    OperationsSequence,
    ProvenanceSource,
    TimingConstraint,
)


class TestOperationsSequenceSchema:
    def test_narrative_only_sequence(self):
        seq = OperationsSequence(
            project_id="demo",
            fidelity=FidelityLevel.NARRATIVE,
            narrative="Boot then poll sensor.",
        )
        assert seq.steps == []
        assert seq.narrative is not None

    def test_steps_sequence(self):
        seq = OperationsSequence(
            project_id="demo",
            fidelity=FidelityLevel.STEPS,
            steps=[
                OperationStep(step_id="s1", description="Enable power"),
            ],
        )
        assert len(seq.steps) == 1

    def test_requires_steps_or_narrative(self):
        with pytest.raises(ValueError, match="at least one step or narrative"):
            OperationsSequence(project_id="demo", fidelity=FidelityLevel.NARRATIVE)

    def test_timing_constraint(self):
        tc = TimingConstraint(
            period_ms=20,
            source=ProvenanceSource.BEST_PRACTICE,
            note="I2C poll default",
        )
        assert tc.period_ms == 20

    def test_demo_robot_master_fixture(self):
        from pathlib import Path

        path = Path("projects/demo_robot/operations/master.json")
        seq = OperationsSequence.model_validate_json(path.read_text())
        assert seq.project_id == "demo_robot"
        assert seq.fidelity == FidelityLevel.NARRATIVE
