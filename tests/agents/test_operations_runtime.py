"""Tests for operations → runtime firmware plan."""

from eda_platform.agents.firmware_engineer.operations_runtime import (
    boot_delay_steps,
    build_runtime_plan,
)
from eda_platform.agents.operations_refiner.best_practices import is_boot_step
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence, TimingConstraint


def test_boot_vs_runtime_delay_partition():
    ops = OperationsSequence(
        project_id="p",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="s1",
                description="Enable power rail",
                timing=TimingConstraint(delay_ms=100),
            ),
            OperationStep(
                step_id="s2",
                description="Pause before reversing motor direction",
                timing=TimingConstraint(delay_ms=500),
            ),
        ],
    )
    assert is_boot_step(ops.steps[0].description)
    boot = boot_delay_steps(ops)
    plan = build_runtime_plan(ops)
    assert boot == [(100, "Enable power rail")]
    assert len(plan.startup_delays) == 1
    assert plan.startup_delays[0].step_id == "s2"
