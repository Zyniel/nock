"""pytest plugin loaded by the quality gate: marks, and missing browsers left out.

Browser tests run once per engine, for the engines the gate passes with
`--browser` (see scripts/gate.py). Where an engine cannot be installed, such as
a sandbox whose network blocks the Playwright download, every test of that
engine fails at setup and the gate can never pass. This plugin deselects the
tests of an engine whose executable is missing and says so in the output.

It never hides a missing engine in CI (the CI environment variable is set),
and it fails the run when no engine at all is installed, so the browser tests
can never disappear silently. Human decision, 2026-10-13.

It also marks every test, so the gate can pick them with `-m` (2026-10-15):

- `browser`: the test runs in a browser engine (it has a `browser_name`
  parameter);
- `serial`: the test is timing-sensitive and runs after the parallel pass, on
  its own, because the load of parallel workers makes it flaky. The files are
  listed in SERIAL_TEST_FILES.

It warms each browser up once, before the first test that uses it (see
`warm_up_browser`). And with `--nock-specs 027,028` (the gate's `--specs`) it
leaves out the browser tests of every other spec (2026-10-16). A selector that
is not a number is a domain's test prefix: `--nock-specs grids,co_op` keeps
`test_grids_*.py` and `test_co_op_*.py` (2026-10-24, specs/_map.md).

For the gate's watchdog, results folder, `--resume` and `--shard` (B-107), it
takes five more options:

- `--nock-progress-dir DIR`: each process that runs tests (a pytest-xdist
  worker, or pytest itself without workers) keeps in `DIR/<worker>.txt` the
  test it is running and since when, so that the gate can say which tests
  were running when its watchdog stopped a pass;
- `--nock-results FILE`: the process that reports (the pytest-xdist
  controller, or pytest itself) appends one JSON line per phase of each test,
  flushed at once, so the file survives a stopped run;
- `--nock-skip-passed FILE`: leaves out the node ids listed in FILE, one per
  line (the gate's `--resume`);
- `--nock-left-out FILE`: with `--nock-skip-passed`, the process that
  collects writes in FILE how many tests of its selection it left out, so
  the gate knows whether a pass that ran nothing had passed tests to leave
  out;
- `--nock-shard I/N`: keeps only the I-th of N shards of the test files, the
  files sorted by path and dealt round robin (the gate's `--shard`). The
  files are those the run's `-m` selection keeps, so each of the gate's
  passes deals its own: a file with serial and parallel tests may fall in
  different shards in the two passes, and the N shards of a pass cover all
  its tests.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Generator
from datetime import datetime
from pathlib import Path
from typing import TextIO

import pytest
from playwright.sync_api import Browser, sync_playwright

ENGINE_NAMES: tuple[str, ...] = ("chromium", "firefox", "webkit")

# The spec number in a test file's name: tests/test_spec_027_ac05_display.py.
TEST_FILE_SPEC_PATTERN = re.compile(r"^test_spec_(\d{3})_")

# The browsers of this process already warmed up, by id (a session's browsers
# live until its end, so an id is never reused meanwhile).
warmed_browser_ids: set[int] = set()
WARM_UP_TIMEOUT_MS = 60_000

# Test files whose tests measure a duration or a pace (a latency percentile, a
# time budget, a time window, a pacing), and so run serially. A check that only
# waits up to a bound for a change (an `expect` within 300 ms) stays in the
# parallel pass unless it flakes there. The two scroll files time, in the page,
# how long a layout change takes to bring a list back to its end (300 ms at
# most); with four workers that once took 341 ms in WebKit on CI (2026-10-16).
# The relay of spec 015 (95 % within 100 ms) once failed in the parallel pass
# while another agent's browsers loaded the machine (2026-10-16); spec 013's
# relay, spec 026's solve budget and spec 034's highlight window (on at 4.5 s,
# gone at 6 s) and feed scroll measure durations too, as does spec 043's note
# lifetime (fading from 2.7 s, gone by 3.7 s; 2026-10-22) and spec 047's « Lien
# copié » line (gone 2 s after the copy; 2026-10-23). The live rooms' engine time
# (`platform/live-rooms.md` rule 1) times the room's rules in milliseconds,
# with no browser (B-030). Reconnection AC-9 times a hidden page's 2 s pings
# over 10 s of real time (B-101). The account's slow mail tests race 50 sends
# held 5 s against a route's and a join's answers (B-102).
SERIAL_TEST_FILES: frozenset[str] = frozenset(
    {
        "test_account_slow_mail.py",
        "test_erasure_busy.py",
        "test_records_history.py",
        "test_erasure_overlap.py",
        "test_erasure_retry.py",
        "test_operations_checkpoint_busy.py",
        "test_live_rooms_engine_time.py",
        "test_live_rooms_socket_responsiveness.py",
        "test_realtime_join_deadline.py",
        "test_reconnection_worker_pings.py",
        "test_foundation_remote_pace.py",
        "test_spec_013_ac02_selections.py",
        "test_spec_013_ac07_ac08_feed_scroll.py",
        "test_spec_015_ac01_relay_to_the_others.py",
        "test_spec_022_ac10_pacing.py",
        "test_spec_022_ac11_ac12_chat_list_scroll.py",
        "test_spec_026_ac01_ac03_grid_solved.py",
        "test_spec_027_ac02_ac03_live_pages.py",
        "test_spec_034_ac02_highlight_timing.py",
        "test_spec_034_ac04_feed_scroll.py",
        "test_spec_036_ac01_time_budgets.py",
        "test_spec_038_ac11_relay_time.py",
        "test_spec_043_ac26_note_lifetime.py",
        "test_spec_047_ac10_copied_line.py",
    }
)

# The engines found missing at configure time, filled by pytest_configure.
missing_engines: set[str] = set()
deselected_count = 0

# The worker name of a process run without pytest-xdist, in the progress and
# results files.
MAIN_PROCESS_NAME = "main"
# The progress file of this process, while it runs tests (--nock-progress-dir).
progress_path: Path | None = None
# The open results file of the reporting process (--nock-results).
results_file: TextIO | None = None


def find_missing_engines() -> set[str]:
    """Return the engines whose browser executable is not installed."""
    missing: set[str] = set()
    with sync_playwright() as playwright:
        for engine_name in ENGINE_NAMES:
            browser_type = getattr(playwright, engine_name)
            if not Path(browser_type.executable_path).exists():
                missing.add(engine_name)
    return missing


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add the gate's options: --nock-specs and those of its results folder."""
    parser.addoption(
        "--nock-specs",
        default="",
        help="Comma-separated spec numbers and domain test prefixes: run only "
        "their browser tests.",
    )
    parser.addoption(
        "--nock-progress-dir",
        default="",
        help="Folder where each process that runs tests names the test it runs.",
    )
    parser.addoption(
        "--nock-results",
        default="",
        help="File to append one JSON line to per phase of each test.",
    )
    parser.addoption(
        "--nock-skip-passed",
        default="",
        help="File of node ids, one per line, to leave out.",
    )
    parser.addoption(
        "--nock-left-out",
        default="",
        help="File to write the count of tests --nock-skip-passed left out to.",
    )
    parser.addoption(
        "--nock-shard",
        default="",
        help="I/N: run only the I-th of N shards of the test files.",
    )


def is_xdist_worker(config: pytest.Config) -> bool:
    """Tell whether this process is a pytest-xdist worker."""
    return hasattr(config, "workerinput")


def is_xdist_controller(config: pytest.Config) -> bool:
    """Tell whether this process hands the tests out to pytest-xdist workers."""
    if is_xdist_worker(config):
        return False
    return config.pluginmanager.hasplugin("dsession")


def pytest_configure(config: pytest.Config) -> None:
    """Register the marks, and open the results file."""
    global results_file
    config.addinivalue_line("markers", "browser: the test runs in a browser engine")
    config.addinivalue_line(
        "markers", "serial: timing-sensitive, runs after the parallel pass"
    )

    results_text = str(config.getoption("--nock-results"))
    if results_text and not is_xdist_worker(config):
        results_path = Path(results_text)
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_file = results_path.open("a", encoding="utf-8")


def pytest_sessionstart(session: pytest.Session) -> None:
    """Choose this process's progress file, when it runs tests.

    Decided here rather than in pytest_configure: pytest-xdist registers its
    controller ("dsession") in a pytest_configure of its own, which may run
    after this plugin's.
    """
    global progress_path
    config = session.config
    progress_folder_text = str(config.getoption("--nock-progress-dir"))
    if not progress_folder_text or is_xdist_controller(config):
        return
    progress_folder = Path(progress_folder_text)
    progress_folder.mkdir(parents=True, exist_ok=True)
    worker_name = os.environ.get("PYTEST_XDIST_WORKER", MAIN_PROCESS_NAME)
    progress_path = progress_folder / f"{worker_name}.txt"


def pytest_unconfigure() -> None:
    """Close the results file."""
    global results_file
    if results_file is not None:
        results_file.close()
        results_file = None


def pytest_runtest_logstart(nodeid: str) -> None:
    """Name the test this process starts in its progress file."""
    if progress_path is None:
        return
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    progress_path.write_text(f"{nodeid}\nstarted {started}\n", encoding="utf-8")


def pytest_runtest_logfinish() -> None:
    """Empty the progress file: this process runs no test any more."""
    if progress_path is None:
        return
    progress_path.unlink(missing_ok=True)


def worker_of(report: pytest.TestReport) -> str:
    """Return the pytest-xdist worker that ran a test, such as gw0, or "main"."""
    # The controller adds the worker's node to the reports it receives.
    worker_node = getattr(report, "node", None)
    gateway = getattr(worker_node, "gateway", None)
    worker_name = getattr(gateway, "id", None)
    if isinstance(worker_name, str):
        return worker_name
    return MAIN_PROCESS_NAME


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    """Append one phase of a test to the results file, at once."""
    if results_file is None:
        return
    line = {
        "nodeid": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
        "duration": round(report.duration, 3),
        "worker": worker_of(report),
    }
    results_file.write(json.dumps(line) + "\n")
    results_file.flush()


def engine_of(item: pytest.Item) -> str | None:
    """Return the browser engine a test runs in, or None for other tests."""
    callspec = getattr(item, "callspec", None)
    if callspec is None:
        return None
    return callspec.params.get("browser_name")


@pytest.fixture(autouse=True)
def warm_up_browser(request: pytest.FixtureRequest) -> None:
    """Before the first test of each browser, open a page in it and type a key.

    A browser just launched can be slow on its first page and its first key
    press: in CI, Firefox on Windows took over 10 s for the first `Enter` of the
    serial pass, which starts a fresh process with the timing-sensitive tests
    (2026-10-15). The warm-up takes that cost, with a generous timeout, in a
    context of its own that it closes, so that no test pays it.

    Args:
        request: The test's request; tests without a browser are left alone.
    """
    if "browser_name" not in request.fixturenames:
        return
    browser: Browser = request.getfixturevalue("browser")
    if id(browser) in warmed_browser_ids:
        return
    warmed_browser_ids.add(id(browser))
    context = browser.new_context()
    try:
        page = context.new_page()
        page.set_default_timeout(WARM_UP_TIMEOUT_MS)
        page.set_content('<input aria-label="warm-up">')
        field = page.get_by_role("textbox")
        field.fill("warm-up")
        field.press("Enter")
    finally:
        context.close()


# A wrapper: its code before `yield` runs before pytest's `-m` filter, so the
# marks are there for it; its code after runs after the filter, so a run without
# browser tests (the gate's `--tests other`) needs no engine at all. (pytest
# ignores hook functions whose name does not start with `pytest_`, so two
# functions with `specname` cannot do this.)
@pytest.hookimpl(wrapper=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> Generator[None]:
    """Mark the browser and serial tests, then leave out what is not run."""
    mark_items(items)
    yield
    deselect_other_specs(config, items)
    # The shards before the tests that passed: a file keeps its shard when
    # --resume leaves out tests, so the shards of a resumed run still cover
    # every file.
    deselect_other_shards(config, items)
    deselect_passed(config, items)
    deselect_missing_engines(config, items)


def mark_items(items: list[pytest.Item]) -> None:
    """Mark the browser tests and the serial tests."""
    for item in items:
        if engine_of(item) is not None:
            item.add_marker(pytest.mark.browser)
        if item.path.name in SERIAL_TEST_FILES:
            item.add_marker(pytest.mark.serial)


def spec_of(item: pytest.Item) -> str | None:
    """Return the spec number of a test's file, or None for other files."""
    match = TEST_FILE_SPEC_PATTERN.match(item.path.name)
    if match is None:
        return None
    return match.group(1)


def is_selected(item: pytest.Item, selectors: set[str]) -> bool:
    """Tell whether a test's file belongs to a selected spec or domain.

    Args:
        item: The test.
        selectors: Spec numbers, and domain test prefixes: a domain's test files
            are `test_<prefix>.py` and `test_<prefix>_*.py`.
    """
    spec_number = spec_of(item)
    if spec_number is not None:
        return spec_number in selectors
    file_name = item.path.name
    for selector in selectors:
        if file_name == f"test_{selector}.py":
            return True
        if file_name.startswith(f"test_{selector}_"):
            return True
    return False


def deselect_other_specs(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Leave out the browser tests of the specs not named in --nock-specs."""
    specs_text = str(config.getoption("--nock-specs"))
    if not specs_text:
        return
    wanted_specs = {part.strip() for part in specs_text.split(",") if part.strip()}
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if engine_of(item) is not None and not is_selected(item, wanted_specs):
            deselected.append(item)
        else:
            kept.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


def read_shard(shard_text: str) -> tuple[int, int]:
    """Return the shard number (1-based) and the shard count of "I/N".

    Raises:
        pytest.UsageError: When the text is not I/N with 1 <= I <= N.
    """
    number_text, _, count_text = shard_text.partition("/")
    if not number_text.isdigit() or not count_text.isdigit():
        raise pytest.UsageError(f"--nock-shard {shard_text}: expected I/N")
    shard_number = int(number_text)
    shard_count = int(count_text)
    if shard_count < 1 or not 1 <= shard_number <= shard_count:
        raise pytest.UsageError(
            f"--nock-shard {shard_text}: expected I/N with 1 <= I <= N"
        )
    return shard_number, shard_count


def deselect_other_shards(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep only the tests of the files of the shard --nock-shard names.

    The test files are sorted by path and dealt round robin: the file at
    position k (from 0) belongs to shard k % N + 1.
    """
    shard_text = str(config.getoption("--nock-shard"))
    if not shard_text:
        return
    shard_number, shard_count = read_shard(shard_text)
    paths = sorted({item.path for item in items})
    kept_paths: set[Path] = set()
    for position, path in enumerate(paths):
        if position % shard_count == shard_number - 1:
            kept_paths.add(path)
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.path in kept_paths:
            kept.append(item)
        else:
            deselected.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


def deselect_passed(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Leave out the tests whose node ids the --nock-skip-passed file lists."""
    skip_text = str(config.getoption("--nock-skip-passed"))
    if not skip_text:
        return
    passed_ids: set[str] = set()
    for line in Path(skip_text).read_text(encoding="utf-8").splitlines():
        if line.strip():
            passed_ids.add(line.strip())
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.nodeid in passed_ids:
            deselected.append(item)
        else:
            kept.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept
    left_out_text = str(config.getoption("--nock-left-out"))
    if left_out_text:
        # Every pytest-xdist worker collects the same tests: the same count.
        Path(left_out_text).write_text(f"{len(deselected)}\n", encoding="utf-8")


def deselect_missing_engines(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Deselect the tests of a missing engine; stop when that is not allowed."""
    global deselected_count
    selected_engines: set[str] = set()
    for item in items:
        engine_name = engine_of(item)
        if engine_name is not None:
            selected_engines.add(engine_name)
    if not selected_engines:
        return
    missing = find_missing_engines() & selected_engines
    if not missing:
        return
    names = ", ".join(sorted(missing))
    if os.environ.get("CI"):
        raise pytest.UsageError(
            f"browser engine(s) not installed: {names}. "
            "CI must run every engine: uv run playwright install --with-deps"
        )
    if missing == selected_engines:
        raise pytest.UsageError(
            f"no browser engine is installed (asked for: {names}). "
            "Run: uv run playwright install chromium firefox webkit"
        )
    missing_engines.update(missing)
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if engine_of(item) in missing_engines:
            deselected.append(item)
        else:
            kept.append(item)
    config.hook.pytest_deselected(items=deselected)
    items[:] = kept
    deselected_count = len(deselected)


def pytest_sessionfinish(session: pytest.Session) -> None:
    """In a pytest-xdist worker, hand the left-out engines to the controller."""
    worker_output = getattr(session.config, "workeroutput", None)
    if worker_output is None:
        return
    worker_output["missing_engines"] = sorted(missing_engines)
    worker_output["deselected_count"] = deselected_count


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node: object, error: object) -> None:
    """In the pytest-xdist controller, gather what each worker left out."""
    global deselected_count
    worker_output = getattr(node, "workeroutput", None)
    if not isinstance(worker_output, dict):
        return
    missing_engines.update(worker_output.get("missing_engines", []))
    # Every worker collects, and so deselects, the same tests.
    deselected_count = max(deselected_count, worker_output.get("deselected_count", 0))


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Warn, at the end of the run, which engines were left out."""
    if not missing_engines:
        return
    names = ", ".join(sorted(missing_engines))
    terminalreporter.write_sep(
        "=",
        f"WARNING: {deselected_count} test(s) not run, engine(s) not installed: "
        f"{names}. CI runs them.",
        yellow=True,
    )
