"""Claude Code hook: run the quality gate when a role finishes its work.

Wired in .claude/settings.json to two events:
    SubagentStop: a subagent is about to return (the role is "agent_type").
    TeammateIdle: an agent team teammate is about to go idle (the role is
        "teammate_name").

Exit codes understood by Claude Code:
    0: the agent may stop.
    2: the agent may not stop. Whatever was written to stderr is sent back to
       it, so it keeps working until the gate is green.
    1: the hook itself could not run (shown to the user, never blocks).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Which gate stage each role must pass before it is allowed to stop.
# Roles that are not listed (spec-writer, reviewer, ...) are never blocked.
ROLE_STAGES: dict[str, str] = {
    "test-writer": "tests",
    "implementer": "full",
}

MAX_OUTPUT_LINES = 80
GATE_TIMEOUT_SECONDS = 540


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

    # Let uv pick the environment of the project being checked.
    environment = dict(os.environ)
    environment.pop("VIRTUAL_ENV", None)
    # Same text encoding on Windows, macOS and Linux.
    environment["PYTHONIOENCODING"] = "utf-8"

    command = [
        uv_path,
        "run",
        "--project",
        str(project_root),
        "python",
        str(gate_script),
        "--stage",
        stage,
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
        return 0

    if completed.returncode != 1:
        # gate.py only ever exits 0 or 1. Anything else is an environment problem.
        print("role_gate: the gate could not run.", file=sys.stderr)
        print(completed.stderr[-2000:], file=sys.stderr)
        return 1

    output_lines = completed.stdout.splitlines()
    shown_lines = output_lines[-MAX_OUTPUT_LINES:]
    print(
        f"The '{stage}' quality gate is failing, so {role_name} is not done yet.\n"
        "Fix the problems below, then finish again. Do not silence a check "
        "(noqa, type: ignore, skip, xfail) and do not edit files you do not own; "
        "if a failure is outside your files, say so in your report instead.\n",
        file=sys.stderr,
    )
    print("\n".join(shown_lines), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
