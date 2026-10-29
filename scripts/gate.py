"""Quality gate for the project.

The same script runs on a developer machine, inside the Claude Code hooks and
in GitHub Actions, so "green locally" means "green in CI".

Usage:
    uv run python scripts/gate.py                 # full gate
    uv run python scripts/gate.py --stage tests   # red phase: tests exist, code not yet
    uv run python scripts/gate.py --browsers all  # browser tests in all three engines

Stages:
    tests: ruff + black + the screens sheet up to date + spec traceability.
    full:  everything in "tests", then pyrefly, svelte-check and the vite build
           of web/, then pytest (browser tests included).

Spec traceability (2026-10-24, the domain specs of specs/_map.md): every test
points to a criterion that exists; a domain spec's criterion is proven by its own
tests (tests/test_<name>_*.py) or by a pointer "(← NNN AC-n)" to tested criteria
of the numbered specs of v1.1.0; a "done" spec has no criterion without proof;
and a tested criterion of a numbered spec moved to specs/_archive/v1.1.0/ is
cited by some domain spec.

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
    --workers: pytest-xdist workers, "auto" (one per CPU) or a number, never
        more than the machine's logical CPUs; 0 runs everything in one serial
        pass. Default: the NOCK_WORKERS environment variable, else auto. The
        tests marked `serial` (scripts/gate_browsers.py) always run after the
        parallel pass, on their own.
    --specs: spec numbers and domain names, comma-separated (for example
        027,grids): the browser tests run only for those numbered specs, those
        domains and the numbered specs the domains point to; the static checks
        and the tests without a browser run in full. The quick gate of an
        agent's finish hook (2026-10-16; domain names since 2026-10-24).

The gate's load on the machine (2026-10-29: in a review round, 16 workers'
Chromium processes and two gates at once froze a 16-thread desktop): the
parallel pass runs at a low priority, the serial pass keeps the normal one for
its timings, and one gate at a time runs its tests in a clone. A second gate
waits for the lock in the clone's .git folder, shared by every worktree, and
fails after GATE_LOCK_WAIT_SECONDS, naming the gate that holds it.

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
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = PROJECT_ROOT / "specs"
TESTS_DIR = PROJECT_ROOT / "tests"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
# Where the numbered specs of v1.1.0 go once their domains are written.
ARCHIVE_DIR = SPECS_DIR / "_archive" / "v1.1.0"

# A spec file is named NNN-short-name.md, for example 001-slugify.md.
SPEC_FILE_PATTERN = re.compile(r"^(\d{3})-.+\.md$")
# An acceptance criterion is a bullet that starts with a bold id: - **AC-1** ...
CRITERION_PATTERN = re.compile(r"^\s*[-*]\s+\*\*AC-(\d+)\*\*", re.MULTILINE)
# The spec status lives in the front matter: status: draft | approved | done
STATUS_PATTERN = re.compile(r"^status:\s*(\S+)\s*$", re.MULTILINE)
# A test is linked to a criterion by its name: def test_ac1_lowercases_text(...)
TEST_FUNCTION_PATTERN = re.compile(r"^\s*def\s+test_ac(\d+)_", re.MULTILINE)
# The spec number in a numbered test file's name: test_spec_027_ac05_display.py.
NUMBERED_TEST_FILE_PATTERN = re.compile(r"^test_spec_(\d{3})")

# A domain spec (specs/<area>/<file>.md, or specs/product.md) opens with front
# matter between two "---" lines, holding "name: value" fields.
FRONT_MATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
FRONT_MATTER_FIELD_PATTERN = re.compile(r"^(\w+):[ \t]*(.*?)[ \t]*$", re.MULTILINE)
DOMAIN_STATUSES: tuple[str, ...] = ("draft", "approved", "done")
# A domain name is the file name without .md, in kebab case: co-op, catch-up.
DOMAIN_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
# The numbered tests are test_spec_NNN_..., so no domain may be called "spec".
RESERVED_DOMAIN_NAMES: frozenset[str] = frozenset({"spec"})
# A file kept next to a domain spec for reasons a later change needs.
NOTES_SUFFIX = ".notes.md"
# A criterion's pointer to the numbered criteria whose tests prove it:
# (← 003 AC-1, 005 AC-2).
POINTER_PATTERN = re.compile(r"\(←([^)]*)\)")
NUMBERED_CRITERION_PATTERN = re.compile(r"(\d{3}) AC-(\d+)")
# A line that ends a criterion's text: a blank line, a new bullet, a heading.
CRITERION_END_PATTERN = re.compile(r"^\s*$|^\s*[-*]\s|^#")

STATIC_STEPS: list[tuple[str, list[str]]] = [
    ("ruff (lint)", ["ruff", "check", "."]),
    ("black (format)", ["black", "--check", "--diff", "--quiet", "."]),
    # The visual reference stays what its sources build (specs/_design/
    # foundation.md, « Authority »; human decision, 2026-10-22).
    (
        "screens sheet (up to date)",
        ["python", "docs/design/screens_sheet/build.py", "--check"],
    ),
]
WEB_DIR = PROJECT_ROOT / "web"

# The grids the repository ships load as the server reads them at start
# (specs/content/grid-files.md, rule 1): a refused file fails the gate here, not
# at the next deployment. No test reads grids/ itself.
LOAD_GRIDS_CODE = (
    "from nock.catalogue import GRIDS_DIR, load_catalogue; "
    "catalogue = load_catalogue(GRIDS_DIR); "
    "print(f'{len(catalogue.entries)} grid(s) in {GRIDS_DIR.name}/')"
)

RUNTIME_STATIC_STEPS: list[tuple[str, list[str]]] = [
    ("pyrefly (types)", ["pyrefly", "check"]),
    ("svelte-check (web types)", ["npm", "--prefix", "web", "run", "check"]),
    ("grids (the repository's own)", ["python", "-c", LOAD_GRIDS_CODE]),
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

# One gate at a time runs its tests in a clone (2026-10-29). The lock file and
# the line naming its holder live in the clone's .git folder.
GATE_LOCK_NAME = "nock-gate.lock"
GATE_HOLDER_NAME = "nock-gate.holder"
# Fits in the 1,140 s scripts/hooks/role_gate.py gives the gate, next to a quick
# gate of about 510 s.
GATE_LOCK_WAIT_SECONDS = 600
GATE_LOCK_POLL_SECONDS = 5
# How far a test pass at low priority lowers itself on Linux and macOS; on
# Windows it runs below normal.
LOW_PRIORITY_NICENESS = 10


@dataclass(frozen=True)
class NumberedSpec:
    """A numbered spec of v1.1.0, in specs/ or in the archive."""

    number: str
    path: Path
    archived: bool
    criterion_ids: frozenset[int]
    tested_ids: frozenset[int]


@dataclass(frozen=True)
class DomainSpec:
    """A domain spec, with its criteria and their pointers."""

    name: str
    path: Path
    status: str
    criterion_ids: frozenset[int]
    # The numbered criteria each criterion points to, as (spec number, id).
    pointers: dict[int, list[tuple[str, int]]]


@dataclass(frozen=True)
class PytestPass:
    """One pytest run of the full stage."""

    step_name: str
    command: list[str]
    # The parallel pass: its workers and their browsers load every CPU.
    low_priority: bool


@dataclass(frozen=True)
class GateLock:
    """The lock a gate holds while its tests run."""

    folder: Path
    descriptor: int


def run_tool(
    step_name: str, command: list[str], low_priority: bool = False
) -> int | None:
    """Run one external tool and return its exit code.

    Args:
        step_name: Label printed before the tool output.
        command: Executable name followed by its arguments.
        low_priority: Run the tool and every process it starts (pytest's
            workers, their browsers) at a low priority, so that the machine
            stays usable.

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
    # The processes a tool starts inherit its priority.
    creation_flags = 0
    if low_priority:
        if sys.platform == "win32":
            creation_flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS
        else:
            nice_path = shutil.which("nice")
            if nice_path is not None:
                niceness = str(LOW_PRIORITY_NICENESS)
                full_command = [nice_path, "-n", niceness, *full_command]
    completed = subprocess.run(
        full_command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        creationflags=creation_flags,
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


def run_pytest_passes(passes: list[PytestPass]) -> bool:
    """Run the pytest passes and report whether they all succeeded.

    A pass that selects no test (pytest's exit code 5) is fine, such as the
    serial pass of a selection without serial tests, as long as one pass ran
    a test.

    Args:
        passes: The passes, in order.

    Returns:
        True when every pass passed or selected nothing, and one ran a test.
    """
    all_passed = True
    tests_ran = False
    for pytest_pass in passes:
        step_name = pytest_pass.step_name
        exit_code = run_tool(step_name, pytest_pass.command, pytest_pass.low_priority)
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


def gate_lock_folder() -> Path:
    """Return the folder of the gate lock: the clone's .git folder.

    Every worktree of the clone shares it, whatever the temporary folder of the
    session that runs the gate. Outside a git clone, the temporary folder.
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return Path(tempfile.gettempdir())
    folder = Path(completed.stdout.strip())
    if completed.returncode != 0 or not folder.is_dir():
        return Path(tempfile.gettempdir())
    return folder


def try_lock(lock_descriptor: int) -> bool:
    """Take the lock on an open lock file without waiting.

    The system lets the lock go when the process ends, however it ends, so a
    gate that crashed or was stopped never leaves the lock behind.

    Args:
        lock_descriptor: The lock file, opened for reading and writing.

    Returns:
        True when the lock is now held by this process.
    """
    try:
        if sys.platform == "win32":
            os.lseek(lock_descriptor, 0, os.SEEK_SET)
            msvcrt.locking(lock_descriptor, msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(lock_descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def read_holder(folder: Path) -> str:
    """Return the line naming the gate that holds the lock, or a placeholder."""
    try:
        holder = (folder / GATE_HOLDER_NAME).read_text(encoding="utf-8").strip()
    except OSError:
        return "a gate that has not named itself yet"
    return holder or "a gate that has not named itself yet"


def take_gate_lock() -> GateLock | None:
    """Wait until no other gate of the clone runs its tests, then hold the lock.

    Returns:
        The lock, for `release_gate_lock`, or None when another gate still held
        it after GATE_LOCK_WAIT_SECONDS.
    """
    print("\n=== gate lock (one gate's tests at a time) ===", flush=True)
    folder = gate_lock_folder()
    lock_descriptor = os.open(folder / GATE_LOCK_NAME, os.O_RDWR | os.O_CREAT)
    wait_minutes = GATE_LOCK_WAIT_SECONDS // 60
    deadline = time.monotonic() + GATE_LOCK_WAIT_SECONDS
    waited = False
    while not try_lock(lock_descriptor):
        if time.monotonic() >= deadline:
            os.close(lock_descriptor)
            print(
                f"FAIL: after {wait_minutes} minutes, the tests of another gate "
                f"still run: {read_holder(folder)}. Let it finish, or stop it if "
                "nothing reads its output, then run the gate again."
            )
            return None
        if not waited:
            print(
                f"Waiting up to {wait_minutes} minutes: the tests of another gate "
                f"run: {read_holder(folder)}.",
                flush=True,
            )
            waited = True
        time.sleep(GATE_LOCK_POLL_SECONDS)

    started = time.strftime("%Y-%m-%d %H:%M:%S")
    arguments = " ".join(sys.argv[1:]) or "(no option)"
    holder = f"process {os.getpid()} in {PROJECT_ROOT}, since {started}: {arguments}"
    (folder / GATE_HOLDER_NAME).write_text(holder + "\n", encoding="utf-8")
    print(f"OK: gate lock held ({folder / GATE_LOCK_NAME})")
    return GateLock(folder=folder, descriptor=lock_descriptor)


def release_gate_lock(lock: GateLock) -> None:
    """Let the next gate run its tests."""
    (lock.folder / GATE_HOLDER_NAME).unlink(missing_ok=True)
    if sys.platform == "win32":
        os.lseek(lock.descriptor, 0, os.SEEK_SET)
        msvcrt.locking(lock.descriptor, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(lock.descriptor, fcntl.LOCK_UN)
    os.close(lock.descriptor)


def find_spec_files(directory: Path = SPECS_DIR) -> list[Path]:
    """Return every numbered spec file directly in a directory, sorted by name."""
    if not directory.is_dir():
        return []

    spec_files: list[Path] = []
    for candidate in sorted(directory.iterdir()):
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


def project_path(path: Path) -> str:
    """Return a path relative to the project root, written with "/"."""
    return path.relative_to(PROJECT_ROOT).as_posix()


def read_numbered_specs() -> tuple[dict[str, NumberedSpec], list[str]]:
    """Return the numbered specs, in specs/ and in the archive, by number.

    Returns:
        The specs by number, and one problem per number found in both places.
    """
    numbered: dict[str, NumberedSpec] = {}
    problems: list[str] = []
    for directory, archived in ((SPECS_DIR, False), (ARCHIVE_DIR, True)):
        for spec_file in find_spec_files(directory):
            name_match = SPEC_FILE_PATTERN.match(spec_file.name)
            if name_match is None:
                continue
            spec_number = name_match.group(1)
            if spec_number in numbered:
                problems.append(
                    f"spec {spec_number} is both in specs/ and in "
                    f"{project_path(ARCHIVE_DIR)}/: keep only one."
                )
                continue
            spec_text = spec_file.read_text(encoding="utf-8")
            tested_ids, _ = read_tested_criterion_ids(spec_number)
            numbered[spec_number] = NumberedSpec(
                number=spec_number,
                path=spec_file,
                archived=archived,
                criterion_ids=frozenset(read_criterion_ids(spec_text)),
                tested_ids=frozenset(tested_ids),
            )
    return numbered, problems


def check_numbered_test_files(numbered: dict[str, NumberedSpec]) -> list[str]:
    """Return one problem per numbered test file whose spec does not exist."""
    problems: list[str] = []
    known_numbers = set(numbered)
    for test_file in sorted(TESTS_DIR.glob("test_spec_*.py")):
        name_match = NUMBERED_TEST_FILE_PATTERN.match(test_file.name)
        if name_match is None:
            continue
        spec_number = name_match.group(1)
        if spec_number not in known_numbers:
            problems.append(
                f"tests/{test_file.name}: spec {spec_number} is neither in specs/ "
                f"nor in {project_path(ARCHIVE_DIR)}/."
            )
    return problems


def read_front_matter(spec_text: str) -> dict[str, str] | None:
    """Return the fields of a spec's front matter, or None when it has none."""
    match = FRONT_MATTER_PATTERN.match(spec_text)
    if match is None:
        return None
    fields: dict[str, str] = {}
    for field_match in FRONT_MATTER_FIELD_PATTERN.finditer(match.group(1)):
        fields[field_match.group(1)] = field_match.group(2)
    return fields


def read_pointers(text: str) -> list[tuple[str, int]]:
    """Return the numbered criteria named by the pointers "(← ...)" of a text."""
    pointers: list[tuple[str, int]] = []
    for pointer_match in POINTER_PATTERN.finditer(text):
        named = NUMBERED_CRITERION_PATTERN.finditer(pointer_match.group(1))
        for criterion_match in named:
            pointers.append((criterion_match.group(1), int(criterion_match.group(2))))
    return pointers


def read_domain_criteria(
    spec_text: str,
) -> tuple[dict[int, list[tuple[str, int]]], list[int]]:
    """Return a domain spec's criteria with their pointers, and repeated ids.

    A criterion's text runs from its bullet to the next blank line, bullet or
    heading; its pointers are read from that text.

    Args:
        spec_text: The text of the domain spec.

    Returns:
        The numbered criteria each criterion points to, by criterion id, and
        the ids declared more than once.
    """
    criteria: dict[int, list[tuple[str, int]]] = {}
    repeated_ids: list[int] = []
    current_id: int | None = None
    current_lines: list[str] = []
    # A last empty line closes the last criterion.
    for line in [*spec_text.splitlines(), ""]:
        start_match = CRITERION_PATTERN.match(line)
        if start_match is not None or CRITERION_END_PATTERN.match(line):
            if current_id is not None:
                criteria[current_id] = read_pointers(" ".join(current_lines))
            current_id = None
            current_lines = []
        if start_match is not None:
            current_id = int(start_match.group(1))
            if current_id in criteria:
                repeated_ids.append(current_id)
            current_lines = [line]
        elif current_id is not None:
            current_lines.append(line)
    return criteria, repeated_ids


def find_domain_spec_files() -> list[Path]:
    """Return the domain spec files, sorted by path.

    They are the .md files under specs/, except the numbered specs, the notes
    files, and every file or folder whose name starts with "_".
    """
    if not SPECS_DIR.is_dir():
        return []
    spec_files: list[Path] = []
    for path in sorted(SPECS_DIR.rglob("*.md")):
        relative_parts = path.relative_to(SPECS_DIR).parts
        hidden = any(part.startswith("_") for part in relative_parts)
        if hidden or path.name.endswith(NOTES_SUFFIX):
            continue
        if len(relative_parts) == 1 and SPEC_FILE_PATTERN.match(path.name):
            continue
        spec_files.append(path)
    return spec_files


def read_domain_spec(spec_file: Path) -> tuple[DomainSpec | None, list[str]]:
    """Read one domain spec and check its front matter.

    Args:
        spec_file: Path of the domain spec.

    Returns:
        The spec, or None when its front matter is not valid, and the problems
        found.
    """
    spec_label = project_path(spec_file)
    spec_text = spec_file.read_text(encoding="utf-8")
    fields = read_front_matter(spec_text)
    if fields is None:
        return None, [
            f"{spec_label}: no front matter (expected area, file and status "
            "between two '---' lines, as in specs/_template.md)."
        ]

    problems: list[str] = []
    name = spec_file.stem
    if not DOMAIN_NAME_PATTERN.match(name) or name in RESERVED_DOMAIN_NAMES:
        problems.append(
            f"{spec_label}: '{name}' is not a domain name (kebab case, not 'spec')."
        )
    if fields.get("file") != name:
        problems.append(
            f"{spec_label}: the front matter must say 'file: {name}', the file "
            "name without .md."
        )
    if not fields.get("area"):
        problems.append(f"{spec_label}: the front matter has no 'area'.")
    status = fields.get("status", "")
    if status not in DOMAIN_STATUSES:
        problems.append(
            f"{spec_label}: status '{status}' is not one of "
            f"{', '.join(DOMAIN_STATUSES)}."
        )
    if problems:
        return None, problems

    criteria, repeated_ids = read_domain_criteria(spec_text)
    for criterion_id in repeated_ids:
        problems.append(f"{spec_label}: AC-{criterion_id} is declared twice.")
    domain = DomainSpec(
        name=name,
        path=spec_file,
        status=status,
        criterion_ids=frozenset(criteria),
        pointers=criteria,
    )
    return domain, problems


def domain_test_prefix(domain_name: str) -> str:
    """Return the name a domain's test files start with after "test_"."""
    return domain_name.replace("-", "_")


def read_domain_specs() -> tuple[list[DomainSpec], list[str]]:
    """Return every valid domain spec and the problems found reading them.

    Besides each file's own problems, two domains may not share a name, and no
    domain's test prefix followed by "_" may begin another's, so that a test
    file always names one domain.
    """
    domains: list[DomainSpec] = []
    problems: list[str] = []
    paths_by_name: dict[str, Path] = {}
    for spec_file in find_domain_spec_files():
        domain, file_problems = read_domain_spec(spec_file)
        problems.extend(file_problems)
        if domain is None:
            continue
        if domain.name in paths_by_name:
            problems.append(
                f"{project_path(spec_file)}: the domain name '{domain.name}' is "
                f"already used by {project_path(paths_by_name[domain.name])}."
            )
            continue
        paths_by_name[domain.name] = spec_file
        domains.append(domain)

    names = sorted(paths_by_name)
    for first_name in names:
        first_prefix = domain_test_prefix(first_name) + "_"
        for second_name in names:
            if domain_test_prefix(second_name).startswith(first_prefix):
                problems.append(
                    f"domains '{first_name}' and '{second_name}': the test files "
                    f"of '{second_name}' would also name '{first_name}'; rename "
                    "one of them."
                )
    return domains, problems


def read_domain_tested_ids(domain_name: str) -> set[int]:
    """Return the criterion numbers covered by a domain's own test files."""
    prefix = domain_test_prefix(domain_name)
    test_files = sorted(TESTS_DIR.glob(f"test_{prefix}_*.py"))
    single_file = TESTS_DIR / f"test_{prefix}.py"
    if single_file.is_file():
        test_files.append(single_file)
    tested_ids: set[int] = set()
    for test_file in test_files:
        test_text = test_file.read_text(encoding="utf-8")
        for match in TEST_FUNCTION_PATTERN.finditer(test_text):
            tested_ids.add(int(match.group(1)))
    return tested_ids


def check_domain_spec(
    domain: DomainSpec, numbered: dict[str, NumberedSpec]
) -> tuple[list[str], list[str], set[tuple[str, int]]]:
    """Check that the criteria of one domain spec are proven.

    Args:
        domain: The domain spec to check.
        numbered: The numbered specs, by number.

    Returns:
        The problems, the criteria still waiting for a test (a problem only
        when the spec is "done"), and the numbered criteria its pointers cite
        with success.
    """
    spec_label = project_path(domain.path)
    test_label = f"tests/test_{domain_test_prefix(domain.name)}_*.py"
    problems: list[str] = []
    pending: list[str] = []
    cited: set[tuple[str, int]] = set()

    if domain.status != "draft" and not domain.criterion_ids:
        problems.append(
            f"{spec_label}: status is '{domain.status}' but no acceptance "
            "criterion was found (expected bullets like '- **AC-1** ...')."
        )

    tested_ids = read_domain_tested_ids(domain.name)
    for criterion_id in sorted(tested_ids - domain.criterion_ids):
        problems.append(
            f"{test_label}: test_ac{criterion_id}_... points to AC-{criterion_id}, "
            f"which does not exist in {spec_label}."
        )

    for criterion_id in sorted(domain.criterion_ids):
        proven = criterion_id in tested_ids
        for spec_number, numbered_id in domain.pointers[criterion_id]:
            pointer = f"{spec_number} AC-{numbered_id}"
            numbered_spec = numbered.get(spec_number)
            if numbered_spec is None:
                problems.append(
                    f"{spec_label}: AC-{criterion_id} points to {pointer}, but "
                    f"spec {spec_number} does not exist."
                )
            elif numbered_id not in numbered_spec.criterion_ids:
                problems.append(
                    f"{spec_label}: AC-{criterion_id} points to {pointer}, which "
                    f"does not exist in {project_path(numbered_spec.path)}."
                )
            elif numbered_id not in numbered_spec.tested_ids:
                problems.append(
                    f"{spec_label}: AC-{criterion_id} points to {pointer}, which "
                    f"no test proves (expected 'def test_ac{numbered_id}_...' in "
                    f"tests/test_spec_{spec_number}*.py)."
                )
            else:
                proven = True
                cited.add((spec_number, numbered_id))
        if not proven:
            # Plain ASCII: a Windows console or pipe may not print an arrow.
            message = (
                f"{spec_label}: AC-{criterion_id} has no test (expected "
                f"'def test_ac{criterion_id}_...' in {test_label}, or a pointer "
                "to tested criteria of a numbered spec, see specs/_map.md)."
            )
            if domain.status == "done":
                problems.append(message)
            else:
                pending.append(message)
    return problems, pending, cited


def check_archived_spec(
    numbered_spec: NumberedSpec, cited: set[tuple[str, int]]
) -> list[str]:
    """Check that the tested criteria of an archived numbered spec have an owner.

    Args:
        numbered_spec: The archived spec.
        cited: The numbered criteria the domain specs point to.

    Returns:
        One problem per test that points nowhere and per tested criterion that
        no domain spec points to.
    """
    spec_label = project_path(numbered_spec.path)
    test_glob = f"tests/test_spec_{numbered_spec.number}*.py"
    problems: list[str] = []
    dangling_ids = numbered_spec.tested_ids - numbered_spec.criterion_ids
    for criterion_id in sorted(dangling_ids):
        problems.append(
            f"{test_glob}: test_ac{criterion_id}_... points to AC-{criterion_id}, "
            f"which does not exist in {spec_label}."
        )
    owned_ids = numbered_spec.tested_ids & numbered_spec.criterion_ids
    for criterion_id in sorted(owned_ids):
        if (numbered_spec.number, criterion_id) not in cited:
            problems.append(
                f"{spec_label}: AC-{criterion_id} has tests but no domain spec "
                f"points to it (point to {numbered_spec.number} AC-{criterion_id} "
                "from the domain criterion that keeps this behaviour, or delete "
                "its tests)."
            )
    return problems


def check_traceability() -> bool:
    """Check that every acceptance criterion is proven, for every spec.

    The numbered specs still in specs/ are checked as before the domain specs:
    each criterion has a test and each test a criterion. The domain specs and
    the archived numbered specs are checked as specs/_map.md describes.

    Returns:
        True when no problem was found. Criteria of a domain spec that is not
        "done" and that wait for a test are listed, not failed.
    """
    print("\n=== spec traceability ===", flush=True)

    numbered, problems = read_numbered_specs()
    problems.extend(check_numbered_test_files(numbered))
    active_count = 0
    archived_specs: list[NumberedSpec] = []
    for spec_number in sorted(numbered):
        numbered_spec = numbered[spec_number]
        if numbered_spec.archived:
            archived_specs.append(numbered_spec)
        else:
            active_count += 1
            problems.extend(check_one_spec(numbered_spec.path))

    domains, domain_problems = read_domain_specs()
    problems.extend(domain_problems)
    pending: list[str] = []
    cited: set[tuple[str, int]] = set()
    for domain in domains:
        spec_problems, spec_pending, spec_cited = check_domain_spec(domain, numbered)
        problems.extend(spec_problems)
        pending.extend(spec_pending)
        cited.update(spec_cited)

    for numbered_spec in archived_specs:
        problems.extend(check_archived_spec(numbered_spec, cited))

    for message in pending:
        print(f"PENDING: {message}")
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        return False

    print(
        f"OK: spec traceability ({active_count} numbered spec(s), "
        f"{len(archived_specs)} archived, {len(domains)} domain spec(s) checked)"
    )
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

    A number above the machine's logical CPUs is lowered to that count: more
    workers than CPUs only slow every test down, and NOCK_WORKERS in
    .claude/settings.json holds one number for machines of every size.

    Raises:
        argparse.ArgumentTypeError: When it is neither "auto" nor a number.
    """
    if workers_text == "auto":
        return workers_text
    if not workers_text.isdigit():
        raise argparse.ArgumentTypeError("expected 'auto' or a number of workers")
    cpu_count = os.cpu_count() or 1
    return str(min(int(workers_text), cpu_count))


def parse_specs(specs_text: str) -> list[str]:
    """Return the spec numbers and domain names of a comma-separated list.

    Raises:
        argparse.ArgumentTypeError: When a part is neither a three-digit number
            nor a domain name.
    """
    specs: list[str] = []
    for part in specs_text.split(","):
        spec_name = part.strip()
        if not spec_name:
            continue
        is_number = SPEC_NUMBER_PATTERN.match(spec_name) is not None
        if not is_number and not DOMAIN_NAME_PATTERN.match(spec_name):
            raise argparse.ArgumentTypeError(
                f"'{spec_name}' is neither a spec number (three digits, e.g. 027) "
                "nor a domain name (e.g. grids)"
            )
        if spec_name not in specs:
            specs.append(spec_name)
    if not specs:
        raise argparse.ArgumentTypeError("no spec number or domain name given")
    return specs


def expand_specs(specs: list[str]) -> tuple[list[str], list[str]]:
    """Return what selects the browser tests of --specs, and the unknown domains.

    A spec number stays as it is. A domain name gives its test prefix (co-op
    gives co_op) and the numbers of the specs its criteria point to.

    Args:
        specs: The spec numbers and domain names given to --specs.

    Returns:
        The selectors for gate_browsers' --nock-specs, sorted, and the names
        that no domain spec has.
    """
    domains, _ = read_domain_specs()
    domains_by_name: dict[str, DomainSpec] = {}
    for domain in domains:
        domains_by_name[domain.name] = domain

    selectors: set[str] = set()
    unknown_names: list[str] = []
    for spec_name in specs:
        if SPEC_NUMBER_PATTERN.match(spec_name):
            selectors.add(spec_name)
            continue
        domain = domains_by_name.get(spec_name)
        if domain is None:
            unknown_names.append(spec_name)
            continue
        selectors.add(domain_test_prefix(domain.name))
        for pointers in domain.pointers.values():
            for spec_number, _ in pointers:
                selectors.add(spec_number)
    return sorted(selectors), unknown_names


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
        default=os.environ.get("NOCK_WORKERS") or "auto",
        help="pytest-xdist workers: 'auto' or a number, at most one per logical "
        "CPU; 0 runs the tests in one serial pass. Default: $NOCK_WORKERS, else "
        "auto.",
    )
    parser.add_argument(
        "--specs",
        type=parse_specs,
        default=None,
        help="Run the browser tests of these numbered specs and domains only "
        "(comma-separated, e.g. 027,grids); the tests without a browser all run.",
    )
    return parser.parse_args()


def join_marks(*expressions: str) -> str:
    """Return the `-m` expression that requires every non-empty expression."""
    parts = [f"({expression})" for expression in expressions if expression]
    return " and ".join(parts)


def pytest_commands(
    engines: list[str], selection: str, workers: str, specs: list[str] | None
) -> list[PytestPass]:
    """Return the pytest runs of the full stage.

    Args:
        engines: The engines of the browser tests.
        selection: The `-m` expression of the --tests choice ("" for all).
        workers: The pytest-xdist workers, "auto" or a number ("0": serial).
        specs: What selects the browser tests that run (spec numbers and
            domain test prefixes, from `expand_specs`), or None for all.

    Returns:
        One run when `workers` is "0", else the parallel run of the tests not
        marked `serial`, at a low priority, then the serial run of the others.
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
        return [PytestPass("pytest (tests)", command, low_priority=False)]

    parallel_command = [*base_command, "-n", workers, "--dist", "worksteal"]
    parallel_command.extend(["-m", join_marks(selection, "not serial")])
    serial_command = [*base_command, "-m", join_marks(selection, "serial")]
    return [
        PytestPass("pytest (tests, parallel)", parallel_command, low_priority=True),
        PytestPass("pytest (tests, serial)", serial_command, low_priority=False),
    ]


def main() -> int:
    """Run the requested stage and return the process exit code."""
    arguments = parse_arguments()

    selected_specs: list[str] | None = None
    if arguments.specs is not None:
        selected_specs, unknown_names = expand_specs(arguments.specs)
        if unknown_names:
            names = ", ".join(unknown_names)
            print(f"FAIL: --specs names no domain spec: {names} (see specs/_map.md)")
            return 1

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
            passes = pytest_commands(
                arguments.browsers, selection, arguments.workers, selected_specs
            )
            lock = take_gate_lock()
            if lock is None:
                results.append(False)
            else:
                try:
                    results.append(run_pytest_passes(passes))
                finally:
                    release_gate_lock(lock)

    failed_count = results.count(False)
    print()
    if failed_count > 0:
        print(f"GATE FAILED ({arguments.stage}): {failed_count} check(s) failed.")
        return 1

    print(f"GATE PASSED ({arguments.stage}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
