"""Quality gate for the project.

The same script runs on a developer machine, inside the Claude Code hooks and
in GitHub Actions, so "green locally" means "green in CI".

Usage:
    uv run python scripts/gate.py                 # full gate
    uv run python scripts/gate.py --stage tests   # red phase: tests exist, code not yet

Stages:
    tests: ruff + black + spec traceability.
    full:  everything in "tests", then pyrefly, svelte-check and the vite build
           of web/, then pytest (browser tests included).

Exit codes:
    0: every check passed.
    1: at least one check failed.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = PROJECT_ROOT / "specs"
TESTS_DIR = PROJECT_ROOT / "tests"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

# A spec file is named NNN-short-name.md, for example 001-slugify.md.
SPEC_FILE_PATTERN = re.compile(r"^(\d{3})-.+\.md$")
# An acceptance criterion is a bullet that starts with a bold id: - **AC-1** ...
CRITERION_PATTERN = re.compile(r"^\s*[-*]\s+\*\*AC-(\d+)\*\*", re.MULTILINE)
# The spec status lives in the front matter: status: draft | approved | done
STATUS_PATTERN = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)
# A test is linked to a criterion by its name: def test_ac1_lowercases_text(...)
TEST_FUNCTION_PATTERN = re.compile(r"^\s*def\s+test_ac(\d+)_", re.MULTILINE)

STATIC_STEPS: list[tuple[str, list[str]]] = [
    ("ruff (lint)", ["ruff", "check", "."]),
    ("black (format)", ["black", "--check", "--diff", "--quiet", "."]),
]
WEB_DIR = PROJECT_ROOT / "web"

# pytest comes after the web build: browser tests load the built client.
RUNTIME_STEPS: list[tuple[str, list[str]]] = [
    ("pyrefly (types)", ["pyrefly", "check"]),
    ("svelte-check (web types)", ["npm", "--prefix", "web", "run", "check"]),
    ("vite build (web)", ["npm", "--prefix", "web", "run", "build"]),
    # gate_browsers leaves out the browser engines that are not installed, with
    # a warning; in CI it fails instead (see scripts/gate_browsers.py).
    ("pytest (tests)", ["pytest", "--quiet", "-p", "gate_browsers"]),
]


def run_step(step_name: str, command: list[str]) -> bool:
    """Run one external tool and report whether it succeeded.

    Args:
        step_name: Label printed before the tool output.
        command: Executable name followed by its arguments.

    Returns:
        True when the tool exited with code 0.
    """
    print(f"\n=== {step_name} ===", flush=True)

    executable_path = shutil.which(command[0])
    if executable_path is None:
        print(
            f"FAIL: '{command[0]}' is not installed. "
            "Run: uv sync (Python tools), or install Node.js LTS (npm)."
        )
        return False

    if command[0] == "npm" and not (WEB_DIR / "node_modules").is_dir():
        print("FAIL: the web dependencies are not installed. Run: npm --prefix web ci")
        return False

    full_command = [executable_path, *command[1:]]
    # scripts/ on the import path, so that pytest can load the gate_browsers plugin.
    environment = dict(os.environ)
    python_path = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(SCRIPTS_DIR), python_path) if part
    )
    completed = subprocess.run(
        full_command, cwd=PROJECT_ROOT, env=environment, check=False
    )
    if completed.returncode != 0:
        print(f"FAIL: {step_name} exited with code {completed.returncode}")
        return False

    print(f"OK: {step_name}")
    return True


def find_spec_files() -> list[Path]:
    """Return every numbered spec file, sorted by name."""
    if not SPECS_DIR.is_dir():
        return []

    spec_files: list[Path] = []
    for candidate in sorted(SPECS_DIR.iterdir()):
        if SPEC_FILE_PATTERN.match(candidate.name):
            spec_files.append(candidate)
    return spec_files


def read_criterion_ids(spec_text: str) -> set[int]:
    """Return the acceptance criterion numbers declared in a spec."""
    criterion_ids: set[int] = set()
    for match in CRITERION_PATTERN.finditer(spec_text):
        criterion_ids.add(int(match.group(1)))
    return criterion_ids


def read_status(spec_text: str) -> str:
    """Return the status declared in the spec front matter, or "draft"."""
    match = STATUS_PATTERN.search(spec_text)
    if match is None:
        return "draft"
    return match.group(1).lower()


def read_tested_criterion_ids(spec_number: str) -> tuple[set[int], int]:
    """Return the criterion numbers covered by the tests of one spec.

    Args:
        spec_number: Three-digit spec number, for example "001".

    Returns:
        The covered criterion numbers and the number of test files found.
    """
    tested_ids: set[int] = set()
    test_files = sorted(TESTS_DIR.glob(f"test_spec_{spec_number}*.py"))
    for test_file in test_files:
        test_text = test_file.read_text(encoding="utf-8")
        for match in TEST_FUNCTION_PATTERN.finditer(test_text):
            tested_ids.add(int(match.group(1)))
    return tested_ids, len(test_files)


def check_one_spec(spec_file: Path) -> list[str]:
    """Check that the tests of one spec line up with its acceptance criteria.

    Args:
        spec_file: Path of the spec to check.

    Returns:
        One human-readable problem per line. Empty when the spec is fine.
    """
    name_match = SPEC_FILE_PATTERN.match(spec_file.name)
    if name_match is None:
        return []
    spec_number = name_match.group(1)
    spec_label = f"specs/{spec_file.name}"
    test_glob = f"tests/test_spec_{spec_number}*.py"

    spec_text = spec_file.read_text(encoding="utf-8")
    status = read_status(spec_text)
    criterion_ids = read_criterion_ids(spec_text)
    tested_ids, test_file_count = read_tested_criterion_ids(spec_number)

    problems: list[str] = []

    if status != "draft" and not criterion_ids:
        problems.append(
            f"{spec_label}: status is '{status}' but no acceptance criterion "
            "was found (expected bullets like '- **AC-1** ...')."
        )

    if test_file_count == 0:
        if status == "done":
            problems.append(
                f"{spec_label}: status is 'done' but {test_glob} is missing."
            )
        # A spec without tests yet is normal before the test-writer has run.
        return problems

    for criterion_id in sorted(criterion_ids - tested_ids):
        problems.append(
            f"{spec_label}: AC-{criterion_id} has no test "
            f"(expected 'def test_ac{criterion_id}_...' in {test_glob})."
        )

    for criterion_id in sorted(tested_ids - criterion_ids):
        problems.append(
            f"{test_glob}: test_ac{criterion_id}_... points to AC-{criterion_id}, "
            f"which does not exist in {spec_label}."
        )

    return problems


def check_traceability() -> bool:
    """Check that every acceptance criterion has a test, for every spec.

    Returns:
        True when no problem was found.
    """
    print("\n=== spec traceability ===", flush=True)

    all_problems: list[str] = []
    spec_files = find_spec_files()
    for spec_file in spec_files:
        all_problems.extend(check_one_spec(spec_file))

    if all_problems:
        for problem in all_problems:
            print(f"FAIL: {problem}")
        return False

    print(f"OK: spec traceability ({len(spec_files)} spec file(s) checked)")
    return True


def parse_arguments() -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description="Run the project quality gate.")
    parser.add_argument(
        "--stage",
        choices=["tests", "full"],
        default="full",
        help="'tests' skips pyrefly and pytest (red phase). Default: full.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the requested stage and return the process exit code."""
    arguments = parse_arguments()

    results: list[bool] = []
    for step_name, command in STATIC_STEPS:
        results.append(run_step(step_name, command))
    results.append(check_traceability())

    if arguments.stage == "full":
        for step_name, command in RUNTIME_STEPS:
            results.append(run_step(step_name, command))

    failed_count = results.count(False)
    print()
    if failed_count > 0:
        print(f"GATE FAILED ({arguments.stage}): {failed_count} check(s) failed.")
        return 1

    print(f"GATE PASSED ({arguments.stage}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
