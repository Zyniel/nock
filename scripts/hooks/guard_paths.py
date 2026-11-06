r"""Claude Code hook: keep each role inside the files it owns.

Wired in .claude/settings.json to PreToolUse for the Edit, Write and
NotebookEdit tools. When the call comes from one of the roles below and the
target file is outside that role's folders, or matches one of the role's
denied patterns (tooling files inside an allowed folder, such as the web/
package and config files), the call is blocked (exit code 2) and the reason is
sent back to the agent.

The main session has no "agent_type", so the lead and you are never limited.

The edited file is judged against the checkout that holds it: the main tree
or a git worktree (a folder with both pyproject.toml and .git). An agent that
works in a worktree is thus held to its folders there, whatever the session's
working directory (2026-10-16: after a container restart, an implementer's
working directory came back as the main tree and every edit in its worktree
was refused).

Every caller, the lead included, is also refused text that holds a raw
invisible character: a format, control, space or separator character other
than the plain space, the line feed and the tab (Unicode categories Cf, Cc, Zs,
Zl and Zp). The code standards write such a character as a `\N{NAME}` escape
(CLAUDE.md); a raw one cannot be seen in a review. The one exception is the
zero-width joiner between two emoji, which joins them into one (B-108). With
`--check-repository`, the script scans every file git tracks instead, as a
static step of scripts/gate.py.

This is a guardrail, not a sandbox: it covers the file-editing tools, not
shell commands. The reviewer and the per-phase git commits are the backstop.
"""

from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

# Folders (ending with "/") and single files each role may write, relative to
# the project root. A role that is not listed here is not restricted.
ROLE_WRITE_PATHS: dict[str, list[str]] = {
    "spec-writer": ["specs/", "docs/design/"],
    "test-writer": ["tests/"],
    "implementer": ["src/", "web/", "docs/", "README.md"],
    "reviewer": [],
    "spec-checker": [],
}

# Files a role may not write even inside its allowed folders, as fnmatch
# patterns relative to the project root. The web/ package, lock and config files
# are tooling (see CLAUDE.md): only the human changes them. "web/.*" covers dot
# files and folders such as .npmrc, .gitignore and .vscode/ (fnmatch's "*" also
# matches "/").
ROLE_DENIED_PATTERNS: dict[str, list[str]] = {
    # docs/design/ is the visual reference, drawn with specs/_design/ by the
    # spec-writer before tests and code (human decision, 2026-10-22).
    "implementer": [
        "docs/design/*",
        "web/package*.json",
        "web/*.config.*",
        "web/tsconfig*.json",
        "web/.*",
    ],
}


# The Unicode categories of the characters a file may not hold raw, and the
# characters of those categories it may.
RAW_CHARACTER_CATEGORIES: frozenset[str] = frozenset({"Cf", "Cc", "Zs", "Zl", "Zp"})
# The names \N{...} accepts for the control characters, which have no Unicode
# name of their own.
CONTROL_CHARACTER_NAMES: dict[str, str] = {
    "\0": "NULL",
    "\b": "BACKSPACE",
    "\v": "LINE TABULATION",
    "\f": "FORM FEED",
    "\r": "CARRIAGE RETURN",
    "\x1b": "ESCAPE",
    "\x7f": "DELETE",
}
# How many problems the hook lists before it gives their total.
LISTED_PROBLEMS = 5
ALLOWED_RAW_CHARACTERS: frozenset[str] = frozenset({" ", "\n", "\t"})
ZERO_WIDTH_JOINER = "\N{ZERO WIDTH JOINER}"
VARIATION_SELECTOR_16 = "\N{VARIATION SELECTOR-16}"
# The first code point of the emoji planes (U+1F000 to U+1FAFF).
FIRST_EMOJI_CODE_POINT = 0x1F000
LAST_EMOJI_CODE_POINT = 0x1FAFF
GIT_TIMEOUT_SECONDS = 30


def is_emoji_part(character: str) -> bool:
    """Tell whether a character can stand next to a joiner inside an emoji.

    Args:
        character: One character.

    Returns:
        True for a symbol (category So), an emoji code point or the emoji
        variation selector.
    """
    if character == VARIATION_SELECTOR_16:
        return True
    code_point = ord(character)
    if FIRST_EMOJI_CODE_POINT <= code_point <= LAST_EMOJI_CODE_POINT:
        return True
    return unicodedata.category(character) == "So"


def raw_character_problems(text: str) -> list[str]:
    """Return one message per raw invisible character a text holds.

    Args:
        text: The text written, or a file's content.

    Returns:
        "line L, column C: U+XXXX NAME" for each character of the categories
        Cf, Cc, Zs, Zl and Zp other than the plain space, the line feed, the tab and a
        zero-width joiner between two emoji parts; empty when there is none.
    """
    problems: list[str] = []
    line_number = 1
    column_number = 0
    for index, character in enumerate(text):
        column_number += 1
        if character == "\n":
            line_number += 1
            column_number = 0
            continue
        if character in ALLOWED_RAW_CHARACTERS:
            continue
        if unicodedata.category(character) not in RAW_CHARACTER_CATEGORIES:
            continue
        joins_emoji = (
            character == ZERO_WIDTH_JOINER
            and 0 < index < len(text) - 1
            and is_emoji_part(text[index - 1])
            and is_emoji_part(text[index + 1])
        )
        if joins_emoji:
            continue
        name = CONTROL_CHARACTER_NAMES.get(character)
        if name is None:
            name = unicodedata.name(character, "UNNAMED")
        problems.append(
            f"line {line_number}, column {column_number}: "
            f"U+{ord(character):04X} {name}"
        )
    return problems


def written_texts(tool_input: dict[str, object]) -> list[str]:
    """Return the texts an Edit, MultiEdit, Write or NotebookEdit call writes.

    Args:
        tool_input: The tool's input from the hook input.

    Returns:
        The new strings, content or cell source the call writes.
    """
    texts: list[str] = []
    for key in ("new_string", "content", "new_source"):
        value = tool_input.get(key)
        if isinstance(value, str):
            texts.append(value)
    edits = tool_input.get("edits")
    if isinstance(edits, list):
        for edit in edits:
            if isinstance(edit, dict):
                new_string = edit.get("new_string")
                if isinstance(new_string, str):
                    texts.append(new_string)
    return texts


def check_repository(project_root: Path) -> int:
    """Scan every file git tracks for raw invisible characters.

    Args:
        project_root: The checkout to scan.

    Returns:
        0 when no tracked text file holds one, else 1.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=project_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=GIT_TIMEOUT_SECONDS,
        check=True,
    )
    file_count = 0
    problem_count = 0
    for relative_path in result.stdout.split("\0"):
        file_path = project_root / relative_path
        if not relative_path or not file_path.is_file():
            continue
        try:
            text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # A binary file (an image, a font): not text to read.
            continue
        file_count += 1
        for problem in raw_character_problems(text):
            print(f"FAIL: {relative_path}, {problem}")
            problem_count += 1
    if problem_count:
        print(
            f"{problem_count} raw invisible character(s): write each as a "
            "\\N{NAME} escape (CLAUDE.md, Code standards)."
        )
        return 1
    print(f"OK: no raw invisible character in {file_count} tracked text files")
    return 0


def find_checkout_root(path: Path) -> Path | None:
    """Return the checkout that holds a path, or None outside any checkout.

    A checkout is the main tree or a git worktree: a folder with both
    pyproject.toml and .git (a folder in the main tree, a file in a worktree).

    Args:
        path: An absolute path; it need not exist yet.
    """
    for candidate in [path, *path.parents]:
        has_project = (candidate / "pyproject.toml").is_file()
        if has_project and (candidate / ".git").exists():
            return candidate
    return None


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
    """Scan the repository, or judge one edit from the hook input on stdin.

    With `--check-repository` (the gate's static step), scan every tracked
    file; with no argument (the PreToolUse hook), read the hook input and allow
    or block the edit.

    Returns:
        The exit code: 0 to allow, 2 to block, 1 on a problem of the hook.
    """
    arguments = sys.argv[1:]
    if arguments == ["--check-repository"]:
        return check_repository(Path(__file__).resolve().parents[2])
    if arguments:
        print(
            f"guard_paths: unknown arguments {arguments}; "
            "use --check-repository or none.",
            file=sys.stderr,
        )
        return 1
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        print("guard_paths: hook input was not valid JSON.", file=sys.stderr)
        return 1

    role_name = str(hook_input.get("agent_type") or "")
    tool_input = hook_input.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return 0
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path:
        return 0

    working_directory = Path(str(hook_input.get("cwd") or Path.cwd()))
    target_path = Path(str(raw_path))
    if not target_path.is_absolute():
        target_path = working_directory / target_path
    target_path = target_path.resolve()

    project_root = find_checkout_root(target_path.parent)
    if project_root is None:
        # Outside any checkout (scratch files, temp folders): not this hook's job.
        return 0
    relative_path = target_path.relative_to(project_root).as_posix()

    problems: list[str] = []
    for text in written_texts(tool_input):
        problems.extend(raw_character_problems(text))
    if problems:
        listed = "; ".join(problems[:LISTED_PROBLEMS])
        if len(problems) > LISTED_PROBLEMS:
            listed += f"; and {len(problems) - LISTED_PROBLEMS} more"
        print(
            f"Blocked: the text written to '{relative_path}' holds a raw "
            f"invisible character ({listed}). Write each one as a \\N{{NAME}} "
            'escape, for example "\\N{NO-BREAK SPACE}" (CLAUDE.md, Code '
            "standards), or as an escape of the file's own language.",
            file=sys.stderr,
        )
        return 2

    allowed_paths = resolve_allowed_paths(role_name)
    if allowed_paths is None:
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
