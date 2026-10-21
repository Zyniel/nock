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

The gate checks the checkout the agent edited, found from its transcript: the
hook input's "cwd" is the session's directory, so it names the main checkout
even when the agent worked in a git worktree of its own (2026-10-17). The files
it wrote with Edit or Write name that checkout, and so do the directories its
Bash commands name with `git -C`, `cd` and `--directory` (2026-10-21: an
implementer that edited only through Bash was gated in the session's directory).

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
# Below the hook's 1,200 s in .claude/settings.json, which leaves time for uv and
# git. A gate that runs out of time does not block (exit 1), so the limit must
# fit the slowest quick gate: on 2026-10-16 the quick gate of a branch that
# changed 19 specs took about 510 s, close to the 540 s of then.
GATE_TIMEOUT_SECONDS = 1140
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
# The tools whose input names a file the agent wrote.
FILE_EDIT_TOOLS: frozenset[str] = frozenset(
    {"Edit", "MultiEdit", "NotebookEdit", "Write"}
)
# The tool whose commands can name the directory the agent works in.
SHELL_TOOL = "Bash"
# A directory a shell command works in: `git -C <path>`, `cd <path>`,
# `--directory <path>` or `--directory=<path>`, the path bare or quoted.
SHELL_DIRECTORY_PATTERN = re.compile(
    r"""(?:\bgit\s+-C\s+|(?<![\w-])cd\s+|--directory(?:=|\s+))"""
    r"""(?:"([^"]+)"|'([^']+)'|([^\s;&|)]+))"""
)
# A Git Bash path to a Windows drive: /k/Projects/awf is K:/Projects/awf.
DRIVE_PATH_PATTERN = re.compile(r"^/([A-Za-z])(/.*)?$")


def nearest_project_root(start_directory: Path) -> Path | None:
    """Walk up from a directory until the folder holding pyproject.toml.

    Args:
        start_directory: Directory to start the search from.

    Returns:
        The project root, or None when no folder above holds pyproject.toml.
    """
    candidates = [start_directory, *start_directory.parents]
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return None


def find_project_root(start_directory: Path) -> Path:
    """Return the project root above a directory.

    Args:
        start_directory: Directory to start the search from.

    Returns:
        The project root. Falls back to the checkout that contains this script.
    """
    project_root = nearest_project_root(start_directory)
    if project_root is None:
        return Path(__file__).resolve().parents[2]
    return project_root


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


def agent_transcript(hook_input: dict[str, object]) -> Path | None:
    """Return the path of the agent's own transcript, or None.

    SubagentStop gives it as "agent_transcript_path". Without it, the agent's
    transcript sits next to the session's, in subagents/agent-<agent_id>.jsonl.

    Args:
        hook_input: The hook input.
    """
    given_path = hook_input.get("agent_transcript_path")
    if isinstance(given_path, str) and given_path:
        return Path(given_path)
    session_transcript = hook_input.get("transcript_path")
    agent_id = hook_input.get("agent_id")
    if not isinstance(session_transcript, str) or not session_transcript:
        return None
    if not isinstance(agent_id, str) or not agent_id:
        return None
    session_folder = Path(session_transcript).with_suffix("")
    return session_folder / "subagents" / f"agent-{agent_id}.jsonl"


def shell_path(text: str) -> Path:
    """Return the path a shell command names, read as this system reads it.

    On Windows, a Git Bash path to a drive (/k/Projects/awf) becomes the drive's
    path (K:/Projects/awf).

    Args:
        text: The path as the command writes it.
    """
    if os.name == "nt":
        match = DRIVE_PATH_PATTERN.match(text)
        if match is not None:
            drive = match.group(1).upper()
            rest = match.group(2) or "/"
            return Path(f"{drive}:{rest}")
    return Path(text)


def command_directories(command: str) -> list[Path]:
    """Return the absolute directories a shell command works in, in order.

    Args:
        command: The command given to the Bash tool.

    Returns:
        The paths after `git -C`, `cd` and `--directory`; relative paths are
        left out, since the shell's directory at that point is not known.
    """
    directories: list[Path] = []
    for match in SHELL_DIRECTORY_PATTERN.finditer(command):
        text = match.group(1) or match.group(2) or match.group(3)
        directory = shell_path(text)
        if directory.is_absolute():
            directories.append(directory)
    return directories


def worked_directories(transcript_path: Path) -> list[Path]:
    """Return the directories an agent's transcript shows it working in, in order.

    Args:
        transcript_path: The agent's transcript, one JSON object per line.

    Returns:
        The folder of each file given to its Edit, MultiEdit, NotebookEdit and
        Write calls, and the directories its Bash commands name; empty when the
        transcript cannot be read.
    """
    try:
        lines = transcript_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    directories: list[Path] = []
    for line in lines.splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = entry.get("message") if isinstance(entry, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_input = block.get("input")
            if not isinstance(tool_input, dict):
                continue
            tool_name = block.get("name")
            if tool_name == SHELL_TOOL:
                command = tool_input.get("command")
                if isinstance(command, str):
                    directories.extend(command_directories(command))
                continue
            if tool_name not in FILE_EDIT_TOOLS:
                continue
            file_path = tool_input.get("file_path") or tool_input.get("notebook_path")
            if isinstance(file_path, str) and file_path:
                directories.append(Path(file_path).parent)
    return directories


def repository_checkouts(project_root: Path) -> set[Path]:
    """Return the main checkout and every git worktree of the repository.

    Args:
        project_root: Any checkout of the repository.
    """
    output = run_git(project_root, ["worktree", "list", "--porcelain"])
    checkouts: set[Path] = set()
    if output is None:
        return checkouts
    for line in output.splitlines():
        if line.startswith("worktree "):
            checkouts.add(Path(line.removeprefix("worktree ")).resolve())
    return checkouts


def checkout_to_check(hook_input: dict[str, object]) -> Path:
    """Return the checkout the gate checks: the one the agent last edited.

    The hook input's "cwd" is the session's directory. For an agent that
    worked in a git worktree, it still names the main checkout: on 2026-10-17
    the hook ran an implementer's quick gate there and missed every change it
    had made in its worktree. The agent's transcript names the files it
    wrote and the directories its shell commands worked in. The checkout of
    the last one counts, provided that checkout is the main checkout or one
    of its worktrees, not a scratch copy. With none, "cwd" decides.

    Args:
        hook_input: The hook input.

    Returns:
        The project root of the checkout to check.
    """
    working_directory = Path(str(hook_input.get("cwd") or Path.cwd()))
    session_root = find_project_root(working_directory)
    transcript_path = agent_transcript(hook_input)
    if transcript_path is None:
        return session_root
    checkouts = repository_checkouts(session_root)
    edited_root: Path | None = None
    for directory in worked_directories(transcript_path):
        directory_root = nearest_project_root(directory)
        if directory_root is not None and directory_root.resolve() in checkouts:
            edited_root = directory_root
    if edited_root is None:
        return session_root
    return edited_root


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

    project_root = checkout_to_check(hook_input)
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
