"""Actually compile the generated firmware with gcc — not just check it's valid Python strings.

This is the class of bug that unit tests over the generator can't catch:
the templates render syntactically valid-looking f-strings, but only a
real compiler proves the emitted C compiles without warnings. Skips
gracefully if gcc/make aren't on PATH (e.g. minimal CI images).
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from eda_platform.agents.firmware_engineer import generate_firmware
from eda_platform.schemas import FidelityLevel, OperationStep, OperationsSequence, TimingConstraint
from tests.data.mock_data import mock_manifests
from tests.test_logic_checker import _valid_project_state


def _runtime_operations() -> OperationsSequence:
    return OperationsSequence(
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


def _hostile_description_operations() -> OperationsSequence:
    return OperationsSequence(
        project_id="valid_i2c_wiring",
        fidelity=FidelityLevel.TIMED,
        steps=[
            OperationStep(
                step_id="evil",
                description=r'Ramp to 100% then log %s and %d values',
                timing=TimingConstraint(period_ms=1000),
            ),
            OperationStep(
                step_id="evil2",
                description=r"Wait for path C:\dev\estop release",
                timing=TimingConstraint(delay_ms=500),
            ),
        ],
    )

_HAS_TOOLCHAIN = shutil.which("gcc") is not None and shutil.which("make") is not None

pytestmark = pytest.mark.skipif(
    not _HAS_TOOLCHAIN, reason="gcc/make not available in this environment"
)


@pytest.mark.parametrize(
    "operations",
    [None, _runtime_operations(), _hostile_description_operations()],
    ids=["no_ops", "runtime_ops", "hostile_descriptions"],
)
def test_generated_firmware_compiles_with_werror(tmp_path: Path, operations):
    """Build every generated .c file with -Wall -Wextra -Werror.

    Regression target: task_sensor_poll.c previously ignored the return
    value of read() on the timerfd, which -Wextra flags as
    -Wunused-result. That warning would fail any CI configured with
    -Werror (a common embedded-firmware convention) even though the
    Python-level unit tests all passed.
    """
    result = generate_firmware(
        _valid_project_state(),
        mock_manifests(),
        approved=True,
        operations=operations,
        operations_approved=operations is not None,
        output_root=tmp_path,
    )
    project_dir = tmp_path / result.project_id

    c_files = sorted(project_dir.rglob("*.c"))
    assert c_files, "expected at least one generated .c file"

    for c_file in c_files:
        proc = subprocess.run(
            [
                "gcc",
                "-Wall",
                "-Wextra",
                "-Werror",
                "-O2",
                "-pthread",
                f"-I{project_dir}",
                "-c",
                str(c_file),
                "-o",
                "/dev/null",
            ],
            cwd=project_dir,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"{c_file.relative_to(project_dir)} failed to compile cleanly:\n"
            f"{proc.stdout}\n{proc.stderr}"
        )


def test_generated_firmware_links_and_fails_gracefully_without_i2c_device(tmp_path: Path):
    """End-to-end: make the binary, run it, confirm a clean non-zero exit
    (no crash/segfault) when /dev/i2c-1 doesn't exist — the expected
    outcome on any non-Pi dev machine, including this test sandbox."""
    result = generate_firmware(
        _valid_project_state(),
        mock_manifests(),
        approved=True,
        output_root=tmp_path,
    )
    project_dir = tmp_path / result.project_id

    make_proc = subprocess.run(
        ["make"], cwd=project_dir, capture_output=True, text=True
    )
    assert make_proc.returncode == 0, f"make failed:\n{make_proc.stdout}\n{make_proc.stderr}"

    binaries = list(project_dir.glob("*_firmware"))
    assert len(binaries) == 1
    binary = binaries[0]

    # Merge stdout+stderr like a terminal or systemd journal would — this is
    # the only way to observe true chronological interleaving between the
    # line-buffered stdout banner and the unbuffered stderr fatal error.
    run_proc = subprocess.run(
        [str(binary)],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=5,
    )
    combined = run_proc.stdout

    # Expect a clean, handled failure (I2C device absent) — not a crash.
    assert run_proc.returncode == 1
    assert "I2C bus init failed" in combined

    # Regression check: without setvbuf(stdout, NULL, _IOLBF, 0), stdout is
    # fully buffered when not attached to a TTY, so the startup banner
    # would only flush at process exit — AFTER the unbuffered stderr
    # error — making logs look like the program errored before starting.
    banner_idx = combined.find("EDA Platform firmware")
    error_idx = combined.find("I2C bus init failed")
    assert banner_idx != -1 and error_idx != -1
    assert banner_idx < error_idx, (
        "startup banner must appear before the fatal error in combined "
        "stdout+stderr output — check setvbuf(stdout, ..., _IOLBF, ...) in main.c"
    )
