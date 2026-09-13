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

    def test_non_boot_runtime_delay_is_not_baked_into_main(self, tmp_path: Path):
        """Regression: a runtime pause (e.g. before reversing motor
        direction, or an estop-release safety delay) must NOT be emitted as
        a one-shot delay in main()'s boot sequence — main() only runs once
        at startup, so a delay that belongs to a recurring runtime action
        would silently execute once at boot and never again, producing
        firmware that does not match the operations sequence.
        """
        ops = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.TIMED,
            steps=[
                OperationStep(
                    step_id="s1",
                    description="Enable power rail",
                    timing=TimingConstraint(delay_ms=100, source="best_practice"),
                ),
                OperationStep(
                    step_id="s2",
                    description="Pause before reversing motor direction",
                    timing=TimingConstraint(delay_ms=500, source="best_practice"),
                ),
                OperationStep(
                    step_id="s3",
                    description="On estop release, wait before resuming",
                    timing=TimingConstraint(delay_ms=1000, source="best_practice"),
                ),
            ],
        )
        result = generate_firmware(
            _valid_project_state(),
            mock_manifests(),
            approved=True,
            operations=ops,
            operations_approved=True,
            output_root=tmp_path,
        )
        main_c = (tmp_path / "valid_i2c_wiring" / "main.c").read_text()
        assert "usleep(100000)" in main_c, "genuine boot delay must still be emitted"
        assert "usleep(500000)" not in main_c, (
            "motor-direction runtime pause must not be baked into the one-time boot sequence"
        )
        assert "usleep(1000000)" not in main_c, (
            "estop-release runtime delay must not be baked into the one-time boot sequence"
        )
        assert "one-shot delays" in result.message.lower()
        runtime_path = tmp_path / "valid_i2c_wiring" / "runtime" / "ops_interpreter.c"
        if runtime_path.is_file():
            runtime_c = runtime_path.read_text()
            assert "usleep(500000)" not in runtime_c
            assert "usleep(1000000)" not in runtime_c

    def test_runtime_period_and_hal_emit(self, tmp_path: Path):
        ops = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.TIMED,
            steps=[
                OperationStep(
                    step_id="run2",
                    description="Log bus current every second",
                    hal_call="hal_sensor_read()",
                    target_node_id="sensor_1",
                    timing=TimingConstraint(period_ms=1000),
                ),
            ],
        )
        result = generate_firmware(
            _valid_project_state(),
            mock_manifests(),
            approved=True,
            operations=ops,
            operations_approved=True,
            output_root=tmp_path,
        )
        runtime_c = (tmp_path / "valid_i2c_wiring" / "runtime" / "ops_interpreter.c").read_text()
        main_c = (tmp_path / "valid_i2c_wiring" / "main.c").read_text()
        assert "1000" in runtime_c
        assert "CLOCK_MONOTONIC" in runtime_c
        assert "hal_sensor_1_read_current_ma" in runtime_c
        assert "task_operations_runtime" in main_c
        assert "ops_runtime_" not in (
            tmp_path / "valid_i2c_wiring" / "tasks" / "task_sensor_poll.c"
        ).read_text()

    def test_depends_on_emitted_step_order(self, tmp_path: Path):
        ops = OperationsSequence(
            project_id="valid_i2c_wiring",
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
        generate_firmware(
            _valid_project_state(),
            mock_manifests(),
            approved=True,
            operations=ops,
            operations_approved=True,
            output_root=tmp_path,
        )
        runtime_c = (tmp_path / "valid_i2c_wiring" / "runtime" / "ops_interpreter.c").read_text()
        assert runtime_c.find('"a"') < runtime_c.find('"b"')
        assert "ops_run_0" in runtime_c and "ops_run_1" in runtime_c

    def test_condition_degrade_in_message(self, tmp_path: Path):
        ops = OperationsSequence(
            project_id="valid_i2c_wiring",
            fidelity=FidelityLevel.TIMED,
            steps=[
                OperationStep(
                    step_id="guard",
                    description="Poll when safe",
                    condition="estop released",
                    target_node_id="sensor_1",
                    hal_call="hal_sensor_read()",
                    timing=TimingConstraint(period_ms=1000),
                ),
            ],
        )
        result = generate_firmware(
            _valid_project_state(),
            mock_manifests(),
            approved=True,
            operations=ops,
            operations_approved=True,
            output_root=tmp_path,
        )
        assert "condition" in result.message.lower()
