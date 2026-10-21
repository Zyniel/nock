"""Quality gate for the project.

The same script runs on a developer machine, inside the Claude Code hooks and
in GitHub Actions, so "green locally" means "green in CI".

Usage:
    uv run python scripts/gate.py                 # full gate
    uv run python scripts/gate.py --stage tests   # red phase: tests exist, code not yet
    uv run python scripts/gate.py --browsers all  # browser tests in all three engines

Stages:
    tests: ruff + black + spec traceability.
    full:  everything in "tests", then pyrefly, svelte-check and the vite build
           of web/, then pytest (browser tests included).

Options of the full stage (2026-10-15, so CI can run one job per engine):
    --browsers: the engines of the browser tests, comma-separated, or "all".
        Default: the NOCK_BROWSERS environment variable, else chromium (human
        decision, 2026-10-21: one engine while the design moves; it was
        chromium,webkit). Engines that are not installed are left out with a
        warning, except in CI.
    --tests: "all" (default), "browser" (only the browser tests) or "other"
        (only the tests that run without a browser).
    --skip-static: skip ruff, black, traceability, pyrefly and svelte-check,
        for CI jobs whose static checks run in another job.
    --workers: pytest-xdist workers, "auto" (default, one per CPU) or a
        number; 0 runs everything in one serial pass. The tests marked
        `serial` (scripts/gate_browsers.py) always run after the parallel
        pass, on their own.
    --specs: spec numbers, comma-separated (for example 027,028): the
        browser tests run only for those specs; the static checks and the
        tests without a browser run in full. The quick gate of an agent's
        finish hook (2026-10-16).

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

RUNTIME_STATIC_STEPS: list[tuple[str, list[str]]] = [
    ("pyrefly (types)", ["pyrefly", "check"]),
    ("svelte-check (web types)", ["npm", "--prefix", "web", "run", "check"]),
]
# pytest comes after the web build: browser tests load the built client.
BUILD_STEP: tuple[str, list[str]] = (
    "vite build (web)",
    ["npm", "--prefix", "web", "run", "build"],
)

ENGINE_NAMES: tuple[str, ...] = ("chromium", "firefox", "webkit")
DEFAULT_ENGINES = "chromium"
# The `-m` expression of each --tests choice.
TEST_SELECTIONS: dict[str, str] = {
    "all": "",
    "browser": "browser",
    "other": "not browser",
}
# pytest's exit code when no test was selected.
NO_TESTS_COLLECTED = 5
# A spec number as --specs takes it: three digits, for example 027.
SPEC_NUMBER_PATTERN = re.compile(r"^\d{3}$")


def run_tool(step_name: str, command: list[str]) -> int | None:
    """Run one external tool and return its exit code.

    Args:
        step_name: Label printed before the tool output.
        command: Executable name followed by its arguments.

    Returns:
        The exit code, or None when the tool or its dependencies are missing.
    """
    print(f"\n=== {step_name} ===", flush=True)

    executable_path = shutil.which(command[0])
    if executable_path is None:
        print(
            f"FAIL: '{command[0]}' is not installed. "
            "Run: uv sync (Python tools), or install Node.js LTS (npm)."
        )
        return None

    if command[0] == "npm" and not (WEB_DIR / "node_modules").is_dir():
        print("FAIL: the web dependencies are not installed. Run: npm --prefix web ci")
        return None

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
    return completed.returncode


def run_step(step_name: str, command: list[str]) -> bool:
    """Run one external tool and report whether it succeeded.

    Args:
        step_name: Label printed before the tool output.
        command: Executable name followed by its arguments.

    Returns:
        True when the tool exited with code 0.
    """
    exit_code = run_tool(step_name, command)
    if exit_code is None:
        return False
    if exit_code != 0:
        print(f"FAIL: {step_name} exited with code {exit_code}")
        return False
    print(f"OK: {step_name}")
    return True


def run_pytest_passes(commands: list[tuple[str, list[str]]]) -> bool:
    """Run the pytest passes and report whether they all succeeded.

    A pass that selects no test (pytest's exit code 5) is fine, such as the
    serial pass of a selection without serial tests, as long as one pass ran
    a test.

    Args:
        commands: The passes, with their step names.

    Returns:
        True when every pass passed or selected nothing, and one ran a test.
    """
    all_passed = True
    tests_ran = False
    for step_name, command in commands:
        exit_code = run_tool(step_name, command)
        if exit_code == 0:
            tests_ran = True
            print(f"OK: {step_name}")
        elif exit_code == NO_TESTS_COLLECTED:
            print(f"OK: {step_name} (no test selected)")
        else:
            all_passed = False
            if exit_code is not None:
                print(f"FAIL: {step_name} exited with code {exit_code}")
    if all_passed and not tests_ran:
        print("FAIL: no pytest pass selected a test")
        return False
    return all_passed


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


def parse_engines(engines_text: str) -> list[str]:
    """Return the engines named in a comma-separated list, or all for "all".

    Raises:
        argparse.ArgumentTypeError: When a name is not a browser engine.
    """
    if engines_text.strip() == "all":
        return list(ENGINE_NAMES)
    engines: list[str] = []
    for part in engines_text.split(","):
        engine_name = part.strip()
        if not engine_name:
            continue
        if engine_name not in ENGINE_NAMES:
            raise argparse.ArgumentTypeError(
                f"unknown browser engine '{engine_name}' "
                f"(expected {', '.join(ENGINE_NAMES)} or all)"
            )
        if engine_name not in engines:
            engines.append(engine_name)
    if not engines:
        raise argparse.ArgumentTypeError("no browser engine given")
    return engines


def parse_workers(workers_text: str) -> str:
    """Return the --workers value: "auto" or a number of workers.

    Raises:
        argparse.ArgumentTypeError: When it is neither "auto" nor a number.
    """
    if workers_text == "auto" or workers_text.isdigit():
        return workers_text
    raise argparse.ArgumentTypeError("expected 'auto' or a number of workers")


def parse_specs(specs_text: str) -> list[str]:
    """Return the spec numbers of a comma-separated list, each three digits.

    Raises:
        argparse.ArgumentTypeError: When a part is not a three-digit number.
    """
    specs: list[str] = []
    for part in specs_text.split(","):
        spec_number = part.strip()
        if not spec_number:
            continue
        if not SPEC_NUMBER_PATTERN.match(spec_number):
            raise argparse.ArgumentTypeError(
                f"'{spec_number}' is not a spec number (three digits, e.g. 027)"
            )
        if spec_number not in specs:
            specs.append(spec_number)
    if not specs:
        raise argparse.ArgumentTypeError("no spec number given")
    return specs


def parse_arguments() -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description="Run the project quality gate.")
    parser.add_argument(
        "--stage",
        choices=["tests", "full"],
        default="full",
        help="'tests' skips pyrefly and pytest (red phase). Default: full.",
    )
    parser.add_argument(
        "--browsers",
        type=parse_engines,
        default=os.environ.get("NOCK_BROWSERS") or DEFAULT_ENGINES,
        help="Engines of the browser tests, comma-separated, or 'all'. "
        f"Default: $NOCK_BROWSERS, else {DEFAULT_ENGINES}.",
    )
    parser.add_argument(
        "--tests",
        choices=list(TEST_SELECTIONS),
        default="all",
        help="'browser' or 'other' runs only the tests with or without a "
        "browser. Default: all.",
    )
    parser.add_argument(
        "--skip-static",
        action="store_true",
        help="Skip ruff, black, traceability, pyrefly and svelte-check.",
    )
    parser.add_argument(
        "--workers",
        type=parse_workers,
        default="auto",
        help="pytest-xdist workers: 'auto' (default) or a number; 0 runs "
        "the tests in one serial pass.",
    )
    parser.add_argument(
        "--specs",
        type=parse_specs,
        default=None,
        help="Run the browser tests of these specs only (comma-separated, "
        "e.g. 027,028); the tests without a browser all run.",
    )
    return parser.parse_args()


def join_marks(*expressions: str) -> str:
    """Return the `-m` expression that requires every non-empty expression."""
    parts = [f"({expression})" for expression in expressions if expression]
    return " and ".join(parts)


def pytest_commands(
    engines: list[str], selection: str, workers: str, specs: list[str] | None
) -> list[tuple[str, list[str]]]:
    """Return the pytest runs of the full stage, with their step names.

    Args:
        engines: The engines of the browser tests.
        selection: The `-m` expression of the --tests choice ("" for all).
        workers: The pytest-xdist workers, "auto" or a number ("0": serial).
        specs: The specs whose browser tests run, or None for every spec.

    Returns:
        One run when `workers` is "0", else the parallel run of the tests not
        marked `serial`, then the serial run of the others.
    """
    # gate_browsers marks the tests and leaves out the browser engines that are
    # not installed, with a warning; in CI it fails instead. It also leaves out
    # the browser tests of the specs not in --nock-specs.
    base_command = ["pytest", "--quiet", "-p", "gate_browsers"]
    for engine_name in engines:
        base_command.extend(["--browser", engine_name])
    if specs is not None:
        base_command.extend(["--nock-specs", ",".join(specs)])

    if workers == "0":
        command = list(base_command)
        if selection:
            command.extend(["-m", selection])
        return [("pytest (tests)", command)]

    parallel_command = [*base_command, "-n", workers, "--dist", "worksteal"]
    parallel_command.extend(["-m", join_marks(selection, "not serial")])
    serial_command = [*base_command, "-m", join_marks(selection, "serial")]
    return [
        ("pytest (tests, parallel)", parallel_command),
        ("pytest (tests, serial)", serial_command),
    ]


def main() -> int:
    """Run the requested stage and return the process exit code."""
    arguments = parse_arguments()

    results: list[bool] = []
    run_static = not arguments.skip_static or arguments.stage == "tests"
    if run_static:
        for step_name, command in STATIC_STEPS:
            results.append(run_step(step_name, command))
        results.append(check_traceability())

    if arguments.stage == "full":
        if run_static:
            for step_name, command in RUNTIME_STATIC_STEPS:
                results.append(run_step(step_name, command))
        build_name, build_command = BUILD_STEP
        results.append(run_step(build_name, build_command))
        if results[-1]:
            selection = TEST_SELECTIONS[arguments.tests]
            commands = pytest_commands(
                arguments.browsers, selection, arguments.workers, arguments.specs
            )
            results.append(run_pytest_passes(commands))

    failed_count = results.count(False)
    print()
    if failed_count > 0:
        print(f"GATE FAILED ({arguments.stage}): {failed_count} check(s) failed.")
        return 1

    print(f"GATE PASSED ({arguments.stage}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
