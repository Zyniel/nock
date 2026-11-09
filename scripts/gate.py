"""Quality gate for the project.

The same script runs on a developer machine, inside the Claude Code hooks and
in GitHub Actions, so "green locally" means "green in CI".

Usage:
    uv run python scripts/gate.py                 # full gate
    uv run python scripts/gate.py --stage tests   # red phase: tests exist, code not yet
    uv run python scripts/gate.py --browsers all  # browser tests in all three engines

Stages:
    tests: ruff + black + the screens sheet up to date + spec traceability +
           the map of the shared client components (SHARED_COMPONENT_DOMAINS).
    full:  everything in "tests", then pyrefly, svelte-check, the TypeScript
           unit tests of tests/web/ (node:test) and the vite build of web/,
           then pytest (browser tests included).

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
    --skip-static: skip ruff, black, traceability, pyrefly, svelte-check and
        the TypeScript unit tests, for CI jobs whose static checks run in
        another job. --tests browser leaves the TypeScript unit tests out too.
    --workers: pytest-xdist workers, "auto" (one per CPU) or a number, never
        more than the machine's logical CPUs; 0 runs everything in one serial
        pass. Default: the NOCK_WORKERS environment variable, else auto. The
        tests marked `serial` (scripts/gate_browsers.py) always run after the
        parallel pass, on their own.
    --specs: spec numbers and domain names, comma-separated (for example
        027,grids): the browser tests run only for those numbered specs, those
        domains, the numbered specs the domains point to, and the domains of
        the shared client components the branch changed since main
        (SHARED_COMPONENT_DOMAINS); the static checks and the tests without a
        browser run in full. The quick gate of an agent's finish hook
        (2026-10-16; domain names since 2026-10-24).
    --pass-timeout: the watchdog's limits for the parallel pass and the serial
        pass (and its re-run), in minutes, "75,20" by default; one number
        sets both. A pass still running at its limit is stopped with every
        process it started, and the tests it was running are named.
    --resume: skip the tests that passed in an earlier run on the same
        checkout (same commit, same uncommitted changes), read from this
        branch's run folders; the count left out is printed.
    --shard I/N: run only the I-th of N shards of the test files, sorted by
        name and dealt round robin. Each pass deals its own files, those its
        `-m` selection keeps, so a file with serial and parallel tests may
        fall in different shards in the two passes; the N shards of a pass
        still cover all its tests.

Each run of the tests keeps its results in .git/nock-gate-results/<branch>/
<run>/ (the newest KEEP_RUNS_PER_BRANCH runs of a branch are kept): run.json
(the commit, the checkout's fingerprint, the options, the CPUs), summary.txt
(every result line of the tests and the verdict, time-stamped), and per pass
(parallel, serial, serial-rerun, or tests for --workers 0) its JUnit XML
report, its results file (one JSON line per test phase, written as the tests
run, so it survives a stopped run) and its progress folder (the test each
worker runs). A gate stopped from outside leaves its browsers running: the
next gate warns about Playwright browsers it finds once it holds the lock, and
never stops them.

The gate's load on the machine (2026-10-29: in a review round, 16 workers'
Chromium processes and two gates at once froze a 16-thread desktop): the
parallel pass runs at a low priority, the serial pass keeps the normal one for
its timings, and one gate at a time runs its tests in a clone. A second gate
waits for the lock in the clone's .git folder, shared by every worktree, and
fails after GATE_LOCK_WAIT_SECONDS, naming the gate that holds it.
Before the serial pass, the gate waits up to SERIAL_LOAD_WAIT_SECONDS for the
load (the processes running or waiting for a CPU) to fall under
SERIAL_LOAD_FRACTION of the logical CPUs, then runs anyway, and writes the load
beside the serial result. The serial tests that failed, if no more than
MAX_RERUN_FAILURES, run once more: those that pass then are reported « passed
on re-run » with both loads, so a test that only passes under a low load can be
seen and mended. A watchdog stop, a pytest error and the parallel pass are
never re-run.

Exit codes:
    0: every check passed.
    1: at least one check failed.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
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
    # A raw invisible character cannot be seen in a review: the code standards
    # write it as a \N{NAME} escape (B-108).
    (
        "raw characters (escaped)",
        ["python", "scripts/hooks/guard_paths.py", "--check-repository"],
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
# The TypeScript tests of the client's pure modules: Node's own runner, types
# stripped by Node (22.18 or later), the Vite-style imports resolved by
# scripts/node_test_hooks.mjs. They need no browser, so they run with the
# static group, and they prove no criterion. Node expands the glob itself.
NODE_TEST_STEP: tuple[str, list[str]] = (
    "node:test (web unit tests)",
    [
        "node",
        "--import",
        "./scripts/node_test_hooks.mjs",
        "--test",
        "tests/web/**/*.test.ts",
    ],
)
# pytest comes after the web build: browser tests load the built client.
BUILD_STEP: tuple[str, list[str]] = (
    "vite build (web)",
    ["npm", "--prefix", "web", "run", "build"],
)

# The client components that serve several domains, and the domains whose
# browser tests they serve: the domain specs whose « Code » section names them.
# A change to one of them adds those domains to the quick gate (--specs) and to
# the implementer's gate (scripts/hooks/role_gate.py), since such a change broke
# other domains' tests that only the full gate ran (B-041, B-045). The static
# check "shared components" keeps it equal to what the Code sections say: every
# component that SHARED_COMPONENT_MIN_DOMAINS domains or more name, with exactly
# those domains.
SHARED_COMPONENT_DOMAINS: dict[str, tuple[str, ...]] = {
    "web/src/lib/ClueCell.svelte": (
        "foundation",
        "product",
        "reactions",
        "viewport",
    ),
    "web/src/lib/FocusableLink.svelte": (
        "foundation",
        "hud",
        "menus",
        "my-account",
        "results",
        "room",
        "rooms",
        "shell",
        "summaries",
    ),
    "web/src/lib/GridViewport.svelte": (
        "authorship",
        "board",
        "foundation",
        "presence",
        "product",
        "server",
        "viewport",
    ),
    "web/src/lib/LetterCell.svelte": (
        "authorship",
        "catch-up",
        "co-op",
        "foundation",
        "hints",
        "pencil",
        "presence",
        "product",
        "viewport",
    ),
    "web/src/lib/PlayButton.svelte": (
        "cards",
        "foundation",
        "history",
        "rooms",
    ),
    "web/src/lib/PlayersPanel.svelte": (
        "chat",
        "host",
        "hud",
        "presence",
        "room",
        "rooms",
    ),
    "web/src/lib/RoomMenu.svelte": (
        "authorship",
        "menus",
        "my-account",
        "rules",
    ),
    "web/src/lib/RoomPage.svelte": (
        "authorship",
        "board",
        "cards",
        "catch-up",
        "chat",
        "co-op",
        "hints",
        "history",
        "host",
        "hud",
        "joining",
        "menus",
        "my-account",
        "pencil",
        "presence",
        "product",
        "reconnection",
        "results",
        "room",
        "rooms",
        "rules",
        "server",
        "shell",
        "viewport",
        "votes",
    ),
    "web/src/lib/RoomTopBar.svelte": (
        "hud",
        "pencil",
        "rules",
        "server",
    ),
}
SHARED_COMPONENT_MIN_DOMAINS = 4
# A word that may name a client component in a spec's Code section: the specs
# write `RoomPage.svelte`, or a list of names with the suffix once at its end
# (`Salon`, `PlayersPanel` (`.svelte`)). A word names a component when a
# .svelte file of web/src/ has that name.
COMPONENT_WORD_PATTERN = re.compile(r"\b([A-Z][A-Za-z0-9]*)\b")
# The heading of a domain spec's Code section, and of the section after it.
CODE_HEADING = "## Code"
SECTION_HEADING_PATTERN = re.compile(r"^## ", re.MULTILINE)
# The branch whose changes the quick gate measures, first the remote one
# (the same as BASE_REFS of scripts/hooks/role_gate.py).
BASE_REFS: tuple[str, ...] = ("origin/main", "main")
GIT_TIMEOUT_SECONDS = 30

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

# The watchdog (B-107): a pytest pass still running after its limit is stopped,
# with every process it started, and the tests it was running are named, so a
# hung browser no longer holds the gate and its lock for hours. --pass-timeout
# changes the limits; the single pass of --workers 0 gets their sum.
PARALLEL_PASS_TIMEOUT_SECONDS = 75 * 60
SERIAL_PASS_TIMEOUT_SECONDS = 20 * 60
# The exit code of a pass the watchdog stopped, the one of the `timeout` command.
TIMED_OUT_EXIT_CODE = 124
# How long to wait for a stopped process to be gone.
STOP_WAIT_SECONDS = 30

# Each run of the gate's tests keeps its results in a folder of its own, under
# the clone's .git folder: <branch>/<run>/ in RESULTS_FOLDER_NAME (B-107).
RESULTS_FOLDER_NAME = "nock-gate-results"
KEEP_RUNS_PER_BRANCH = 20
# A branch name becomes a folder name: every other character becomes "-".
FOLDER_NAME_UNSAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]")
# The labels of the pytest passes, in the order a run writes their files.
RESULT_LABELS: tuple[str, ...] = ("tests", "parallel", "serial", "serial-rerun")

# Before the serial pass, the gate waits a little for the load of the machine
# to fall under this share of its logical CPUs, and re-runs the serial tests
# that failed once, if they are few (B-107).
SERIAL_LOAD_FRACTION = 0.75
# Short enough that the 1,140 s scripts/hooks/role_gate.py gives the gate
# still holds the quick gate, the lock wait and, at worst, two of these waits:
# one before the serial pass and one before its re-run (2 x 120 s).
SERIAL_LOAD_WAIT_SECONDS = 120
LOAD_POLL_SECONDS = 5
MAX_RERUN_FAILURES = 20
# The browsers' processes: their executables live under ms-playwright, or
# under $PLAYWRIGHT_BROWSERS_PATH.
PLAYWRIGHT_FOLDER_NAME = "ms-playwright"
MAX_SHOWN_PIDS = 20
PROCESS_LIST_TIMEOUT_SECONDS = 30


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
    # The name of its files in the run's folder: parallel, serial,
    # serial-rerun, or tests for the single pass of --workers 0.
    label: str
    # The watchdog's limit.
    timeout_seconds: float
    # The serial pass: it waits for a low load, and its failures re-run once.
    serial: bool


@dataclass(frozen=True)
class GateRun:
    """The results folder of one run of the gate's tests."""

    folder: Path
    summary_path: Path
    # The checkout's commit and changes (checkout_fingerprint), for --resume.
    fingerprint: str | None
    cpu_count: int


@dataclass(frozen=True)
class Watchdog:
    """The limit of one pytest pass, and the files that say what it runs."""

    timeout_seconds: float
    progress_folder: Path
    results_path: Path
    run: GateRun


@dataclass(frozen=True)
class GateLock:
    """The lock a gate holds while its tests run."""

    folder: Path
    descriptor: int


def run_tool(
    step_name: str,
    command: list[str],
    low_priority: bool = False,
    watchdog: Watchdog | None = None,
) -> int | None:
    """Run one external tool and return its exit code.

    Args:
        step_name: Label printed before the tool output.
        command: Executable name followed by its arguments.
        low_priority: Run the tool and every process it starts (pytest's
            workers, their browsers) at a low priority, so that the machine
            stays usable.
        watchdog: The limit of a pytest pass: past it, the tests it runs are
            named, and the tool and every process it started are stopped.
            None waits as long as the tool runs.

    Returns:
        The exit code, TIMED_OUT_EXIT_CODE when the watchdog stopped the tool,
        or None when the tool or its dependencies are missing.

    Raises:
        KeyboardInterrupt: On Ctrl-C, once the tool and every process it
            started are stopped.
    """
    print(f"\n=== {step_name} ===", flush=True)

    executable_path = shutil.which(command[0])
    if executable_path is None:
        print(
            f"FAIL: '{command[0]}' is not installed. "
            "Run: uv sync (Python tools), or install Node.js LTS (npm)."
        )
        return None

    if command[0] in ("npm", "node") and not (WEB_DIR / "node_modules").is_dir():
        print("FAIL: the web dependencies are not installed. Run: npm --prefix web ci")
        return None

    full_command = [executable_path, *command[1:]]
    environment = dict(os.environ)
    # scripts/ on pytest's import path only, so that it can load the
    # gate_browsers plugin. Pyrefly reads PYTHONPATH as a site-packages folder
    # and leaves it out of the project, so with it scripts/ went unchecked
    # (B-029).
    if command[0] == "pytest":
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
    # Output goes straight to the gate's own, as it comes.
    process = subprocess.Popen(
        full_command,
        cwd=PROJECT_ROOT,
        env=environment,
        creationflags=creation_flags,
    )
    timeout_seconds = None
    if watchdog is not None:
        timeout_seconds = watchdog.timeout_seconds
    try:
        return process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        # Stopped before the report, so that nothing in the report can leave
        # pytest running once the gate lets the lock go. The progress files
        # outlive the stop, so the report still names the tests.
        try:
            stop_process_tree(process.pid)
            wait_for_end(process)
        except KeyboardInterrupt:
            stop_process_tree(process.pid)
            raise
        if watchdog is not None:
            report_watchdog_stop(step_name, watchdog)
        return TIMED_OUT_EXIT_CODE
    except KeyboardInterrupt:
        stop_process_tree(process.pid)
        wait_for_end(process)
        raise


def wait_for_end(process: subprocess.Popen[bytes]) -> None:
    """Wait a little for a stopped process to be gone."""
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=STOP_WAIT_SECONDS)


def list_processes(columns: str) -> list[str]:
    """Return one line per process of the machine, from `ps` (Linux, macOS).

    Args:
        columns: The `ps -o` columns, each followed by "=" so that no header
            line is printed, such as "pid=,ppid=".

    Returns:
        The lines; empty when `ps` is missing or fails.
    """
    ps_path = shutil.which("ps")
    if ps_path is None:
        return []
    try:
        completed = subprocess.run(
            [ps_path, "-A", "-o", columns],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROCESS_LIST_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    return completed.stdout.splitlines()


def descendant_pids(root_pid: int) -> list[int]:
    """Return the processes a process started, and theirs, and so on.

    Args:
        root_pid: The process whose descendants are wanted.

    Returns:
        Their process ids; empty when `ps` cannot list the processes.
    """
    children_by_parent: dict[int, list[int]] = {}
    for line in list_processes("pid=,ppid="):
        fields = line.split()
        if len(fields) != 2 or not fields[0].isdigit() or not fields[1].isdigit():
            continue
        child_pid = int(fields[0])
        parent_pid = int(fields[1])
        children_by_parent.setdefault(parent_pid, []).append(child_pid)

    descendants: list[int] = []
    parents_to_visit = [root_pid]
    while parents_to_visit:
        parent_pid = parents_to_visit.pop()
        for child_pid in children_by_parent.get(parent_pid, []):
            descendants.append(child_pid)
            parents_to_visit.append(child_pid)
    return descendants


def stop_process_tree(root_pid: int) -> None:
    """Stop a process and every process it started, at once.

    The gate starts its tools in its own session and process group, not in
    one of their own, on purpose: scripts/hooks/role_gate.py stops the
    gate's whole group on its own timeout, and Ctrl-C in a terminal reaches
    the whole group, so both must still reach pytest, its workers and their
    browsers. The tree is found from each process's parent instead: on
    Windows by taskkill, as stop_process_tree of scripts/hooks/role_gate.py
    does; on Linux and macOS from `ps`.

    Args:
        root_pid: The process the gate started.
    """
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/PID", str(root_pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    descendants = descendant_pids(root_pid)
    # The root first, so that pytest-xdist cannot start a new worker in place
    # of one stopped; the descendants were listed before.
    for pid in [root_pid, *descendants]:
        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.kill(pid, signal.SIGKILL)


def format_minutes(seconds: float) -> str:
    """Return a duration in minutes, as short as it can be written: 75, 0.2."""
    return f"{seconds / 60:g}"


def worker_sort_key(progress_file: Path) -> tuple[int, str]:
    """Order the progress files gw0, gw1, ..., gw9, gw10, then main."""
    return (len(progress_file.stem), progress_file.stem)


def running_tests(progress_folder: Path) -> list[str]:
    """Return one line per test running, from the progress files of a pass.

    Args:
        progress_folder: The folder given to gate_browsers' --nock-progress-dir.

    Returns:
        Lines such as "gw0 tests/test_x.py::test_y[chromium] (since 14 min)",
        one per worker running a test.
    """
    if not progress_folder.is_dir():
        return []
    lines: list[str] = []
    now = datetime.now().astimezone()
    for progress_file in sorted(progress_folder.glob("*.txt"), key=worker_sort_key):
        try:
            file_lines = progress_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        if not file_lines:
            continue
        node_id = file_lines[0]
        since = "since an unknown time"
        if len(file_lines) > 1 and file_lines[1].startswith("started "):
            try:
                started = datetime.fromisoformat(file_lines[1].removeprefix("started "))
            except ValueError:
                started = None
            if started is not None:
                minutes = int((now - started).total_seconds() // 60)
                since = f"since {minutes} min"
        lines.append(f"{progress_file.stem} {node_id} ({since})")
    return lines


def report_watchdog_stop(step_name: str, watchdog: Watchdog) -> None:
    """Say that the watchdog stops a pass, and which tests were running.

    Args:
        step_name: The pass, such as "pytest (tests, parallel)".
        watchdog: Its limit and the files that say what it runs.
    """
    minutes = format_minutes(watchdog.timeout_seconds)
    # pytest's line of dots may not have ended.
    print()
    stopped = f"FAIL: {step_name} stopped by the watchdog after {minutes} min"
    tests = running_tests(watchdog.progress_folder)
    if tests:
        note(watchdog.run, f"{stopped}; running:")
        for line in tests:
            note(watchdog.run, f"  {line}")
    elif read_result_lines(watchdog.results_path):
        note(
            watchdog.run,
            f"{stopped}; no test was running: the start or the end of a "
            "session hung (a browser launched or closed)",
        )
    else:
        note(
            watchdog.run,
            f"{stopped}; no test had started: collection or warm-up hung",
        )


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


def pass_command(
    pytest_pass: PytestPass, run: GateRun, extra_options: list[str]
) -> list[str]:
    """Return a pass's command, writing its results in the run's folder.

    Args:
        pytest_pass: The pass.
        run: The run's results folder.
        extra_options: More pytest options, such as --nock-skip-passed.

    Returns:
        The command, with the JUnit XML report, the results file and the
        progress folder of the pass's label.
    """
    label = pytest_pass.label
    junit_path = run.folder / f"{label}.xml"
    progress_folder = run.folder / "progress" / label
    # "--option=value": pytest picks its root folder before it knows the
    # plugin's options, and would take a separate path value for a test path
    # (the clone's root, through .git/, instead of the checkout's).
    return [
        *pytest_pass.command,
        *extra_options,
        f"--junitxml={junit_path}",
        # The format whose report keeps the tests' record_property values.
        "--override-ini=junit_family=xunit1",
        f"--nock-results={results_path_of(run, label)}",
        f"--nock-progress-dir={progress_folder}",
    ]


def results_path_of(run: GateRun, label: str) -> Path:
    """Return the results file of a pass, one JSON line per test phase."""
    return run.folder / f"{label}.jsonl"


def read_left_out_count(left_out_path: Path) -> int:
    """Return the count gate_browsers' --nock-left-out wrote, or 0.

    Args:
        left_out_path: The file of the count of tests a pass left out as
            passed already (--resume).

    Returns:
        The count; 0 when the file is missing or holds no number.
    """
    try:
        text = left_out_path.read_text(encoding="utf-8").strip()
    except OSError:
        return 0
    if not text.isdigit():
        return 0
    return int(text)


def resume_options(skip_path: Path | None, run: GateRun, label: str) -> list[str]:
    """Return the pytest options of --resume for one pass.

    Args:
        skip_path: The file of node ids to leave out, or None without --resume.
        run: The run's results folder.
        label: The pass's label.

    Returns:
        --nock-skip-passed and --nock-left-out, or nothing without --resume.
    """
    if skip_path is None:
        return []
    left_out_path = run.folder / f"{label}-left-out.txt"
    return [f"--nock-skip-passed={skip_path}", f"--nock-left-out={left_out_path}"]


def run_pytest_pass(
    pytest_pass: PytestPass, run: GateRun, extra_options: list[str]
) -> int | None:
    """Run one pytest pass under its watchdog and return its exit code.

    Args:
        pytest_pass: The pass.
        run: The run's results folder.
        extra_options: More pytest options, such as --nock-skip-passed.

    Returns:
        pytest's exit code, TIMED_OUT_EXIT_CODE when the watchdog stopped it,
        or None when pytest is missing.
    """
    label = pytest_pass.label
    watchdog = Watchdog(
        timeout_seconds=pytest_pass.timeout_seconds,
        progress_folder=run.folder / "progress" / label,
        results_path=results_path_of(run, label),
        run=run,
    )
    command = pass_command(pytest_pass, run, extra_options)
    return run_tool(pytest_pass.step_name, command, pytest_pass.low_priority, watchdog)


def run_pytest_passes(
    passes: list[PytestPass],
    run: GateRun,
    base_command: list[str],
    skip_path: Path | None,
) -> bool:
    """Run the pytest passes and report whether they all succeeded.

    A pass that selects no test (pytest's exit code 5) is fine, such as the
    serial pass of a selection without serial tests, as long as one pass ran
    a test, or --resume left out tests of its selection. The serial pass
    waits for a low load first (wait_for_low_load), and the tests it fails
    run once more (rerun_serial_failures).

    Args:
        passes: The passes, in order.
        run: The run's results folder; every result line goes to its summary.
        base_command: The pytest command without a selection, for a re-run.
        skip_path: The file of node ids --resume leaves out, for every pass
            but a re-run; None without --resume.

    Returns:
        True when every pass passed or selected nothing, and one ran a test.
    """
    all_passed = True
    tests_ran = False
    # What the passes' own selections left out as passed, from gate_browsers.
    tests_left_out = 0
    for pytest_pass in passes:
        step_name = pytest_pass.step_name
        load_label = ""
        load: float | None = None
        if pytest_pass.serial:
            load = wait_for_low_load(run)
            load_label = f" ({describe_load(load, run.cpu_count)})"
        extra_options = resume_options(skip_path, run, pytest_pass.label)
        exit_code = run_pytest_pass(pytest_pass, run, extra_options)
        if skip_path is not None:
            left_out_path = run.folder / f"{pytest_pass.label}-left-out.txt"
            tests_left_out += read_left_out_count(left_out_path)
        if exit_code == 0:
            tests_ran = True
            note(run, f"OK: {step_name}{load_label}")
        elif exit_code == NO_TESTS_COLLECTED:
            note(run, f"OK: {step_name} (no test selected)")
        elif exit_code is None:
            all_passed = False
            append_summary(run, f"FAIL: {step_name} could not start")
        elif exit_code == TIMED_OUT_EXIT_CODE:
            # report_watchdog_stop has said so.
            all_passed = False
        elif exit_code == 1 and pytest_pass.serial:
            if rerun_serial_failures(pytest_pass, run, base_command, load):
                tests_ran = True
            else:
                all_passed = False
        else:
            all_passed = False
            note(run, f"FAIL: {step_name} exited with code {exit_code}{load_label}")
    if all_passed and not tests_ran:
        if tests_left_out > 0:
            note(
                run,
                f"OK: the {tests_left_out} selected test(s) passed in an earlier "
                "run (--resume)",
            )
            return True
        note(run, "FAIL: no pytest pass selected a test")
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


def results_root() -> Path:
    """Return the folder of every run's results, in the clone's .git folder."""
    return gate_lock_folder() / RESULTS_FOLDER_NAME


def branch_folder_name() -> str:
    """Return the checkout's branch as a folder name, or "detached".

    Every character other than a letter, a digit, ".", "_" or "-" becomes
    "-": feat/b-107-x gives feat-b-107-x.
    """
    output = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    if output is None:
        return "detached"
    branch = output.strip()
    if not branch or branch == "HEAD":
        return "detached"
    return FOLDER_NAME_UNSAFE_PATTERN.sub("-", branch)


def checkout_fingerprint() -> str | None:
    """Return a digest of the checkout: its commit, its changes, its new files.

    A copy of checkout_fingerprint of scripts/hooks/role_gate.py, for the
    project's own checkout.

    Returns:
        A hex digest that changes when a commit, an edit of a tracked file, or
        a new or edited untracked file changes the checkout; None when git
        cannot tell.
    """
    head = run_git(["rev-parse", "HEAD"])
    changes = run_git(["diff", "HEAD", "--binary"])
    untracked = run_git(["ls-files", "--others", "--exclude-standard"])
    if head is None or changes is None or untracked is None:
        return None
    digest = hashlib.sha256()
    for part in (head, changes, untracked):
        digest.update(part.encode("utf-8", errors="replace"))
        digest.update(b"\0")
    for relative_path in untracked.splitlines():
        try:
            digest.update((PROJECT_ROOT / relative_path).read_bytes())
        except OSError:
            digest.update(b"unreadable")
        digest.update(b"\0")
    return digest.hexdigest()


def prune_old_runs(branch_folder: Path) -> None:
    """Delete a branch's oldest run folders, keeping KEEP_RUNS_PER_BRANCH."""
    run_folders: list[Path] = []
    for candidate in branch_folder.iterdir():
        if candidate.is_dir():
            run_folders.append(candidate)
    # A run folder's name starts with its start time, so names sort by age.
    run_folders.sort()
    old_count = len(run_folders) - KEEP_RUNS_PER_BRANCH
    for old_folder in run_folders[: max(old_count, 0)]:
        shutil.rmtree(old_folder, ignore_errors=True)


def start_gate_run(shard: str | None) -> GateRun:
    """Make this run's results folder and describe the run in run.json.

    Called once the gate lock is held, so that one run at a time writes in the
    results folders.

    Args:
        shard: The --shard value, such as "2/3", or None.

    Returns:
        The run.
    """
    branch_folder = results_root() / branch_folder_name()
    run_name = time.strftime("%Y-%m-%dT%H-%M-%S") + f"-p{os.getpid()}"
    folder = branch_folder / run_name
    folder.mkdir(parents=True, exist_ok=True)
    prune_old_runs(branch_folder)

    commit = run_git(["rev-parse", "HEAD"])
    fingerprint = checkout_fingerprint()
    cpu_count = os.cpu_count() or 1
    description = {
        "commit": None if commit is None else commit.strip(),
        "fingerprint": fingerprint,
        "branch": branch_folder.name,
        "argv": sys.argv[1:],
        "started": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cpus": cpu_count,
        "platform": sys.platform,
        "shard": shard,
    }
    run_file = folder / "run.json"
    run_file.write_text(json.dumps(description, indent=2) + "\n", encoding="utf-8")
    print(f"Results of this run: {folder}", flush=True)
    return GateRun(
        folder=folder,
        summary_path=folder / "summary.txt",
        fingerprint=fingerprint,
        cpu_count=cpu_count,
    )


def append_summary(run: GateRun, line: str) -> None:
    """Add a time-stamped line to the run's summary.txt."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        with run.summary_path.open("a", encoding="utf-8") as summary:
            summary.write(f"{stamp} {line}\n")
    except OSError as error:
        print(f"WARNING: cannot write {run.summary_path}: {error}")


def note(run: GateRun, line: str) -> None:
    """Print a result line and add it to the run's summary."""
    print(line, flush=True)
    append_summary(run, line)


def windows_playwright_pids(markers: list[str]) -> list[int]:
    """Return the processes whose executable's path holds a marker, on Windows."""
    powershell_path = shutil.which("powershell")
    if powershell_path is None:
        return []
    conditions: list[str] = []
    for marker in markers:
        quoted = marker.replace("'", "''")
        conditions.append(f"$_.ExecutablePath -like '*{quoted}*'")
    script = (
        "Get-CimInstance Win32_Process | Where-Object { "
        + " -or ".join(conditions)
        + " } | Select-Object ProcessId, Name"
    )
    try:
        completed = subprocess.run(
            [powershell_path, "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PROCESS_LIST_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode != 0:
        return []
    pids: list[int] = []
    # A table: a header, a line of dashes, then "ProcessId Name" rows.
    for line in completed.stdout.splitlines():
        fields = line.split()
        if fields and fields[0].isdigit():
            pids.append(int(fields[0]))
    return pids


def playwright_pids() -> list[int]:
    """Return the processes of Playwright's browsers running on the machine.

    A browser process is one whose executable lies under the browsers' folder;
    the rest of a command line is not read, since a shell or a test may name
    that folder without being a browser.

    Returns:
        Their process ids, without the gate's own; empty when the processes
        cannot be listed.
    """
    markers = [PLAYWRIGHT_FOLDER_NAME]
    browsers_path = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")
    if browsers_path and browsers_path != "0":
        markers.append(browsers_path)
    if sys.platform == "win32":
        pids = windows_playwright_pids(markers)
    else:
        pids = []
        for line in list_processes("pid=,args="):
            pid_text, _, arguments = line.strip().partition(" ")
            if not pid_text.isdigit():
                continue
            # The executable, up to the first space: a browser's path holds
            # none before the browsers' folder.
            executable = arguments.strip().partition(" ")[0]
            for marker in markers:
                if marker in executable:
                    pids.append(int(pid_text))
                    break
    own_pid = os.getpid()
    return [pid for pid in pids if pid != own_pid]


def warn_about_orphan_browsers(run: GateRun) -> None:
    """Warn when Playwright browsers run while no gate runs its tests.

    Called once the lock is held, before the first pass: such browsers belong
    to an earlier gate that was stopped, or to a pytest run outside the gate.
    The gate never stops them: they may be someone else's.

    Args:
        run: The run whose summary gets the warning.
    """
    pids = playwright_pids()
    if not pids:
        return
    shown = " ".join(str(pid) for pid in pids[:MAX_SHOWN_PIDS])
    if len(pids) > MAX_SHOWN_PIDS:
        shown += " ..."
    note(
        run,
        f"WARNING: {len(pids)} Playwright browser process(es) run while no gate "
        "holds the lock: an earlier gate stopped, or a pytest outside the gate. "
        f"PIDs {shown}. Stop them if they are not yours.",
    )


def windows_system_times() -> tuple[int, int] | None:
    """Return Windows' idle and total CPU time so far, in 100 ns units.

    Returns:
        Both times, summed over the CPUs; None when Windows cannot tell, or on
        another system.
    """
    idle_time = ctypes.c_uint64()
    kernel_time = ctypes.c_uint64()
    user_time = ctypes.c_uint64()
    succeeded = False
    # The check lets the type checker read WinDLL, which only Windows has.
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.WinDLL("kernel32")
            succeeded = kernel32.GetSystemTimes(
                ctypes.byref(idle_time),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            )
        except (OSError, AttributeError):
            return None
    if not succeeded:
        return None
    # The kernel time includes the idle time.
    return idle_time.value, kernel_time.value + user_time.value


def read_windows_load() -> float | None:
    """Return how many CPUs' worth of work Windows did over one second."""
    first_times = windows_system_times()
    if first_times is None:
        return None
    time.sleep(1)
    second_times = windows_system_times()
    if second_times is None:
        return None
    idle_delta = second_times[0] - first_times[0]
    total_delta = second_times[1] - first_times[1]
    if total_delta <= 0:
        return None
    busy_fraction = 1 - idle_delta / total_delta
    return busy_fraction * (os.cpu_count() or 1)


def read_load() -> float | None:
    """Return the machine's load: the processes running or waiting for a CPU.

    On Linux and macOS, the load average of the last minute; on Windows, the
    CPUs' busy share over one second times their count.

    Returns:
        The load, or None when the system cannot tell.
    """
    if sys.platform == "win32":
        return read_windows_load()
    try:
        return os.getloadavg()[0]
    except OSError:
        return None


def describe_load(load: float | None, cpu_count: int) -> str:
    """Return "load 2.3 of 16 CPUs", or "load unknown"."""
    if load is None:
        return "load unknown"
    return f"load {load:.1f} of {cpu_count} CPUs"


def load_number(load: float | None) -> str:
    """Return a load as "2.3", or "unknown"."""
    if load is None:
        return "unknown"
    return f"{load:.1f}"


def wait_for_low_load(run: GateRun) -> float | None:
    """Wait a little for the machine's load to fall, before timed tests.

    The wait ends when the load falls under SERIAL_LOAD_FRACTION of the CPUs,
    or after SERIAL_LOAD_WAIT_SECONDS, when the tests run anyway.

    Args:
        run: The run whose summary says when the load stayed high.

    Returns:
        The load when the wait ended, or None when it is unknown (no wait).
    """
    load = read_load()
    if load is None:
        return None
    limit = SERIAL_LOAD_FRACTION * run.cpu_count
    if load < limit:
        return load
    print(
        f"Waiting for the load to fall under {limit:.1f} (now {load:.1f} of "
        f"{run.cpu_count} CPUs).",
        flush=True,
    )
    deadline = time.monotonic() + SERIAL_LOAD_WAIT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(LOAD_POLL_SECONDS)
        load = read_load()
        if load is None:
            return None
        if load < limit:
            return load
    note(
        run,
        f"WARNING: load still {load:.1f} after {SERIAL_LOAD_WAIT_SECONDS} s, "
        "running anyway",
    )
    return load


def read_result_lines(results_path: Path) -> list[dict[str, object]]:
    """Return the lines of a pass's results file; a broken line is skipped.

    Args:
        results_path: The file gate_browsers' --nock-results wrote.

    Returns:
        One dictionary per test phase (nodeid, when, outcome, duration,
        worker); empty when the file does not exist.
    """
    try:
        text = results_path.read_text(encoding="utf-8")
    except OSError:
        return []
    result_lines: list[dict[str, object]] = []
    for line in text.splitlines():
        try:
            result = json.loads(line)
        except json.JSONDecodeError:
            # The last line of a stopped run may be cut.
            continue
        if isinstance(result, dict):
            result_lines.append(result)
    return result_lines


def failed_node_ids(results_path: Path) -> list[str]:
    """Return the tests that failed in a pass: one phase failed or more.

    Args:
        results_path: The pass's results file.

    Returns:
        Their node ids, in the order they failed.
    """
    failed_ids: list[str] = []
    for result in read_result_lines(results_path):
        node_id = str(result.get("nodeid", ""))
        if result.get("outcome") == "failed" and node_id not in failed_ids:
            failed_ids.append(node_id)
    return failed_ids


def rerun_serial_failures(
    serial_pass: PytestPass,
    run: GateRun,
    base_command: list[str],
    first_load: float | None,
) -> bool:
    """Run the tests the serial pass failed once more, if they are few.

    A timed test can fail when the machine is loaded; it passes on a re-run
    when the failure was the load's. Both loads are written beside the
    result, so a test that only passes on a re-run can be seen and mended.

    Args:
        serial_pass: The serial pass, which exited with code 1.
        run: The run's results folder.
        base_command: The pytest command without a selection.
        first_load: The load when the serial pass started.

    Returns:
        True when every test that failed passed on the re-run.
    """
    step_name = serial_pass.step_name
    first_load_label = describe_load(first_load, run.cpu_count)
    failed_ids = failed_node_ids(results_path_of(run, serial_pass.label))
    if not failed_ids:
        note(
            run,
            f"FAIL: {step_name} exited with code 1 ({first_load_label}); its "
            "results name no failed test, so nothing is re-run",
        )
        return False
    if len(failed_ids) > MAX_RERUN_FAILURES:
        note(
            run,
            f"FAIL: {step_name}: {len(failed_ids)} tests failed "
            f"({first_load_label}), more than {MAX_RERUN_FAILURES}: not re-run",
        )
        return False

    print(
        f"{step_name}: {len(failed_ids)} test(s) failed ({first_load_label}); "
        "running them once more.",
        flush=True,
    )
    rerun_pass = PytestPass(
        step_name=f"{step_name} re-run",
        command=[*base_command, *failed_ids],
        low_priority=False,
        label="serial-rerun",
        timeout_seconds=serial_pass.timeout_seconds,
        serial=True,
    )
    load = wait_for_low_load(run)
    exit_code = run_pytest_pass(rerun_pass, run, [])
    count = len(failed_ids)
    if exit_code == 0:
        note(
            run,
            f"OK: {step_name}: {count} test(s) passed on re-run under load "
            f"{load_number(load)} of {run.cpu_count} CPUs (failed first under "
            f"load {load_number(first_load)}):",
        )
    elif exit_code == 1:
        note(
            run,
            f"FAIL: {step_name}: {count} test(s) failed again on re-run under "
            f"load {load_number(load)}:",
        )
    else:
        if exit_code != TIMED_OUT_EXIT_CODE:
            note(run, f"FAIL: {step_name} re-run exited with code {exit_code}")
        note(run, f"FAIL: {step_name}: {count} test(s) failed:")
    for node_id in failed_ids:
        note(run, f"  {node_id}")
    return exit_code == 0


def read_run_fingerprint(run_folder: Path) -> str | None:
    """Return the checkout fingerprint an earlier run's run.json holds."""
    try:
        description = json.loads((run_folder / "run.json").read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(description, dict):
        return None
    fingerprint = description.get("fingerprint")
    if isinstance(fingerprint, str):
        return fingerprint
    return None


def read_outcomes(results_path: Path, passed_by_id: dict[str, bool]) -> None:
    """Record whether each test of a results file passed.

    A test passed when its call passed and none of its phases failed. A test
    already recorded takes the outcome of this later file.

    Args:
        results_path: A pass's results file.
        passed_by_id: Whether each test passed, by node id; updated.
    """
    seen_ids: set[str] = set()
    call_passed_ids: set[str] = set()
    failed_ids: set[str] = set()
    for result in read_result_lines(results_path):
        node_id = str(result.get("nodeid", ""))
        seen_ids.add(node_id)
        outcome = result.get("outcome")
        if outcome == "failed":
            failed_ids.add(node_id)
        elif outcome == "passed" and result.get("when") == "call":
            call_passed_ids.add(node_id)
    for node_id in seen_ids:
        passed = node_id in call_passed_ids and node_id not in failed_ids
        passed_by_id[node_id] = passed


def prepare_resume(run: GateRun) -> Path | None:
    """List the tests that passed already on this checkout, for --resume.

    They are read from the earlier runs of this branch whose checkout had the
    same fingerprint; the latest outcome of a test wins.

    Args:
        run: This run; skip-passed.txt goes in its folder.

    Returns:
        The file of node ids to leave out, or None when git cannot describe
        the checkout.
    """
    if run.fingerprint is None:
        note(
            run,
            "FAIL: --resume: git cannot describe this checkout (its commit and "
            "changes), so no earlier run can match it. Run without --resume.",
        )
        return None
    passed_by_id: dict[str, bool] = {}
    for run_folder in sorted(run.folder.parent.iterdir()):
        if run_folder == run.folder or not run_folder.is_dir():
            continue
        if read_run_fingerprint(run_folder) != run.fingerprint:
            continue
        for label in RESULT_LABELS:
            results_path = run_folder / f"{label}.jsonl"
            if results_path.is_file():
                read_outcomes(results_path, passed_by_id)

    passed_ids: list[str] = []
    for node_id in sorted(passed_by_id):
        if passed_by_id[node_id]:
            passed_ids.append(node_id)
    skip_path = run.folder / "skip-passed.txt"
    skip_text = "".join(f"{node_id}\n" for node_id in passed_ids)
    skip_path.write_text(skip_text, encoding="utf-8")
    if passed_ids:
        note(
            run,
            f"--resume: {len(passed_ids)} test(s) passed on this checkout "
            "already, left out",
        )
    else:
        note(run, "--resume: nothing passed on this checkout yet")
    return skip_path


def run_tests(
    passes: list[PytestPass],
    run: GateRun,
    base_command: list[str],
    resume: bool,
) -> bool:
    """Run the pytest passes of a run, once the gate lock is held.

    Args:
        passes: The passes, in order.
        run: The run's results folder.
        base_command: The pytest command without a selection, for a re-run.
        resume: Leave out the tests that passed already on this checkout.

    Returns:
        True when the passes succeeded.
    """
    warn_about_orphan_browsers(run)
    skip_path: Path | None = None
    if resume:
        skip_path = prepare_resume(run)
        if skip_path is None:
            return False
    return run_pytest_passes(passes, run, base_command, skip_path)


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


def code_section(spec_text: str) -> str:
    """Return a domain spec's Code section, without its heading.

    Args:
        spec_text: The domain spec's text.

    Returns:
        The text between "## Code" and the next "## " heading; empty when the
        spec has no Code section.
    """
    start = spec_text.find(f"\n{CODE_HEADING}\n")
    if start < 0:
        return ""
    body_start = start + len(CODE_HEADING) + 2
    next_heading = SECTION_HEADING_PATTERN.search(spec_text, body_start)
    if next_heading is None:
        return spec_text[body_start:]
    return spec_text[body_start : next_heading.start()]


def component_domains_from_specs() -> dict[str, set[str]]:
    """Return the domains whose Code section names each client component.

    Returns:
        The domain names, by the component's repository-relative path (for
        example web/src/lib/RoomPage.svelte), for every component that some
        Code section names.
    """
    paths_by_name: dict[str, str] = {}
    for component_file in sorted(WEB_DIR.joinpath("src").rglob("*.svelte")):
        component_path = component_file.relative_to(PROJECT_ROOT).as_posix()
        paths_by_name[component_file.stem] = component_path

    domains_by_component: dict[str, set[str]] = {}
    for spec_file in find_domain_spec_files():
        section = code_section(spec_file.read_text(encoding="utf-8"))
        for word in COMPONENT_WORD_PATTERN.findall(section):
            component_path = paths_by_name.get(word)
            if component_path is None:
                continue
            domain_names = domains_by_component.setdefault(component_path, set())
            domain_names.add(spec_file.stem)
    return domains_by_component


def shared_component_problems(
    component_domains: dict[str, set[str]],
) -> list[str]:
    """Compare SHARED_COMPONENT_DOMAINS with the domains the specs give.

    Args:
        component_domains: The domains naming each component, from
            component_domains_from_specs.

    Returns:
        One message per difference; empty when the map is right.
    """
    expected: dict[str, set[str]] = {}
    for component_path, domain_names in component_domains.items():
        if len(domain_names) >= SHARED_COMPONENT_MIN_DOMAINS:
            expected[component_path] = domain_names

    problems: list[str] = []
    for component_path, domain_tuple in SHARED_COMPONENT_DOMAINS.items():
        if len(set(domain_tuple)) != len(domain_tuple):
            problems.append(f"{component_path} lists a domain twice.")
        expected_domains = expected.get(component_path)
        if expected_domains is None:
            problems.append(
                f"{component_path} is not a component that "
                f"{SHARED_COMPONENT_MIN_DOMAINS} domains or more name in their "
                "Code section: take it out of SHARED_COMPONENT_DOMAINS."
            )
            continue
        if set(domain_tuple) != expected_domains:
            names = ", ".join(sorted(expected_domains))
            problems.append(
                f"{component_path}: the Code sections of {names} name it; "
                "SHARED_COMPONENT_DOMAINS must list exactly those."
            )
    for component_path in sorted(expected):
        if component_path not in SHARED_COMPONENT_DOMAINS:
            names = ", ".join(sorted(expected[component_path]))
            problems.append(
                f"{component_path}: the Code sections of {names} name it; add it "
                "to SHARED_COMPONENT_DOMAINS."
            )
    return problems


def check_shared_components() -> bool:
    """Check SHARED_COMPONENT_DOMAINS against the domain specs' Code sections.

    Every client component that SHARED_COMPONENT_MIN_DOMAINS domain specs or
    more name in their Code section must be in the map, under its path, with
    exactly those domains; the map holds no other component.

    Returns:
        True when the map and the Code sections agree.
    """
    print("\n=== shared components (the quick gate's map) ===", flush=True)
    problems = shared_component_problems(component_domains_from_specs())
    if problems:
        for problem in problems:
            print(f"FAIL: shared components: {problem}")
        return False
    print(f"OK: shared components ({len(SHARED_COMPONENT_DOMAINS)} in the map)")
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


def parse_pass_timeout(timeout_text: str) -> tuple[float, float]:
    """Return the watchdog's limits of --pass-timeout, in seconds.

    Args:
        timeout_text: "MINUTES" for both passes, or "MINUTES,MINUTES" for the
            parallel pass and the serial pass (and its re-run).

    Returns:
        The limits of the parallel pass and of the serial pass.

    Raises:
        argparse.ArgumentTypeError: When a part is not a number of minutes
            above zero, or there are more than two.
    """
    parts = timeout_text.split(",")
    if len(parts) > 2:
        raise argparse.ArgumentTypeError(
            "expected MINUTES or MINUTES,MINUTES (the parallel and serial passes)"
        )
    limits: list[float] = []
    for part in parts:
        try:
            minutes = float(part.strip())
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"'{part.strip()}' is not a number of minutes"
            ) from None
        # An infinite limit overflows Popen.wait on Windows.
        if not math.isfinite(minutes) or not minutes > 0:
            raise argparse.ArgumentTypeError(
                "a limit must be a finite number of minutes above 0"
            )
        limits.append(minutes * 60)
    if len(limits) == 1:
        return limits[0], limits[0]
    return limits[0], limits[1]


def parse_shard(shard_text: str) -> str:
    """Return the --shard value, "I/N", checked.

    Raises:
        argparse.ArgumentTypeError: When it is not I/N with 1 <= I <= N.
    """
    number_text, _, count_text = shard_text.strip().partition("/")
    if not number_text.isdigit() or not count_text.isdigit():
        raise argparse.ArgumentTypeError(
            f"'{shard_text}' is not I/N, such as 2/3 (the second of three shards)"
        )
    shard_number = int(number_text)
    shard_count = int(count_text)
    if shard_count < 1:
        raise argparse.ArgumentTypeError(f"'{shard_text}': N must be 1 or more")
    if not 1 <= shard_number <= shard_count:
        raise argparse.ArgumentTypeError(
            f"'{shard_text}': I must be from 1 to {shard_count}"
        )
    return f"{shard_number}/{shard_count}"


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


def shared_component_domains(paths: list[str]) -> list[str]:
    """Return the domains served by the shared components among some paths.

    Args:
        paths: Repository-relative paths written with "/".

    Returns:
        The domain names of SHARED_COMPONENT_DOMAINS for those paths, sorted.
    """
    domain_names: set[str] = set()
    for path in paths:
        domain_names.update(SHARED_COMPONENT_DOMAINS.get(path, ()))
    return sorted(domain_names)


def run_git(arguments: list[str]) -> str | None:
    """Run one git command in the project and return its output.

    Args:
        arguments: The git arguments, without "git".

    Returns:
        The standard output, or None when git is missing or the command fails.
    """
    git_path = shutil.which("git")
    if git_path is None:
        return None
    try:
        completed = subprocess.run(
            [git_path, *arguments],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def branch_changed_paths() -> list[str]:
    """Return the paths changed since the branch left `main`, committed or not.

    The role hook has its own copy (changed_paths of
    scripts/hooks/role_gate.py), which measures the checkout it checks.

    Returns:
        Repository-relative paths; empty when git cannot tell.
    """
    base_commit = None
    for base_ref in BASE_REFS:
        output = run_git(["merge-base", "HEAD", base_ref])
        if output is not None and output.strip():
            base_commit = output.strip()
            break
    if base_commit is None:
        return []
    paths: list[str] = []
    changed = run_git(["diff", "--name-only", base_commit])
    untracked = run_git(["ls-files", "--others", "--exclude-standard"])
    for output in (changed, untracked):
        if output is not None:
            paths.extend(line for line in output.splitlines() if line)
    return paths


def add_shared_component_domains(specs: list[str]) -> list[str]:
    """Add to --specs the domains of the shared components the branch changed.

    Args:
        specs: The spec numbers and domain names given to --specs.

    Returns:
        The same list, followed by the domains it lacked, which are printed.
    """
    added_names: list[str] = []
    for domain_name in shared_component_domains(branch_changed_paths()):
        if domain_name not in specs:
            added_names.append(domain_name)
    if added_names:
        names = ",".join(added_names)
        print(f"--specs: the branch changed a shared component, adding {names}")
    return [*specs, *added_names]


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
        help="Skip ruff, black, traceability, pyrefly, svelte-check and the "
        "TypeScript unit tests.",
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
    default_minutes = (
        f"{format_minutes(PARALLEL_PASS_TIMEOUT_SECONDS)},"
        f"{format_minutes(SERIAL_PASS_TIMEOUT_SECONDS)}"
    )
    parser.add_argument(
        "--pass-timeout",
        type=parse_pass_timeout,
        default=default_minutes,
        metavar="MINUTES[,MINUTES]",
        help="The watchdog's limits for the parallel pass and the serial pass "
        f"(and its re-run), in minutes. Default: {default_minutes}.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip the tests that passed in an earlier run of this gate on the "
        "same checkout (same commit and same uncommitted changes), read from the "
        f"run folders of this branch under .git/{RESULTS_FOLDER_NAME}/. The count "
        "left out is printed.",
    )
    parser.add_argument(
        "--shard",
        type=parse_shard,
        default=None,
        metavar="I/N",
        help="Run only the I-th of N shards of the test files (1-based): the "
        "files sorted by name, dealt round robin, so a long run of several "
        "engines fits in shorter runs. Each pass deals its own files (after "
        "-m): a file with serial and parallel tests may fall in different "
        "shards in the two passes, and the N shards of each pass cover all its "
        "tests.",
    )
    return parser.parse_args()


def join_marks(*expressions: str) -> str:
    """Return the `-m` expression that requires every non-empty expression."""
    parts = [f"({expression})" for expression in expressions if expression]
    return " and ".join(parts)


def base_pytest_command(engines: list[str], specs: list[str] | None) -> list[str]:
    """Return the pytest command every pass starts from, without a selection.

    Args:
        engines: The engines of the browser tests.
        specs: What selects the browser tests that run (spec numbers and
            domain test prefixes, from `expand_specs`), or None for all.

    Returns:
        The command: pytest with the gate_browsers plugin and the engines.
    """
    # gate_browsers marks the tests and leaves out the browser engines that are
    # not installed, with a warning; in CI it fails instead. It also leaves out
    # the browser tests of the specs not in --nock-specs.
    base_command = ["pytest", "--quiet", "-p", "gate_browsers"]
    for engine_name in engines:
        base_command.extend(["--browser", engine_name])
    if specs is not None:
        base_command.extend(["--nock-specs", ",".join(specs)])
    return base_command


def pytest_commands(
    base_command: list[str],
    selection: str,
    workers: str,
    shard: str | None,
    timeouts: tuple[float, float],
) -> list[PytestPass]:
    """Return the pytest runs of the full stage.

    Args:
        base_command: The command every pass starts from (base_pytest_command).
        selection: The `-m` expression of the --tests choice ("" for all).
        workers: The pytest-xdist workers, "auto" or a number ("0": serial).
        shard: The --shard value, "I/N", or None for every test file.
        timeouts: The watchdog's limits of the parallel and serial passes, in
            seconds.

    Returns:
        One run when `workers` is "0", else the parallel run of the tests not
        marked `serial`, at a low priority, then the serial run of the others.
    """
    shard_options: list[str] = []
    if shard is not None:
        shard_options = [f"--nock-shard={shard}"]
    parallel_timeout, serial_timeout = timeouts

    if workers == "0":
        command = [*base_command, *shard_options]
        if selection:
            command.extend(["-m", selection])
        # Not `serial`: the pass holds every test, so a failure is not re-run.
        single_pass = PytestPass(
            "pytest (tests)",
            command,
            low_priority=False,
            label="tests",
            timeout_seconds=parallel_timeout + serial_timeout,
            serial=False,
        )
        return [single_pass]

    parallel_command = [*base_command, *shard_options]
    parallel_command.extend(["-n", workers, "--dist", "worksteal"])
    parallel_command.extend(["-m", join_marks(selection, "not serial")])
    serial_command = [*base_command, *shard_options]
    serial_command.extend(["-m", join_marks(selection, "serial")])
    parallel_pass = PytestPass(
        "pytest (tests, parallel)",
        parallel_command,
        low_priority=True,
        label="parallel",
        timeout_seconds=parallel_timeout,
        serial=False,
    )
    serial_pass = PytestPass(
        "pytest (tests, serial)",
        serial_command,
        low_priority=False,
        label="serial",
        timeout_seconds=serial_timeout,
        serial=True,
    )
    return [parallel_pass, serial_pass]


def main() -> int:
    """Run the requested stage and return the process exit code."""
    arguments = parse_arguments()

    selected_specs: list[str] | None = None
    if arguments.specs is not None:
        specs = add_shared_component_domains(arguments.specs)
        selected_specs, unknown_names = expand_specs(specs)
        if unknown_names:
            names = ", ".join(unknown_names)
            print(f"FAIL: --specs names no domain spec: {names} (see specs/_map.md)")
            return 1

    results: list[bool] = []
    # The run's results folder, once the gate lock is held.
    gate_run: GateRun | None = None
    run_static = not arguments.skip_static or arguments.stage == "tests"
    if run_static:
        for step_name, command in STATIC_STEPS:
            results.append(run_step(step_name, command))
        results.append(check_traceability())
        results.append(check_shared_components())

    if arguments.stage == "full":
        if run_static:
            for step_name, command in RUNTIME_STATIC_STEPS:
                results.append(run_step(step_name, command))
            if arguments.tests != "browser":
                results.append(run_step(*NODE_TEST_STEP))
        build_name, build_command = BUILD_STEP
        results.append(run_step(build_name, build_command))
        if results[-1]:
            selection = TEST_SELECTIONS[arguments.tests]
            base_command = base_pytest_command(arguments.browsers, selected_specs)
            passes = pytest_commands(
                base_command,
                selection,
                arguments.workers,
                arguments.shard,
                arguments.pass_timeout,
            )
            lock = take_gate_lock()
            if lock is None:
                results.append(False)
            else:
                try:
                    gate_run = start_gate_run(arguments.shard)
                    passed = run_tests(passes, gate_run, base_command, arguments.resume)
                    results.append(passed)
                except KeyboardInterrupt:
                    if gate_run is not None:
                        append_summary(gate_run, "INTERRUPTED: the gate was stopped")
                    raise
                finally:
                    release_gate_lock(lock)

    failed_count = results.count(False)
    print()
    if failed_count > 0:
        verdict = f"GATE FAILED ({arguments.stage}): {failed_count} check(s) failed."
    else:
        verdict = f"GATE PASSED ({arguments.stage})."
    print(verdict)
    if gate_run is not None:
        append_summary(gate_run, verdict)
        print(f"Results of this run: {gate_run.folder}")
    if failed_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
