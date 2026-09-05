"""Tests for firmware C code generation."""

from pathlib import Path

from eda_platform.agents.firmware_engineer.codegen.emitter import emit_firmware_tree, generate_source_files
from eda_platform.agents.firmware_engineer import plan_from_project
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def test_generate_source_files_contains_expected_artifacts():
    project = _valid_project_state()
    manifests = mock_manifests()
    plan = plan_from_project(project, manifests)
    files = generate_source_files(project, manifests, plan)

    assert "main.c" in files
    assert "Makefile" in files
    assert "platform/board_config.h" in files
    assert "hal/hal_i2c_bus_0.c" in files
    assert "hal/hal_sensor_1.c" in files
    assert "tasks/task_sensor_poll.c" in files
    assert "pthread_create" in files["main.c"]
    assert "pthread_mutex" in files["hal/hal_i2c_bus_0.c"]
    assert "/dev/i2c-1" in files["platform/board_config.h"]


def test_emit_firmware_tree_writes_files(tmp_path: Path):
    project = _valid_project_state()
    manifests = mock_manifests()
    plan = plan_from_project(project, manifests)

    written = emit_firmware_tree(tmp_path, project, manifests, plan)
    assert len(written) >= 7
    assert (tmp_path / "main.c").is_file()
    assert (tmp_path / "hal" / "hal_sensor_1.c").is_file()
