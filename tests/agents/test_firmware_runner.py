"""Integration tests for firmware generation runner."""

from pathlib import Path

from eda_platform.agents.firmware_engineer import generate_firmware
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def test_generate_firmware_writes_output(tmp_path: Path):
    result = generate_firmware(
        _valid_project_state(),
        mock_manifests(),
        approved=True,
        output_root=tmp_path,
    )
    assert result.success
    assert result.project_id == "valid_i2c_wiring"
    assert (tmp_path / "valid_i2c_wiring" / "main.c").exists()
    assert "hal/hal_sensor_1.c" in result.files_written
