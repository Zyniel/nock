"""pytest plugin loaded by the quality gate: leave out browsers that are missing.

Browser tests run once per engine (`--browser` in pyproject.toml, plus Firefox
through PYTEST_ADDOPTS in CI). Where an engine cannot be installed, such as a
sandbox whose network blocks the Playwright download, every test of that
engine fails at setup and the gate can never pass. This plugin deselects the
tests of an engine whose executable is missing and says so in the output.

It never hides a missing engine in CI (the CI environment variable is set),
and it fails the run when no engine at all is installed, so the browser tests
can never disappear silently. Human decision, 2026-10-13.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ENGINE_NAMES: tuple[str, ...] = ("chromium", "firefox", "webkit")

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


def requested_engines(config: pytest.Config) -> set[str]:
    """Return the engines the run asks for through --browser."""
    browser_option = config.getoption("--browser", default=None)
    if not browser_option:
        return {"chromium"}
    return set(browser_option)


def pytest_configure(config: pytest.Config) -> None:
    """Find the missing engines, and stop when none of the requested is there."""
    requested = requested_engines(config)
    missing = find_missing_engines() & requested
    if not missing:
        return
    names = ", ".join(sorted(missing))
    if os.environ.get("CI"):
        raise pytest.UsageError(
            f"browser engine(s) not installed: {names}. "
            "CI must run every engine: uv run playwright install --with-deps"
        )
    if missing == requested:
        raise pytest.UsageError(
            f"no browser engine is installed (asked for: {names}). "
            "Run: uv run playwright install chromium firefox webkit"
        )
    missing_engines.update(missing)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Deselect the tests that run in a missing engine."""
    global deselected_count
    if not missing_engines:
        return
    kept: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        callspec = getattr(item, "callspec", None)
        engine_name = None
        if callspec is not None:
            engine_name = callspec.params.get("browser_name")
        if engine_name in missing_engines:
            deselected.append(item)
        else:
            kept.append(item)
    if deselected:
        config.hook.pytest_deselected(items=deselected)
        items[:] = kept
    deselected_count = len(deselected)


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
