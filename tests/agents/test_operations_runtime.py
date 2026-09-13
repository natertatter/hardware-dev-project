"""Tests for operations → runtime firmware plan."""

import pytest

from eda_platform.agents.firmware_engineer.operations_runtime import (
    boot_delay_steps,
    build_runtime_plan,
    partition_step_ids,
)
from eda_platform.agents.operations_refiner.best_practices import is_boot_step
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence, TimingConstraint
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def _sensors():
    project = _valid_project_state()
    from eda_platform.agents.firmware_engineer import plan_from_project

    plan = plan_from_project(project, mock_manifests())
    from eda_platform.agents.firmware_engineer.codegen.emitter import _sensor_nodes

    return _sensor_nodes(plan, project, mock_manifests())


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
    plan, notes = build_runtime_plan(ops, _sensors())
    assert boot == [(100, "Enable power rail")]
    assert plan.periodic_steps == []
    assert notes.deferred_delay_step_ids == ["s2"]


def test_boot_step_with_hal_call_not_periodic():
    ops = OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="boot1",
                description="Enable power rail before sensors",
                hal_call="hal_power_enable()",
                timing=TimingConstraint(delay_ms=100),
            ),
            OperationStep(
                step_id="run1",
                description="Pause before reversing motor direction",
                timing=TimingConstraint(delay_ms=500),
            ),
            OperationStep(
                step_id="run2",
                description="Log bus current every second",
                hal_call="hal_sensor_read()",
                target_node_id="sensor_1",
                timing=TimingConstraint(period_ms=1000),
            ),
        ],
    )
    boot_ids, periodic_ids, deferred_ids, _ = partition_step_ids(ops, _sensors())
    assert "boot1" in boot_ids
    assert "boot1" not in periodic_ids
    assert "run2" in periodic_ids
    assert "run1" in deferred_ids


def test_partition_covers_all_steps():
    ops = OperationsSequence(
        project_id="p",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(step_id="a", description="Enable power", timing=TimingConstraint(delay_ms=10)),
            OperationStep(
                step_id="b",
                description="Poll sensor",
                target_node_id="sensor_1",
                hal_call="hal_sensor_1_read_current_ma",
                timing=TimingConstraint(period_ms=50),
            ),
            OperationStep(
                step_id="c",
                description="Pause before reversing motor",
                timing=TimingConstraint(delay_ms=200),
            ),
        ],
    )
    boot_ids, periodic_ids, deferred_ids, conditioned_ids = partition_step_ids(ops, _sensors())
    all_ids = {s.step_id for s in ops.steps}
    assigned = boot_ids | periodic_ids | deferred_ids | conditioned_ids
    assert assigned <= all_ids
    assert "a" in boot_ids
    assert "b" in periodic_ids
    assert "c" in deferred_ids


@pytest.mark.parametrize(
    "delay_ms,period_ms,hal_call,boot_word,expected_bucket",
    [
        (100, None, None, True, "boot"),
        (500, None, None, False, "deferred"),
        (None, 1000, "hal_sensor_read()", False, "periodic"),
    ],
)
def test_step_classification_matrix(delay_ms, period_ms, hal_call, boot_word, expected_bucket):
    desc = "Enable power rail" if boot_word else "Poll sensor current"
    timing_kwargs = {}
    if delay_ms is not None:
        timing_kwargs["delay_ms"] = delay_ms
    if period_ms is not None:
        timing_kwargs["period_ms"] = period_ms
    step = OperationStep(
        step_id="x",
        description=desc,
        hal_call=hal_call,
        target_node_id="sensor_1" if expected_bucket == "periodic" else None,
        timing=TimingConstraint(**timing_kwargs) if timing_kwargs else None,
    )
    ops = OperationsSequence(project_id="p", fidelity=FidelityLevel.TIMED, steps=[step])
    boot_ids, periodic_ids, deferred_ids, _ = partition_step_ids(ops, _sensors())
    if expected_bucket == "boot":
        assert "x" in boot_ids
    elif expected_bucket == "deferred":
        assert "x" in deferred_ids
    elif expected_bucket == "periodic":
        assert "x" in periodic_ids


def test_depends_on_orders_periodic_steps():
    ops = OperationsSequence(
        project_id="p",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="b",
                description="Poll sensor",
                target_node_id="sensor_1",
                hal_call="hal_sensor_read()",
                timing=TimingConstraint(period_ms=500),
                depends_on=["a"],
            ),
            OperationStep(
                step_id="a",
                description="Poll sensor baseline",
                target_node_id="sensor_1",
                hal_call="hal_sensor_read()",
                timing=TimingConstraint(period_ms=1000),
            ),
        ],
    )
    plan, _ = build_runtime_plan(ops, _sensors())
    assert [s.step_id for s in plan.periodic_steps] == ["a", "b"]


def test_condition_steps_reported_not_emitted():
    ops = OperationsSequence(
        project_id="p",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="guard",
                description="Poll sensor when estop released",
                condition="estop released",
                target_node_id="sensor_1",
                hal_call="hal_sensor_read()",
                timing=TimingConstraint(period_ms=1000),
            ),
        ],
    )
    plan, notes = build_runtime_plan(ops, _sensors())
    assert plan.periodic_steps == []
    assert notes.conditioned_step_ids == ["guard"]
