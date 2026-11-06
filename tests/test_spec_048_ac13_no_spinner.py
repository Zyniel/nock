"""Tests of spec 048, AC-13: no page of the client has a spinner or a skeleton.

They read files with Python only, as spec 041's colour scans do: the client
sources `web/src/**/*.svelte`, `*.ts` and `*.css` with their comments removed
(spec 041's `split_svelte`, `remove_script_comments` and `remove_css_comments`),
and the built CSS under `web/dist/assets/`, which the gate builds before pytest;
without `web/dist/index.html` the test fails with spec 040's message. The
samples of the criterion check the checker itself.

Readings of the spec's wording:

- `@keyframes` and `@-<vendor>-keyframes` (any letters as the vendor, such as
  `@-webkit-keyframes`) are matched without regard to case (CSS at-rules are not
  case sensitive).
- "A CSS declaration whose property, once a leading vendor prefix (`-webkit-`,
  `-moz-`, `-ms-`, `-o-`) is removed, is `animation` or starts with
  `animation-`" (the prefixes were added by the lead after review round 1): one
  of those prefixes or none, then the word `animation`, alone or followed by `-`
  and more letters, the whole not preceded by a letter, a digit, `-`, `_` or
  `.`, then optional spaces and a colon. So `animation:`, `animation-name:`,
  `-webkit-animation:` and `-moz-animation:` are flagged, and
  `-webkit-transition:` is not. In a script
  the same text is flagged too, wherever it is, since a style may be written
  there; a `.ts` name such as `animation: Animation` would be flagged as well.
- "The text `<progress`": `<progress` not followed by a letter, a digit, `-` or
  `_`, so `<progression` is not flagged; `role="progressbar"` with single or
  double quotes, spaces allowed around `=`.

The text scan cannot see an animation started at run time (DRAFT-013), so three
browser tests also ask the page of each state of spec 048 AC-14 (the states of
`open_account_state` and `open_ops_state`) for `document.getAnimations()` (as spec
046 AC-9 does): the shared recap, the account page and the ops page. A
CSS transition is left out, since the criterion accepts `transition` (its samples
`a{transition:opacity .25s}`); anything else running, such as an `element.animate`
call or a CSS animation, fails. The elements with `role="progressbar"` are counted
too.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec033_harness import AccountServer, account_live_server
from spec038_harness import OpsServer, ops_live_server
from spec041_harness import (
    WEB_DIST_ASSETS_DIR,
    remove_css_comments,
    remove_script_comments,
    require_build,
    source_files,
    split_svelte,
)
from spec048_harness import (
    open_account_state,
    open_share,
    open_share_loading,
    open_share_unavailable,
)
from spec048_ops_harness import open_ops_state

KEYFRAMES = re.compile(r"@(?:-[A-Za-z]+-)?keyframes\b", re.IGNORECASE)
ANIMATION_DECLARATION = re.compile(
    r"(?<![A-Za-z0-9_.\-])(?:-(?:webkit|moz|ms|o)-)?animation(?:-[A-Za-z-]+)?\s*:",
    re.IGNORECASE,
)
PROGRESS_ELEMENT = re.compile(r"<progress(?![A-Za-z0-9_\-])", re.IGNORECASE)
PROGRESSBAR_ROLE = re.compile(r"""role\s*=\s*(?:"progressbar"|'progressbar')""")

ACCOUNT_STATES = [
    "loading",
    "signing_in",
    "signed_in",
    "deletion_asked",
    "link_invalid",
    "signed_out_error",
    "signed_out_sent",
    "deleted",
    "error",
]
OPS_STATES = [
    "locked_refused",
    "loading",
    "error",
    "ready_position_4",
    "ready_empty",
    "replay_not_found",
]

# Counts the progress bars and the running animations other than CSS transitions.
RUN_TIME_SCRIPT = """() => [
    document.querySelectorAll('[role="progressbar"]').length,
    document.getAnimations().filter(
        animation => !(animation instanceof CSSTransition)
    ).length,
]"""

FLAGGED_SAMPLES = [
    "@keyframes spin{}",
    "@-webkit-keyframes spin{}",
    "a{animation:spin 1s}",
    "a{animation-name:spin}",
    "a{-webkit-animation:spin 1s}",
    "a{-moz-animation:spin 1s}",
    "a{-webkit-animation-name:spin}",
    '<progress value="1">',
    '<div role="progressbar">',
]
ACCEPTED_SAMPLES = [
    "a{transition:opacity .25s}",
    "a{-webkit-transition:opacity .25s}",
    "a{transition-duration:0s}",
    '<div role="status">',
    "<p>progression</p>",
]


def spinner_findings(text: str) -> list[str]:
    """What makes a text (comments removed) break the "no spinner" rule.

    Args:
        text: A source or built text with its comments already removed.

    Returns:
        One entry per kind of finding: `@keyframes`, an `animation` declaration,
        a `<progress` element or a `progressbar` role. Empty when none is found.
    """
    findings: list[str] = []
    if KEYFRAMES.search(text):
        findings.append("@keyframes")
    match = ANIMATION_DECLARATION.search(text)
    if match is not None:
        findings.append(f"declaration {match.group(0)!r}")
    if PROGRESS_ELEMENT.search(text):
        findings.append("<progress")
    if PROGRESSBAR_ROLE.search(text):
        findings.append('role="progressbar"')
    return findings


def css_findings(text: str) -> list[str]:
    """The findings of a CSS file: no `@keyframes` and no `animation` declaration."""
    css = remove_css_comments(text)
    findings: list[str] = []
    if KEYFRAMES.search(css):
        findings.append("@keyframes")
    match = ANIMATION_DECLARATION.search(css)
    if match is not None:
        findings.append(f"declaration {match.group(0)!r}")
    return findings


def source_text(path: Path) -> str:
    """A client source with its comments removed, as one text."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".svelte":
        parts = split_svelte(text)
        return "\n".join([*parts.scripts, *parts.styles, parts.markup])
    if path.suffix == ".css":
        return remove_css_comments(text)
    return remove_script_comments(text)


# ---- The checker's samples ----------------------------------------------------------


@pytest.mark.parametrize("sample", FLAGGED_SAMPLES)
def test_ac13_the_checker_flags_each_spinner_sample(sample: str) -> None:
    assert spinner_findings(sample) != []


@pytest.mark.parametrize("sample", ACCEPTED_SAMPLES)
def test_ac13_the_checker_accepts_each_harmless_sample(sample: str) -> None:
    assert spinner_findings(sample) == []


def test_ac13_the_checker_ignores_a_spinner_in_a_comment() -> None:
    css = "/* @keyframes spin{} a{animation:spin 1s} */ a{color:red}"
    script = '// role="progressbar"\nconst a = 1 /* <progress> */'

    assert spinner_findings(remove_css_comments(css)) == []
    assert spinner_findings(remove_script_comments(script)) == []


# ---- The client ------------------------------------------------------------------


def test_ac13_no_client_source_holds_a_spinner_or_an_animation() -> None:
    sources = source_files(".svelte", ".ts", ".css")
    found: dict[str, list[str]] = {}
    for path in sources:
        findings = spinner_findings(source_text(path))
        if findings:
            found[path.as_posix()] = findings

    assert len(sources) > 0
    assert found == {}


def test_ac13_no_built_css_holds_keyframes_or_an_animation() -> None:
    require_build()
    sheets = sorted(WEB_DIST_ASSETS_DIR.rglob("*.css"))
    found: dict[str, list[str]] = {}
    for path in sheets:
        findings = css_findings(path.read_text(encoding="utf-8"))
        if findings:
            found[path.name] = findings

    assert len(sheets) > 0
    assert found == {}


# ---- The client at run time ------------------------------------------------------


def run_time_problems(page: Page) -> list[str]:
    """How the page now breaks "no spinner, no animation" at run time.

    Args:
        page: A page in the state to check.

    Returns:
        One entry for the elements with `role="progressbar"` and one for the
        running animations other than CSS transitions. Empty when there are none.
    """
    found = page.evaluate(RUN_TIME_SCRIPT)
    assert isinstance(found, list), found
    progress_bars, animations = found
    problems: list[str] = []
    if progress_bars != 0:
        problems.append(f"{progress_bars} elements with role=progressbar")
    if animations != 0:
        problems.append(f"{animations} running animations")
    return problems


@pytest.mark.parametrize("state", ["loading", "unavailable", "loaded"])
def test_ac13_the_shared_recap_runs_no_animation_in_any_state(
    page: Page, live_server: str, state: str
) -> None:
    if state == "loading":
        open_share_loading(page, live_server)
    elif state == "unavailable":
        open_share_unavailable(page, live_server)
    else:
        open_share(page, live_server)

    assert run_time_problems(page) == []


@pytest.fixture
def account_server(tmp_path: Path, catalogue: Catalogue) -> Iterator[AccountServer]:
    with account_live_server(tmp_path, catalogue) as server:
        yield server


@pytest.mark.parametrize("state", ACCOUNT_STATES)
def test_ac13_the_account_page_runs_no_animation_in_any_state(
    page: Page, account_server: AccountServer, state: str
) -> None:
    open_account_state(page, account_server.base_url, state)

    assert run_time_problems(page) == []


@pytest.fixture
def ops_server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as server:
        yield server


@pytest.mark.parametrize("state", OPS_STATES)
def test_ac13_the_ops_page_runs_no_animation_in_any_state(
    page: Page, ops_server: OpsServer, fx01_grid: Grid, state: str
) -> None:
    open_ops_state(page, ops_server.base_url, state, fx01_grid)

    assert run_time_problems(page) == []
