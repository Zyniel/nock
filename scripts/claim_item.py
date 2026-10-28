"""Claim the next backlog item: its number, its branch and its worktree.

Usage:
    uv run python scripts/claim_item.py <short-name>   # claim B-NNN and its worktree
    uv run python scripts/claim_item.py --list         # list the items in flight

A brief reaches `Backlog.md` on `main` only when its pull request merges, so
the next number read from there is the same for every session that writes a
brief meanwhile. On 2026-10-28 six sessions working in parallel took B-016 to
B-018 more than once, then renumbered one another's items, branches and commits
until B-020 had two owners. Hence one claim, made once:

- The number is one more than the highest number main's `Backlog.md`, main's
  commit subjects, any item branch (local or on origin) or any claim names. A
  number is never given twice, and a dropped item leaves a gap.
- The claim is the ref refs/items/b-NNN, which git creates only when it does
  not exist yet: of two sessions that claim at the same moment, one gets the
  number and the other the next one. Every worktree of this clone shares it.
- The item's branch feat/b-NNN-<short-name> starts from origin/main in the
  worktree .claude/worktrees/b-NNN-<short-name> of the main checkout, so no
  session switches the branch of a checkout that other sessions use.

The script then lists the other items in flight (with a branch or a claim, and
not on main yet) and the spec files each one changes, so the brief can name an
overlap. A claim is local to this clone: a cloud session sees another machine's
items only once their branches are pushed.

Exit codes:
    0: the item is claimed, or the list is printed.
    1: nothing was claimed, or git failed (the reason is printed).
    2: the command line is wrong.
"""

from __future__ import annotations

import argparse
import contextlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Items start from the remote main, fetched first.
REMOTE_NAME = "origin"
BASE_REF = f"{REMOTE_NAME}/main"
BACKLOG_FILE = "Backlog.md"
CLAIM_REF_PREFIX = "refs/items/b-"
# Under the main checkout, left out by .gitignore.
WORKTREES_FOLDER = Path(".claude") / "worktrees"
# The paths whose overlap the list reports.
SPEC_PATHS: tuple[str, ...] = ("specs",)
# Two sessions claiming at once cost one attempt; more means something is wrong.
CLAIM_ATTEMPTS = 5

# An item's heading in Backlog.md: ### B-016 Creator rooms and host return
ITEM_HEADING_PATTERN = re.compile(r"^### B-(\d{3}) ", re.MULTILINE)
# An item named in a commit subject: docs: the human's decisions on B-006
ITEM_MENTION_PATTERN = re.compile(r"\bB-(\d{3})\b")
# The last commit of an item's build (.claude/skills/feature/SKILL.md).
ITEM_CLOSE_PATTERN = re.compile(r"\bclose B-(\d{3})\b")
# An item branch, local or on origin: refs/heads/feat/b-016-creator-rooms
ITEM_BRANCH_PATTERN = re.compile(
    rf"^refs/(?:heads|remotes/{REMOTE_NAME})/(feat/b-(\d{{3}})-.+)$"
)
CLAIM_REF_PATTERN = re.compile(rf"^{re.escape(CLAIM_REF_PREFIX)}(\d{{3}})$")
# The short name of a branch and its folder: room-gone, creator-rooms.
SHORT_NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ClaimError(Exception):
    """A step failed; its message says why and what to do."""


@dataclass
class ItemInFlight:
    """An item with a branch or a claim that main does not know yet."""

    number: int
    # Branch names (feat/b-NNN-...) and the worktree of each, when it has one.
    branches: dict[str, Path | None] = field(default_factory=dict)
    spec_files: set[str] = field(default_factory=set)


def run_git(arguments: list[str], folder: Path = PROJECT_ROOT) -> str:
    """Run git in a folder and return its standard output.

    Args:
        arguments: The git arguments, without "git".
        folder: The checkout to run in.

    Returns:
        The standard output.

    Raises:
        ClaimError: git exited with a code other than 0.
    """
    completed = subprocess.run(
        ["git", *arguments],
        cwd=folder,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed.returncode != 0:
        command_text = " ".join(["git", *arguments])
        raise ClaimError(f"'{command_text}' failed: {completed.stderr.strip()}")
    return completed.stdout


def item_label(number: int) -> str:
    """Return an item's name in Backlog.md, for example B-016.

    Args:
        number: The item number.
    """
    return f"B-{number:03d}"


def claim_ref_name(number: int) -> str:
    """Return the ref that claims an item number, for example refs/items/b-016.

    Args:
        number: The item number.
    """
    return f"{CLAIM_REF_PREFIX}{number:03d}"


def find_main_checkout() -> Path:
    """Return the main checkout, which holds the git folder every worktree shares."""
    common_folder = run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"])
    return Path(common_folder.strip()).parent


def read_main_numbers() -> tuple[set[int], set[int]]:
    """Read the item numbers that main knows.

    Returns:
        The numbers named by main's Backlog.md or by any commit subject of main,
        and among them those of items main holds: an item heading in
        Backlog.md, or a "close B-NNN" commit for an item gone from it since.
    """
    backlog_text = run_git(["show", f"{BASE_REF}:{BACKLOG_FILE}"])
    subjects_text = run_git(["log", BASE_REF, "--format=%s"])

    held_numbers: set[int] = set()
    for match in ITEM_HEADING_PATTERN.finditer(backlog_text):
        held_numbers.add(int(match.group(1)))
    for match in ITEM_CLOSE_PATTERN.finditer(subjects_text):
        held_numbers.add(int(match.group(1)))

    named_numbers = set(held_numbers)
    for match in ITEM_MENTION_PATTERN.finditer(subjects_text):
        named_numbers.add(int(match.group(1)))
    return named_numbers, held_numbers


def read_item_branches() -> dict[int, set[str]]:
    """Return the item branches, local or on origin, by item number."""
    refs_text = run_git(
        ["for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes"]
    )
    branches_by_number: dict[int, set[str]] = {}
    for ref_name in refs_text.splitlines():
        match = ITEM_BRANCH_PATTERN.match(ref_name)
        if match is None:
            continue
        number = int(match.group(2))
        branches_by_number.setdefault(number, set()).add(match.group(1))
    return branches_by_number


def read_claimed_numbers() -> set[int]:
    """Return the numbers of every claim ref."""
    refs_text = run_git(["for-each-ref", "--format=%(refname)", "refs/items"])
    claimed_numbers: set[int] = set()
    for ref_name in refs_text.splitlines():
        match = CLAIM_REF_PATTERN.match(ref_name)
        if match is not None:
            claimed_numbers.add(int(match.group(1)))
    return claimed_numbers


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


def read_local_branches() -> set[str]:
    """Return the names of the local branches."""
    refs_text = run_git(["for-each-ref", "--format=%(refname:short)", "refs/heads"])
    return set(refs_text.splitlines())


def read_spec_files(branch_ref: str, worktree: Path | None) -> set[str]:
    """Return the spec files a branch changes, committed or not, since main.

    Args:
        branch_ref: The branch, feat/b-NNN-..., or its origin copy.
        worktree: The folder where it is checked out, or None.
    """
    changed_text = run_git(
        ["diff", "--name-only", f"{BASE_REF}...{branch_ref}", "--", *SPEC_PATHS]
    )
    spec_files = set(changed_text.splitlines())
    if worktree is not None and worktree.is_dir():
        uncommitted_text = run_git(
            ["diff", "--name-only", "HEAD", "--", *SPEC_PATHS], worktree
        )
        untracked_text = run_git(
            ["ls-files", "--others", "--exclude-standard", "--", *SPEC_PATHS],
            worktree,
        )
        spec_files.update(uncommitted_text.splitlines())
        spec_files.update(untracked_text.splitlines())
    return spec_files


def find_used_numbers() -> set[int]:
    """Return every number main, a branch or a claim already names."""
    named_numbers, _ = read_main_numbers()
    used_numbers = set(named_numbers)
    used_numbers.update(read_item_branches())
    used_numbers.update(read_claimed_numbers())
    return used_numbers


def find_items_in_flight() -> list[ItemInFlight]:
    """Return the items with a branch or a claim that main does not hold yet."""
    _, held_numbers = read_main_numbers()
    branches_by_number = read_item_branches()
    folders_by_branch = read_worktrees()
    local_branches = read_local_branches()

    item_numbers = set(branches_by_number) | read_claimed_numbers()
    items: list[ItemInFlight] = []
    for number in sorted(item_numbers - held_numbers):
        item = ItemInFlight(number)
        for branch_name in sorted(branches_by_number.get(number, set())):
            worktree = folders_by_branch.get(branch_name)
            item.branches[branch_name] = worktree
            branch_ref = branch_name
            if branch_name not in local_branches:
                branch_ref = f"{REMOTE_NAME}/{branch_name}"
            item.spec_files.update(read_spec_files(branch_ref, worktree))
        items.append(item)
    return items


def print_items_in_flight(items: list[ItemInFlight]) -> None:
    """Print the items in flight, their spec files and the files they share.

    Args:
        items: The items to print.
    """
    if not items:
        print("No other item in flight.")
        return

    print(f"Items in flight (not on {BASE_REF} yet):")
    items_by_file: dict[str, list[str]] = {}
    for item in items:
        label = item_label(item.number)
        if not item.branches:
            print(f"  {label}  claimed, no branch")
        for branch_name, worktree in item.branches.items():
            if worktree is None:
                print(f"  {label}  {branch_name}")
            else:
                print(f"  {label}  {branch_name}  ({worktree.as_posix()})")
        if item.spec_files:
            print(f"          specs: {', '.join(sorted(item.spec_files))}")
        elif item.branches:
            print("          specs: none changed yet")
        for spec_file in item.spec_files:
            items_by_file.setdefault(spec_file, []).append(label)

    shared_files = []
    for spec_file, labels in sorted(items_by_file.items()):
        if len(labels) > 1:
            shared_files.append(f"{spec_file} ({', '.join(labels)})")
    if shared_files:
        print("Spec files changed by more than one item:")
        for shared_file in shared_files:
            print(f"  {shared_file}")


def claim_next_number(base_commit: str) -> int:
    """Create the claim ref of the next free number and return that number.

    Args:
        base_commit: The commit the claim points to, where the item starts.

    Raises:
        ClaimError: every attempt found its number claimed in the meantime.
    """
    # git creates a ref whose expected old value is all zeros only when the ref
    # does not exist yet, under a lock: two claims of one number cannot both win.
    absent_value = "0" * len(base_commit)
    for _ in range(CLAIM_ATTEMPTS):
        number = max(find_used_numbers(), default=0) + 1
        try:
            run_git(["update-ref", claim_ref_name(number), base_commit, absent_value])
        except ClaimError:
            continue
        return number
    raise ClaimError(
        f"{CLAIM_ATTEMPTS} claims in a row lost a race; run the script again."
    )


def claim_item(short_name: str) -> tuple[int, str, Path]:
    """Claim the next item and make its branch and worktree.

    Args:
        short_name: The name after the number: room-gone, creator-rooms.

    Returns:
        The number, the branch and the worktree folder.

    Raises:
        ClaimError: the short name is not valid, or a git step failed.
    """
    if SHORT_NAME_PATTERN.match(short_name) is None:
        raise ClaimError(
            f"'{short_name}' is not a short name: lower-case words joined by "
            "dashes, for example room-gone."
        )

    run_git(["fetch", REMOTE_NAME])
    base_commit = run_git(["rev-parse", BASE_REF]).strip()
    number = claim_next_number(base_commit)

    branch_name = f"feat/b-{number:03d}-{short_name}"
    worktree = find_main_checkout() / WORKTREES_FOLDER / f"b-{number:03d}-{short_name}"
    try:
        run_git(["worktree", "add", "-b", branch_name, str(worktree), base_commit])
    except ClaimError as error:
        undo_claim(number, branch_name, base_commit)
        message = f"{error}\nThe claim of {item_label(number)} is undone."
        raise ClaimError(message) from error
    return number, branch_name, worktree


def undo_claim(number: int, branch_name: str, base_commit: str) -> None:
    """Delete a claim, and the branch a refused worktree left behind.

    `git worktree add -b` makes the branch before it checks the folder. Each ref
    is deleted only while it still points at the base commit, so no commit is
    lost; a ref that does not exist is left alone.

    Args:
        number: The claimed number.
        branch_name: The item's branch.
        base_commit: The commit the claim and the branch point to.
    """
    for ref_name in (f"refs/heads/{branch_name}", claim_ref_name(number)):
        with contextlib.suppress(ClaimError):
            run_git(["update-ref", "-d", ref_name, base_commit])


def parse_arguments() -> argparse.Namespace:
    """Read the command line."""
    parser = argparse.ArgumentParser(
        description="Claim the next backlog item, or list the items in flight."
    )
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument(
        "short_name",
        nargs="?",
        help="the item's short name, for example room-gone",
    )
    action.add_argument(
        "--list", action="store_true", help="only list the items in flight"
    )
    return parser.parse_args()


def main() -> int:
    """Claim an item or list the items in flight; return the exit code."""
    arguments = parse_arguments()
    try:
        if arguments.list:
            run_git(["fetch", REMOTE_NAME])
            print_items_in_flight(find_items_in_flight())
            return 0

        number, branch_name, worktree = claim_item(arguments.short_name)
        print(f"Claimed {item_label(number)}.")
        print(f"  Branch:   {branch_name} (from {BASE_REF})")
        print(f"  Worktree: {worktree.as_posix()}")
        print("Work only in that folder. The number is final: never renumber it.")
        print()
        other_items = []
        for item in find_items_in_flight():
            if item.number != number:
                other_items.append(item)
        print_items_in_flight(other_items)
    except ClaimError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
