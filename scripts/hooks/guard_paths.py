"""Claude Code hook: keep each role inside the files it owns.

Wired in .claude/settings.json to PreToolUse for the Edit, Write and
NotebookEdit tools. When the call comes from one of the roles below and the
target file is outside that role's folders, or matches one of the role's
denied patterns (tooling files inside an allowed folder, such as the web/
package and config files), the call is blocked (exit code 2) and the reason is
sent back to the agent.

The main session has no "agent_type", so the lead and you are never limited.

This is a guardrail, not a sandbox: it covers the file-editing tools, not
shell commands. The reviewer and the per-phase git commits are the backstop.
"""

from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

# Folders (ending with "/") and single files each role may write, relative to
# the project root. A role that is not listed here is not restricted.
ROLE_WRITE_PATHS: dict[str, list[str]] = {
    "spec-writer": ["specs/"],
    "test-writer": ["tests/"],
    "implementer": ["src/", "web/", "docs/", "README.md"],
    "reviewer": [],
}

# Files a role may not write even inside its allowed folders, as fnmatch
# patterns relative to the project root. The web/ package, lock and config files
# are tooling (see CLAUDE.md): only the human changes them. "web/.*" covers dot
# files and folders such as .npmrc, .gitignore and .vscode/ (fnmatch's "*" also
# matches "/").
ROLE_DENIED_PATTERNS: dict[str, list[str]] = {
    "implementer": [
        "web/package*.json",
        "web/*.config.*",
        "web/tsconfig*.json",
        "web/.*",
    ],
}


def find_project_root(start_directory: Path) -> Path:
    """Walk up from a directory until the folder holding pyproject.toml.

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


def resolve_allowed_paths(role_name: str) -> list[str] | None:
    """Return the paths a role may write, or None when it is not restricted.

    "implementer-2" is treated like "implementer".

    Args:
        role_name: Agent type taken from the hook input.
    """
    for known_role, allowed_paths in ROLE_WRITE_PATHS.items():
        if role_name == known_role or role_name.startswith(f"{known_role}-"):
            return allowed_paths
    return None


def resolve_denied_patterns(role_name: str) -> list[str]:
    """Return the patterns a role may never write, even inside its folders.

    "implementer-2" is treated like "implementer".

    Args:
        role_name: Agent type taken from the hook input.

    Returns:
        The role's denied patterns, or an empty list when it has none.
    """
    for known_role, denied_patterns in ROLE_DENIED_PATTERNS.items():
        if role_name == known_role or role_name.startswith(f"{known_role}-"):
            return denied_patterns
    return []


def find_denied_pattern(relative_path: str, denied_patterns: list[str]) -> str | None:
    """Return the first pattern that matches a path, or None.

    Args:
        relative_path: Path relative to the project root, with "/" separators.
        denied_patterns: fnmatch patterns relative to the project root.

    Returns:
        The first matching pattern, or None when no pattern matches.
    """
    for pattern in denied_patterns:
        if fnmatch.fnmatchcase(relative_path, pattern):
            return pattern
    return None


def is_allowed(relative_path: str, allowed_paths: list[str]) -> bool:
    """Tell whether a project-relative path falls inside the allowed paths.

    Args:
        relative_path: Path relative to the project root, with "/" separators.
        allowed_paths: Folders (ending with "/") and single files.
    """
    for allowed_path in allowed_paths:
        if allowed_path.endswith("/"):
            if relative_path.startswith(allowed_path):
                return True
        elif relative_path == allowed_path:
            return True
    return False


def main() -> int:
    """Read the hook input from stdin and allow or block the edit."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("guard_paths: hook input was not valid JSON.", file=sys.stderr)
        return 1

    role_name = str(hook_input.get("agent_type") or "")
    allowed_paths = resolve_allowed_paths(role_name)
    if allowed_paths is None:
        return 0

    tool_input = hook_input.get("tool_input") or {}
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path:
        return 0

    working_directory = Path(str(hook_input.get("cwd") or Path.cwd()))
    project_root = find_project_root(working_directory).resolve()

    target_path = Path(str(raw_path))
    if not target_path.is_absolute():
        target_path = working_directory / target_path
    target_path = target_path.resolve()

    try:
        relative_path = target_path.relative_to(project_root).as_posix()
    except ValueError:
        # Outside the project (scratch files, temp folders): not this hook's job.
        return 0

    denied_pattern = find_denied_pattern(
        relative_path, resolve_denied_patterns(role_name)
    )
    if denied_pattern is not None:
        print(
            f"Blocked: the {role_name} role may not write '{relative_path}': "
            f"it matches '{denied_pattern}', which is tooling (see CLAUDE.md). "
            "Only the human changes tooling. If this file really has to change, "
            "stop and say so in your report: name the file, the change and the "
            "reason, so the lead can ask the human.",
            file=sys.stderr,
        )
        return 2

    if is_allowed(relative_path, allowed_paths):
        return 0

    if allowed_paths:
        allowed_text = ", ".join(allowed_paths)
    else:
        allowed_text = "nothing (this role is read-only)"
    print(
        f"Blocked: the {role_name} role may not write '{relative_path}'. "
        f"It may write: {allowed_text}. "
        "If this file really has to change, stop and say so in your report: "
        "name the file, the change and the reason, so the lead can hand it to "
        "the role that owns it.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
