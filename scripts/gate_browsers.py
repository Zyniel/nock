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
"""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ENGINE_NAMES: tuple[str, ...] = ("chromium", "firefox", "webkit")

# Test files whose tests measure time or pace, and so run serially.
SERIAL_TEST_FILES: frozenset[str] = frozenset(
    {
        "test_spec_022_ac10_pacing.py",
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


# A wrapper: its code before `yield` runs before pytest's `-m` filter, so the
# marks are there for it; its code after runs after the filter, so a run without
# browser tests (the gate's `--tests other`) needs no engine at all. (pytest
# ignores hook functions whose name does not start with `pytest_`, so two
# functions with `specname` cannot do this.)
@pytest.hookimpl(wrapper=True)
def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> Generator[None]:
    """Mark the browser and serial tests, then leave out missing engines."""
    mark_items(items)
    yield
    deselect_missing_engines(config, items)


def mark_items(items: list[pytest.Item]) -> None:
    """Mark the browser tests and the serial tests."""
    for item in items:
        if engine_of(item) is not None:
            item.add_marker(pytest.mark.browser)
        if item.path.name in SERIAL_TEST_FILES:
            item.add_marker(pytest.mark.serial)


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
