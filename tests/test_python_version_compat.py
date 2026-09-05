"""Guard against syntax that violates the package's declared minimum Python version.

Regression coverage: `codegen/templates.py` once used backslash escapes
inside f-string `{...}` expressions (e.g. `f'{"\\"quoted\\"" if cond else ""}'`),
which is only legal on Python 3.12+ (PEP 701). `pyproject.toml` declares
`requires-python = ">=3.11"`, so that code raised `SyntaxError` at import
time on 3.11 even though every test passed in this (3.12) sandbox — the bug
was invisible to the test suite until parsed with the older grammar.
"""

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _declared_min_python_version() -> tuple[int, int]:
    pyproject = (REPO_ROOT / "pyproject.toml").read_text()
    match = re.search(r'requires-python\s*=\s*">=\s*(\d+)\.(\d+)"', pyproject)
    assert match, "could not find requires-python in pyproject.toml"
    return int(match.group(1)), int(match.group(2))


def _all_source_files() -> list[Path]:
    files = list((REPO_ROOT / "src").rglob("*.py"))
    files += list((REPO_ROOT / "tests").rglob("*.py"))
    return [f for f in files if "__pycache__" not in f.parts]


def test_all_python_files_parse_under_declared_minimum_version():
    min_version = _declared_min_python_version()
    failures: list[str] = []

    for path in _all_source_files():
        source = path.read_text()
        try:
            ast.parse(source, feature_version=min_version)
        except SyntaxError as exc:
            failures.append(f"{path.relative_to(REPO_ROOT)}: {exc}")

    assert not failures, (
        f"Files use syntax newer than the declared minimum Python "
        f"{min_version[0]}.{min_version[1]} (see pyproject.toml requires-python):\n"
        + "\n".join(failures)
    )
