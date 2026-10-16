"""Claude Code hook: run the quality gate when a role finishes its work.

Wired in .claude/settings.json to two events:
    SubagentStop: a subagent is about to return (the role is "agent_type").
    TeammateIdle: an agent team teammate is about to go idle (the role is
        "teammate_name").

The test-writer must pass the gate's "tests" stage. The implementer must pass
a quick gate that fits the hook's time (human decision, 2026-10-16): the static
checks, every test without a browser, and the browser tests in Chromium of the
specs the branch changed since `main` (found from the names of the changed
spec, test and harness files). CI runs everything else.

Exit codes understood by Claude Code:
    0: the agent may stop.
    2: the agent may not stop. Whatever was written to stderr is sent back to
       it, so it keeps working until the gate is green.
    1: the hook itself could not run (shown to the user, never blocks).

A failure the agent cannot fix, such as a stale test that only the test-writer
may change, must not hold it for ever (2026-10-16: an implementer was blocked at
every stop by a spec 018 test that spec 028 had made stale). When the hook
blocks, it keeps a fingerprint of the checkout. When the same agent then stops
again ("stop_hook_active") without having changed anything, it has reported
what it could not fix, as the message asks, and it may stop; the gate is not run
again. Any change to the checkout means a new attempt, which the gate judges.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Which gate stage each role must pass before it is allowed to stop.
# Roles that are not listed (spec-writer, reviewer, ...) are never blocked.
ROLE_STAGES: dict[str, str] = {
    "test-writer": "tests",
    "implementer": "full",
}

MAX_OUTPUT_LINES = 80
GATE_TIMEOUT_SECONDS = 540
GIT_TIMEOUT_SECONDS = 30
# The branch the changes are measured from, first the remote one.
BASE_REFS: tuple[str, ...] = ("origin/main", "main")
# The paths that name a spec: specs/027-shared-timer.md,
# tests/test_spec_027_ac05_display.py, tests/spec027_harness.py.
SPEC_PATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^specs/(\d{3})-"),
    re.compile(r"^tests/test_spec_(\d{3})_"),
    re.compile(r"^tests/spec(\d{3})_"),
)
# Where the hook keeps, per agent, the fingerprint of the checkout it last
# blocked (one small file per agent, removed when the gate passes).
BLOCK_STATE_DIRECTORY = Path(tempfile.gettempdir()) / "nock-role-gate"


def find_project_root(start_directory: Path) -> Path:
    """Walk up from a directory until the folder holding pyproject.toml.

    The hook input gives the directory the agent is working in. That is the
    main checkout in a normal session and the worktree root for an agent
    running in a git worktree, so the gate checks the files the agent edited.

    Args:
        start_directory: Directory to start the search from.

    Returns:
        The project root. Falls back to the checkout that contains this script.
    """
    candidates = [start_directory, *start_directory.parents]
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return Path(__file__).resolve().parents[2]


def resolve_stage(role_name: str) -> str | None:
    """Return the gate stage for a role name, or None when it has no gate.

    "implementer-2" is treated like "implementer", which lets an agent team
    run several implementers side by side.

    Args:
        role_name: Agent type or teammate name taken from the hook input.
    """
    for known_role, stage in ROLE_STAGES.items():
        if role_name == known_role or role_name.startswith(f"{known_role}-"):
            return stage
    return None


def run_git(project_root: Path, arguments: list[str]) -> str | None:
    """Run one git command in the project and return its output.

    Args:
        project_root: The checkout to run it in.
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
            cwd=project_root,
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


def changed_paths(project_root: Path) -> list[str]:
    """Return the paths changed since the branch left `main`, committed or not.

    Args:
        project_root: The checkout whose changes are wanted.

    Returns:
        Repository-relative paths; empty when git cannot tell.
    """
    base_commit = None
    for base_ref in BASE_REFS:
        output = run_git(project_root, ["merge-base", "HEAD", base_ref])
        if output is not None and output.strip():
            base_commit = output.strip()
            break
    if base_commit is None:
        return []
    paths: list[str] = []
    changed = run_git(project_root, ["diff", "--name-only", base_commit])
    untracked = run_git(project_root, ["ls-files", "--others", "--exclude-standard"])
    for output in (changed, untracked):
        if output is not None:
            paths.extend(line for line in output.splitlines() if line)
    return paths


def changed_specs(project_root: Path) -> list[str]:
    """Return the numbers of the specs whose spec, tests or harness changed.

    Args:
        project_root: The checkout whose changes are wanted.

    Returns:
        Three-digit spec numbers, sorted; empty when none changed.
    """
    specs: set[str] = set()
    for path in changed_paths(project_root):
        for pattern in SPEC_PATH_PATTERNS:
            match = pattern.match(path)
            if match is not None:
                specs.add(match.group(1))
    return sorted(specs)


def gate_arguments(stage: str, project_root: Path) -> list[str]:
    """Return the gate's arguments for a role's stage.

    Args:
        stage: The role's stage, "tests" or "full".
        project_root: The checkout the gate checks.

    Returns:
        "--stage tests" for the test-writer. For the implementer, the quick
        gate: the changed specs' browser tests in Chromium, or no browser test
        when no spec changed.
    """
    if stage == "tests":
        return ["--stage", "tests"]
    specs = changed_specs(project_root)
    if not specs or not gate_takes_specs(project_root):
        return ["--tests", "other"]
    return ["--specs", ",".join(specs), "--browsers", "chromium"]


def checkout_fingerprint(project_root: Path) -> str | None:
    """Return a digest of the checkout: its commit, its changes, its new files.

    Args:
        project_root: The checkout to describe.

    Returns:
        A hex digest that changes when a commit, an edit of a tracked file, or
        a new or edited untracked file changes the checkout; None when git
        cannot tell.
    """
    head = run_git(project_root, ["rev-parse", "HEAD"])
    changes = run_git(project_root, ["diff", "HEAD", "--binary"])
    untracked = run_git(project_root, ["ls-files", "--others", "--exclude-standard"])
    if head is None or changes is None or untracked is None:
        return None
    digest = hashlib.sha256()
    for part in (head, changes, untracked):
        digest.update(part.encode("utf-8", errors="replace"))
        digest.update(b"\0")
    for relative_path in untracked.splitlines():
        try:
            digest.update((project_root / relative_path).read_bytes())
        except OSError:
            digest.update(b"unreadable")
        digest.update(b"\0")
    return digest.hexdigest()


def block_state_path(hook_input: dict[str, object], role_name: str) -> Path:
    """Return the file that keeps the fingerprint of an agent's last block.

    Args:
        hook_input: The hook input; its agent id (or, failing that, its
            session id) names the agent.
        role_name: The agent's role, part of the name too.

    Returns:
        A path in BLOCK_STATE_DIRECTORY, named by a digest of those ids.
    """
    agent_key = str(hook_input.get("agent_id") or hook_input.get("session_id") or "")
    name = hashlib.sha256(f"{role_name}\0{agent_key}".encode()).hexdigest()[:32]
    return BLOCK_STATE_DIRECTORY / f"{name}.txt"


def read_block_state(state_path: Path) -> str | None:
    """Return the fingerprint kept in a block state file, or None."""
    try:
        return state_path.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def write_block_state(state_path: Path, fingerprint: str | None) -> None:
    """Keep the fingerprint of the checkout the hook is blocking.

    With no fingerprint, the file is removed, so the next stop runs the gate.
    """
    if fingerprint is None:
        clear_block_state(state_path)
        return
    # Without the file, the agent's next stop runs the gate: that is all.
    with contextlib.suppress(OSError):
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(fingerprint, encoding="utf-8")


def clear_block_state(state_path: Path) -> None:
    """Forget an agent's last block."""
    with contextlib.suppress(OSError):
        state_path.unlink(missing_ok=True)


def gate_takes_specs(project_root: Path) -> bool:
    """Tell whether the checkout's gate has --specs (added on 2026-10-16).

    A worktree branched before then has an older gate; it gets the static
    checks and the tests without a browser rather than an error.

    Args:
        project_root: The checkout the gate checks.
    """
    gate_script = project_root / "scripts" / "gate.py"
    try:
        gate_text = gate_script.read_text(encoding="utf-8")
    except OSError:
        return False
    return '"--specs"' in gate_text


def main() -> int:
    """Read the hook input from stdin, run the gate and decide."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("role_gate: hook input was not valid JSON.", file=sys.stderr)
        return 1

    agent_type = hook_input.get("agent_type")
    teammate_name = hook_input.get("teammate_name")
    role_name = str(agent_type or teammate_name or "")
    stage = resolve_stage(role_name)
    if stage is None:
        return 0

    working_directory = Path(str(hook_input.get("cwd") or Path.cwd()))
    project_root = find_project_root(working_directory)
    gate_script = project_root / "scripts" / "gate.py"

    uv_path = shutil.which("uv")
    if uv_path is None or not gate_script.is_file():
        print("role_gate: uv or scripts/gate.py is missing.", file=sys.stderr)
        return 1

    # Blocked before and nothing changed since: the agent has reported what it
    # cannot fix, as the message below asks, so it may stop.
    state_path = block_state_path(hook_input, role_name)
    if hook_input.get("stop_hook_active") is True:
        fingerprint = checkout_fingerprint(project_root)
        if fingerprint is not None and fingerprint == read_block_state(state_path):
            clear_block_state(state_path)
            return 0

    # Let uv pick the environment of the project being checked.
    environment = dict(os.environ)
    environment.pop("VIRTUAL_ENV", None)
    # Same text encoding on Windows, macOS and Linux.
    environment["PYTHONIOENCODING"] = "utf-8"

    arguments = gate_arguments(stage, project_root)
    command = [
        uv_path,
        "run",
        "--project",
        str(project_root),
        "python",
        str(gate_script),
        *arguments,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=project_root,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GATE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print("role_gate: the quality gate timed out.", file=sys.stderr)
        return 1

    if completed.returncode == 0:
        clear_block_state(state_path)
        return 0

    if completed.returncode != 1:
        # gate.py only ever exits 0 or 1. Anything else is an environment problem.
        print("role_gate: the gate could not run.", file=sys.stderr)
        print(completed.stderr[-2000:], file=sys.stderr)
        return 1

    # Taken after the gate ran, so that files the run itself leaves behind do
    # not count as the agent's change at its next stop.
    write_block_state(state_path, checkout_fingerprint(project_root))
    output_lines = completed.stdout.splitlines()
    shown_lines = output_lines[-MAX_OUTPUT_LINES:]
    gate_description = " ".join(arguments)
    print(
        f"The quality gate ({gate_description}) is failing, so {role_name} is "
        "not done yet.\n"
        "Fix the problems below, then finish again. Do not silence a check "
        "(noqa, type: ignore, skip, xfail) and do not edit files you do not own.\n"
        "If a failure is outside your files (a test that only the test-writer may "
        "change, a tooling file), say so in your report and finish again without "
        "changing anything: the hook then lets you stop.\n",
        file=sys.stderr,
    )
    print("\n".join(shown_lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
