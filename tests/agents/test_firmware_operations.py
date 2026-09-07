"""Firmware generation with operations sequence integration."""

from pathlib import Path

import pytest

from eda_platform.agents.firmware_engineer import FirmwareEngineerError, generate_firmware
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence, TimingConstraint
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def _operations() -> OperationsSequence:
    return OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="s1",
                description="Enable power rail",
                timing=TimingConstraint(delay_ms=100, source="best_practice"),
            ),
        ],
    )


class TestFirmwareWithOperations:
    def test_requires_operations_approval_when_operations_provided(self):
        with pytest.raises(FirmwareEngineerError, match="operations not approved"):
            generate_firmware(
                _valid_project_state(),
                mock_manifests(),
                approved=True,
                operations=_operations(),
                operations_approved=False,
            )

    def test_generates_docs_and_boot_delays(self, tmp_path: Path):
        result = generate_firmware(
            _valid_project_state(),
            mock_manifests(),
            approved=True,
            operations=_operations(),
            operations_approved=True,
            output_root=tmp_path,
        )
        assert "OPERATING_PROCEDURE.md" in result.files_written
        assert "BRINGUP_CHECKLIST.md" in result.files_written
        main_c = (tmp_path / "valid_i2c_wiring" / "main.c").read_text()
        assert "usleep(100000)" in main_c
