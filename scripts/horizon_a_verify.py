#!/usr/bin/env python3
"""Horizon A host-side verification (no Raspberry Pi required).

Exercises disk-backed demo_robot → validate → operations validate → firmware
generate → optional local compile. Use after pytest/vitest in a dev or CI loop.

Usage:
  python3 scripts/horizon_a_verify.py
  python3 scripts/horizon_a_verify.py --write-firmware
  python3 scripts/horizon_a_verify.py --live-api http://localhost:8000
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROJECT = "demo_robot"


class VerifyError(RuntimeError):
    """Raised when a verification step fails (testable without subprocess)."""


def _step(name: str) -> None:
    print(f"\n==> {name}")


def verify_project_api() -> None:
    _step("Project persistence API")
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from fastapi.testclient import TestClient

    from eda_platform.api.main import app

    client = TestClient(app)
    listed = client.get("/api/v1/projects")
    if listed.status_code != 200:
        raise VerifyError(f"GET /projects returned {listed.status_code}")
    ids = listed.json().get("project_ids", [])
    if DEFAULT_PROJECT not in ids:
        raise VerifyError(f"{DEFAULT_PROJECT} not in project list: {ids}")
    schematic = client.get(f"/api/v1/projects/{DEFAULT_PROJECT}/schematic")
    if schematic.status_code != 200:
        raise VerifyError(f"GET schematic for {DEFAULT_PROJECT} returned {schematic.status_code}")
    print(f"OK — projects API lists {DEFAULT_PROJECT} ({len(ids)} project(s))")


def verify_pipeline(
    write_firmware: bool,
    output_root: Path | None,
    *,
    require_toolchain: bool = False,
) -> bool:
    """Return True if ``make`` ran successfully."""
    _step(f"Pipeline for {DEFAULT_PROJECT}")
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from eda_platform.agents.firmware_engineer import generate_firmware
    from eda_platform.agents.logic_checker import validate_project_collect
    from eda_platform.agents.operations_checker.runner import validate_operations_collect
    from eda_platform.api.manifest_loader import load_all_manifests
    from eda_platform.api.project_loader import load_operations_master, load_project_state

    project = load_project_state(DEFAULT_PROJECT)
    if project is None:
        raise VerifyError("could not load wired project state for demo_robot")
    manifests = load_all_manifests()

    logic = validate_project_collect(project, manifests)
    if not logic.valid:
        raise VerifyError(f"logic checker: {logic.errors[0].message}")

    operations = load_operations_master(DEFAULT_PROJECT)
    if operations is not None:
        ops = validate_operations_collect(operations, project, manifests)
        if not ops.valid:
            raise VerifyError(f"operations checker: {ops.errors[0].message}")
        print("OK — operations master validated")
    else:
        print("SKIP — no operations master (optional)")

    if not write_firmware:
        print("OK — validate-only (use --write-firmware to generate binaries)")
        return False

    out = output_root or (REPO_ROOT / "generated" / "firmware")
    result = generate_firmware(
        project,
        manifests,
        approved=True,
        operations=operations,
        operations_approved=operations is not None,
        output_root=out,
    )
    if not result.success:
        raise VerifyError(result.message or "firmware generation failed")

    project_dir = out / result.project_id
    print(f"OK — firmware written to {project_dir}")
    print(f"     files: {', '.join(result.files_written[:5])}{'…' if len(result.files_written) > 5 else ''}")

    has_toolchain = shutil.which("gcc") is not None and shutil.which("make") is not None
    if not has_toolchain:
        if require_toolchain:
            raise VerifyError("gcc/make required but not on PATH")
        print("SKIP — gcc/make not on PATH (Pi cross-compile not required for this check)")
        return False

    _step("Compile generated firmware (host gcc)")
    proc = subprocess.run(
        ["make", "-C", str(project_dir)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        raise VerifyError("make failed")
    print("OK — make succeeded")
    return True


def verify_live_api(base_url: str) -> None:
    _step(f"Live API at {base_url}")
    import urllib.error
    import urllib.request

    health_url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError) as exc:
        raise VerifyError(f"cannot reach {health_url}: {exc}") from exc
    if body.get("status") != "ok":
        raise VerifyError(f"unexpected health payload: {body}")

    projects_url = f"{base_url.rstrip('/')}/api/v1/projects"
    with urllib.request.urlopen(projects_url, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    if DEFAULT_PROJECT not in data.get("project_ids", []):
        raise VerifyError(f"{DEFAULT_PROJECT} not listed by live API")
    print("OK — live API health and project list")


def main() -> None:
    parser = argparse.ArgumentParser(description="Horizon A host verification")
    parser.add_argument(
        "--write-firmware",
        action="store_true",
        help="Generate firmware under generated/firmware/ (default: validate only)",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override firmware output root (default: repo generated/firmware)",
    )
    parser.add_argument(
        "--live-api",
        metavar="URL",
        default=None,
        help="Also probe a running API (e.g. http://localhost:8000)",
    )
    parser.add_argument(
        "--require-toolchain",
        action="store_true",
        help="Fail if gcc/make are missing when --write-firmware is set",
    )
    args = parser.parse_args()

    try:
        print("Horizon A verify — host-side smoke")
        verify_project_api()
        verify_pipeline(
            args.write_firmware,
            args.output_root,
            require_toolchain=args.require_toolchain,
        )
        if args.live_api:
            verify_live_api(args.live_api)
        print("\nAll Horizon A host checks passed.")
    except VerifyError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
