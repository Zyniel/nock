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
leaves out the browser tests of every other spec (2026-10-16).
"""

from __future__ import annotations

import os
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, sync_playwright

ENGINE_NAMES: tuple[str, ...] = ("chromium", "firefox", "webkit")

# The spec number in a test file's name: tests/test_spec_027_ac05_display.py.
TEST_FILE_SPEC_PATTERN = re.compile(r"^test_spec_(\d{3})_")

# The browsers of this process already warmed up, by id (a session's browsers
# live until its end, so an id is never reused meanwhile).
warmed_browser_ids: set[int] = set()
WARM_UP_TIMEOUT_MS = 60_000

# Test files whose tests measure time or pace, and so run serially. The two
# scroll files time, in the page, how long a layout change takes to bring a
# list back to its end (300 ms at most); with four workers that once took
# 341 ms in WebKit on CI (2026-10-16).
SERIAL_TEST_FILES: frozenset[str] = frozenset(
    {
        "test_spec_013_ac07_ac08_feed_scroll.py",
        "test_spec_022_ac10_pacing.py",
        "test_spec_022_ac11_ac12_chat_list_scroll.py",
        "test_spec_027_ac02_ac03_live_pages.py",
        "test_spec_036_ac01_time_budgets.py",
    }
)

# The engines found missing at configure time, filled by pytest_configure.
missing_engines: set[str] = set()
deselected_count = 0


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
    """Add --nock-specs, the gate's --specs."""
    parser.addoption(
        "--nock-specs",
        default="",
        help="Comma-separated spec numbers: run only their browser tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register the marks."""
    config.addinivalue_line("markers", "browser: the test runs in a browser engine")
    config.addinivalue_line(
        "markers", "serial: timing-sensitive, runs after the parallel pass"
    )


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


def deselect_other_specs(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Leave out the browser tests of the specs not named in --nock-specs."""
    specs_text = str(config.getoption("--nock-specs"))
    if not specs_text:
        return
    wanted_specs = {part.strip() for part in specs_text.split(",") if part.strip()}
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if engine_of(item) is not None and spec_of(item) not in wanted_specs:
            deselected.append(item)
        else:
            kept.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept


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
