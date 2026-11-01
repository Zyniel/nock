"""Start a backlog task, or a board branch: its branch and its worktree.

Usage:
    uv run python scripts/start_item.py B-054              # a task's worktree
    uv run python scripts/start_item.py B-054 room-gone    # with your short name
    uv run python scripts/start_item.py --board <topic>    # a board's worktree

A task's number comes from the Backlog.md tool (`backlog task create`), which
reads the task files of every branch and worktree, so two sessions never get
the same one. A task starts from origin/main and its file must be there: a
milestone's tasks reach main when the human merges its pitch, and a task added
later reaches it through a board pull request.

- A task's branch is feat/b-NNN-<short-name>, made from origin/main in the
  worktree .claude/worktrees/b-NNN-<short-name> of the main checkout, so no
  session switches the branch of a checkout other sessions use. The short name
  comes from the task's title unless one is given.
- A task whose branch exists already, local or on origin, keeps it: the number
  and its branch never change. The script gives its worktree, made if missing.
- A board branch, backlog/<topic>, holds the edits of the backlog that belong
  to no task's branch: drafts, milestones, a task added to a milestone, an
  assignment. Its worktree is .claude/worktrees/backlog-<topic>.

Exit codes:
    0: the worktree is ready; its folder is printed.
    1: nothing was made, or git failed (the reason is printed).
    2: the command line is wrong.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REMOTE_NAME = "origin"
BASE_REF = f"{REMOTE_NAME}/main"
TASKS_FOLDER = "backlog/tasks"
# Under the main checkout, left out by .gitignore.
WORKTREES_FOLDER = Path(".claude") / "worktrees"

# A task as typed: B-054, b-54 or 54.
TASK_ID_PATTERN = re.compile(r"^(?:[Bb]-)?(\d{1,3})$")
# A task file: "b-054 - The-backlog-moves-to-the-Backlog.md-tool.md".
TASK_FILE_PATTERN = re.compile(r"^b-(\d{3}) - (.+)\.md$", re.IGNORECASE)
# The short name of a branch and its folder: room-gone, creator-rooms.
SHORT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# A short name made from a title keeps its first words, the small ones left out.
SHORT_NAME_WORDS = 5
SMALL_WORDS = frozenset({"a", "an", "and", "of", "on", "the", "to"})


class StartError(Exception):
    """A step failed; its message says why and what to do."""


def run_git(arguments: list[str]) -> str:
    """Run git in this checkout and return its standard output.

    Args:
        arguments: The git arguments, without "git".

    Returns:
        The standard output.

    Raises:
        StartError: git exited with a code other than 0.
    """
    completed = subprocess.run(
        ["git", *arguments],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        command_text = " ".join(["git", *arguments])
        raise StartError(f"'{command_text}' failed: {completed.stderr.strip()}")
    return completed.stdout


def find_main_checkout() -> Path:
    """Return the main checkout, which holds the git folder every worktree shares."""
    common_folder = run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"])
    return Path(common_folder.strip()).parent


def parse_task_number(task_text: str) -> int:
    """Return the number of a task as typed: B-054, b-54 or 54.

    Args:
        task_text: The task as given on the command line.

    Raises:
        StartError: the text names no task.
    """
    match = TASK_ID_PATTERN.match(task_text)
    if match is None:
        raise StartError(f"'{task_text}' is not a task: write it B-054.")
    return int(match.group(1))


def read_task_title(number: int) -> str:
    """Return a task's title as its file name on origin/main spells it.

    Args:
        number: The task number.

    Raises:
        StartError: origin/main holds no file of that task.
    """
    listing = run_git(["ls-tree", "-z", "--name-only", f"{BASE_REF}:{TASKS_FOLDER}"])
    for file_name in listing.split("\0"):
        match = TASK_FILE_PATTERN.match(file_name)
        if match is not None and int(match.group(1)) == number:
            return match.group(2)
    raise StartError(
        f"B-{number:03d} is not in {TASKS_FOLDER} on {BASE_REF}: a task starts "
        "once its file is merged (its milestone's pitch, or a board pull request)."
    )


def make_short_name(title: str) -> str:
    """Turn a title into a short name: its first words, lower case, joined by dashes.

    Args:
        title: A task title, for example "Sign-out-forgets-the-accounts-seats".

    Returns:
        The short name, for example "sign-out-forgets-accounts-seats".
    """
    decomposed = unicodedata.normalize("NFKD", title)
    ascii_title = decomposed.encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[a-z0-9]+", ascii_title.lower())
    kept_words: list[str] = []
    for word in words:
        if word not in SMALL_WORDS:
            kept_words.append(word)
    return "-".join(kept_words[:SHORT_NAME_WORDS])


def find_branches(prefix: str) -> tuple[set[str], set[str]]:
    """Return the local branches, and the branches on origin, with a name prefix.

    Args:
        prefix: The start of the branch names, for example feat/b-054-.
    """
    local_text = run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    remote_text = run_git(
        ["for-each-ref", "--format=%(refname)", f"refs/remotes/{REMOTE_NAME}"]
    )
    local_branches: set[str] = set()
    for branch_name in local_text.splitlines():
        if branch_name.startswith(prefix):
            local_branches.add(branch_name)
    remote_branches: set[str] = set()
    remote_ref_prefix = f"refs/remotes/{REMOTE_NAME}/"
    for ref_name in remote_text.splitlines():
        branch_name = ref_name.removeprefix(remote_ref_prefix)
        if branch_name.startswith(prefix):
            remote_branches.add(branch_name)
    return local_branches, remote_branches


def find_task_branch(number: int) -> str | None:
    """Return the branch a task has already, local or on origin, or None.

    Args:
        number: The task number.

    Raises:
        StartError: the task has more than one branch.
    """
    local_branches, remote_branches = find_branches(f"feat/b-{number:03d}-")
    branch_names = sorted(local_branches | remote_branches)
    if len(branch_names) > 1:
        raise StartError(
            f"B-{number:03d} has {len(branch_names)} branches "
            f"({', '.join(branch_names)}): keep one, then run the script again."
        )
    if branch_names:
        return branch_names[0]
    return None


def read_worktrees() -> dict[str, Path]:
    """Return the folder of each worktree that has a branch checked out, by branch."""
    porcelain_text = run_git(["worktree", "list", "--porcelain"])
    folders_by_branch: dict[str, Path] = {}
    current_folder: Path | None = None
    for line in porcelain_text.splitlines():
        if line.startswith("worktree "):
            current_folder = Path(line.removeprefix("worktree "))
        elif line.startswith("branch refs/heads/") and current_folder is not None:
            branch_name = line.removeprefix("branch refs/heads/")
            folders_by_branch[branch_name] = current_folder
    return folders_by_branch


def prepare_worktree(branch_name: str, folder_name: str) -> Path:
    """Return the worktree of a branch, making the worktree and the branch if needed.

    A branch that exists nowhere starts from origin/main.

    Args:
        branch_name: The branch, for example feat/b-054-backlog-import.
        folder_name: The worktree's folder under .claude/worktrees/ when one
            is made, for example b-054-backlog-import.

    Raises:
        StartError: a git step failed.
    """
    worktrees = read_worktrees()
    if branch_name in worktrees:
        return worktrees[branch_name]

    folder = find_main_checkout() / WORKTREES_FOLDER / folder_name
    local_branches, remote_branches = find_branches(branch_name)
    if branch_name in local_branches:
        run_git(["worktree", "add", str(folder), branch_name])
    elif branch_name in remote_branches:
        remote_branch = f"{REMOTE_NAME}/{branch_name}"
        run_git(
            [
                "worktree",
                "add",
                "--track",
                "-b",
                branch_name,
                str(folder),
                remote_branch,
            ]
        )
    else:
        run_git(["worktree", "add", "-b", branch_name, str(folder), BASE_REF])
    return folder


def holds_main(branch_name: str) -> bool:
    """Return whether a branch already holds every commit of origin/main.

    Args:
        branch_name: The local branch.
    """
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASE_REF, branch_name],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def start_task(task_text: str, short_name: str | None) -> tuple[str, Path]:
    """Return a task's branch and worktree, making them if needed.

    Args:
        task_text: The task as typed, for example B-054.
        short_name: The short name for a new branch, or None to make one from
            the task's title.

    Raises:
        StartError: the task or the short name is not valid, or a git step
            failed.
    """
    number = parse_task_number(task_text)
    if short_name is not None and SHORT_NAME_PATTERN.match(short_name) is None:
        raise StartError(
            f"'{short_name}' is not a short name: lower-case words joined by "
            "dashes, for example room-gone."
        )
    run_git(["fetch", REMOTE_NAME])
    title = read_task_title(number)

    branch_name = find_task_branch(number)
    if branch_name is None:
        if short_name is None:
            short_name = make_short_name(title)
        branch_name = f"feat/b-{number:03d}-{short_name}"
    worktree = prepare_worktree(branch_name, branch_name.removeprefix("feat/"))
    return branch_name, worktree


def start_board(topic: str) -> tuple[str, Path]:
    """Return a board branch and its worktree, making them if needed.

    Args:
        topic: What the board edits are about, for example milestone-hints.

    Raises:
        StartError: the topic is not a short name, or a git step failed.
    """
    if SHORT_NAME_PATTERN.match(topic) is None:
        raise StartError(
            f"'{topic}' is not a topic: lower-case words joined by dashes, for "
            "example milestone-hints."
        )
    run_git(["fetch", REMOTE_NAME])
    branch_name = f"backlog/{topic}"
    worktree = prepare_worktree(branch_name, f"backlog-{topic}")
    return branch_name, worktree


def parse_arguments() -> argparse.Namespace:
    """Read the command line; exit with code 2 when it is wrong."""
    parser = argparse.ArgumentParser(
        description="Start a backlog task, or a board branch, in a worktree."
    )
    parser.add_argument("task", nargs="?", help="the task, for example B-054")
    parser.add_argument(
        "short_name",
        nargs="?",
        help="the short name of a new branch, for example room-gone",
    )
    parser.add_argument(
        "--board", metavar="TOPIC", help="start the board branch backlog/TOPIC"
    )
    arguments = parser.parse_args()
    if arguments.board is not None and arguments.task is not None:
        parser.error("give a task or --board, not both")
    if arguments.board is None and arguments.task is None:
        parser.error("give a task, for example B-054, or --board TOPIC")
    return arguments


def main() -> int:
    """Start a task or a board branch; return the exit code."""
    arguments = parse_arguments()
    try:
        if arguments.board is not None:
            branch_name, worktree = start_board(arguments.board)
        else:
            branch_name, worktree = start_task(arguments.task, arguments.short_name)
        print(f"Branch:   {branch_name}")
        print(f"Worktree: {worktree.as_posix()}")
        print("Work only in that folder, by its absolute path.")
        if not holds_main(branch_name):
            print(f"The branch lacks commits of {BASE_REF}: merge it there first.")
    except StartError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
