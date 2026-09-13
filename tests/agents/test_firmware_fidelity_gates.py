"""Codegen fidelity gates (Horizon B2)."""

from pathlib import Path

import pytest

from eda_platform.agents.firmware_engineer import FirmwareEngineerError, generate_firmware
from eda_platform.schemas import (
    FidelityLevel,
    OpenQuestion,
    OperationStep,
    OperationsSequence,
)
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def test_executable_blocked_by_open_questions():
    ops = OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.EXECUTABLE,
        steps=[OperationStep(step_id="s1", description="Poll sensor")],
        open_questions=[OpenQuestion(question_id="q1", text="Which sensor?")],
    )
    with pytest.raises(FirmwareEngineerError, match="open questions"):
        generate_firmware(
            _valid_project_state(),
            mock_manifests(),
            approved=True,
            operations=ops,
            operations_approved=True,
        )


def test_timed_open_questions_degrade_note(tmp_path: Path):
    ops = OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.TIMED,
        steps=[OperationStep(step_id="s1", description="Poll sensor")],
        open_questions=[OpenQuestion(question_id="q1", text="Which sensor?")],
    )
    result = generate_firmware(
        _valid_project_state(),
        mock_manifests(),
        approved=True,
        operations=ops,
        operations_approved=True,
        output_root=tmp_path,
    )
    assert "open question" in result.message.lower()


def test_executable_blocked_by_needs_refinement():
    ops = OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.EXECUTABLE,
        steps=[
            OperationStep(
                step_id="s1",
                description="Poll sensor",
                needs_refinement=True,
            )
        ],
    )
    with pytest.raises(FirmwareEngineerError, match="needs_refinement"):
        generate_firmware(
            _valid_project_state(),
            mock_manifests(),
            approved=True,
            operations=ops,
            operations_approved=True,
        )
