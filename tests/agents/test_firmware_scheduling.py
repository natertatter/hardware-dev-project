"""Tests for firmware scheduling plan generation."""

from eda_platform.agents.firmware_engineer import plan_from_project
from eda_platform.agents.firmware_engineer.models import ExecutionTier
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def test_valid_i2c_project_produces_sensor_poll_task():
    plan = plan_from_project(_valid_project_state(), mock_manifests())

    assert plan.platform == "rpi4"
    assert len(plan.bus_locks) == 1
    assert plan.bus_locks[0].i2c_device_path == "/dev/i2c-1"
    assert "sensor_1" in plan.bus_locks[0].nodes

    poll = next(t for t in plan.tasks if t.task_id == "task_sensor_poll")
    assert poll.tier == ExecutionTier.T1
    assert poll.period_ms == 20
    assert "hal_i2c_bus_0" in poll.hal_modules
    assert "hal_sensor_1" in poll.hal_modules
