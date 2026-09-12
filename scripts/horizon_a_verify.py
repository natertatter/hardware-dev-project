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


def _step(name: str) -> None:
    print(f"\n==> {name}")


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def verify_project_api() -> None:
    _step("Project persistence API")
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from fastapi.testclient import TestClient

    from eda_platform.api.main import app

    client = TestClient(app)
    listed = client.get("/api/v1/projects")
    if listed.status_code != 200:
        _fail(f"GET /projects returned {listed.status_code}")
    ids = listed.json().get("project_ids", [])
    if DEFAULT_PROJECT not in ids:
        _fail(f"{DEFAULT_PROJECT} not in project list: {ids}")
    schematic = client.get(f"/api/v1/projects/{DEFAULT_PROJECT}/schematic")
    if schematic.status_code != 200:
        _fail(f"GET schematic for {DEFAULT_PROJECT} returned {schematic.status_code}")
    print(f"OK — projects API lists {DEFAULT_PROJECT} ({len(ids)} project(s))")


def verify_pipeline(write_firmware: bool, output_root: Path | None) -> None:
    _step(f"Pipeline for {DEFAULT_PROJECT}")
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from eda_platform.agents.firmware_engineer import generate_firmware
    from eda_platform.agents.logic_checker import validate_project_collect
    from eda_platform.agents.operations_checker.runner import validate_operations_collect
    from eda_platform.api.manifest_loader import load_all_manifests
    from eda_platform.api.project_loader import load_operations_master, load_project_state

    schematic_path = REPO_ROOT / "projects" / DEFAULT_PROJECT / "schematic.json"
    if not schematic_path.is_file():
        _fail(f"missing {schematic_path}")

    project = load_project_state(DEFAULT_PROJECT)
    if project is None:
        _fail("could not load project state")
    manifests = load_all_manifests()

    logic = validate_project_collect(project, manifests)
    if not logic.valid:
        _fail(f"logic checker: {logic.errors[0].message}")

    operations = load_operations_master(DEFAULT_PROJECT)
    if operations is not None:
        ops = validate_operations_collect(operations, project, manifests)
        if not ops.valid:
            _fail(f"operations checker: {ops.errors[0].message}")
        print("OK — operations master validated")
    else:
        print("SKIP — no operations master (optional)")

    if not write_firmware:
        print("OK — validate-only (use --write-firmware to generate binaries)")
        return

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
        _fail(result.message or "firmware generation failed")

    project_dir = out / result.project_id
    print(f"OK — firmware written to {project_dir}")
    print(f"     files: {', '.join(result.files_written[:5])}{'…' if len(result.files_written) > 5 else ''}")

    if shutil.which("gcc") and shutil.which("make"):
        _step("Compile generated firmware (host gcc)")
        proc = subprocess.run(
            ["make", "-C", str(project_dir)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(proc.stdout)
            print(proc.stderr, file=sys.stderr)
            _fail("make failed")
        print("OK — make succeeded")
    else:
        print("SKIP — gcc/make not on PATH (Pi cross-compile not required for this check)")


def verify_live_api(base_url: str) -> None:
    _step(f"Live API at {base_url}")
    import urllib.error
    import urllib.request

    health_url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            body = json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError) as exc:
        _fail(f"cannot reach {health_url}: {exc}")
    if body.get("status") != "ok":
        _fail(f"unexpected health payload: {body}")

    projects_url = f"{base_url.rstrip('/')}/api/v1/projects"
    with urllib.request.urlopen(projects_url, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    if DEFAULT_PROJECT not in data.get("project_ids", []):
        _fail(f"{DEFAULT_PROJECT} not listed by live API")
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
    args = parser.parse_args()

    print("Horizon A verify — host-side smoke")
    verify_project_api()
    verify_pipeline(args.write_firmware, args.output_root)
    if args.live_api:
        verify_live_api(args.live_api)
    print("\nAll Horizon A host checks passed.")


if __name__ == "__main__":
    main()
