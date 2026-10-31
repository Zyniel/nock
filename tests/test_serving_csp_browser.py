"""Tests of platform/serving, AC-11: the pages work under rule 12's policy.

Browser tests, in the engine pytest-playwright runs (the gate runs each of the
three), on the live server of spec 038's "Test harness" (`ops_live_server`: the
real build, a file database, FX-01 as grid 1, the operator pages on). One
parametrized test loads one page, does what the criterion says on it and reads
what the browser reported:

- `library`: `/`, until `catalogue-page` is `ready`.
- `room`: a room of FX-01 where Ana joins (`enter_room`) and types `T` in the
  cell (1, 0), which the room then holds.
- `ops`: `/ops`, the token given, until the page is `ready` (the dashboard).

How a violation is detected: a script added to the page before its own scripts
(`add_init_script`) listens to the document's `securitypolicyviolation` event, and
the page's console messages are kept; the test reads both once the page is done
and expects neither to report a blocked resource, style or script. Every response
the page received (documents, scripts, styles, fonts, API answers) must carry
rule 12's three headers, so that the page is really served under the policy, and
at least the document is among them.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import ConsoleMessage, Page, Response

from nock.catalogue import Catalogue
from nock.grid import Grid
from serving_harness import EDGE_HEADERS
from serving_harness import catalogue as catalogue
from serving_harness import fx01_grid as fx01_grid
from spec038_harness import (
    OpsServer,
    open_dashboard,
    ops_live_server,
    type_across,
    wait_for_room_letters,
)
from spec046_harness import open_catalogue

VIOLATION_RECORDER = """
window.__violations = [];
document.addEventListener('securitypolicyviolation', (event) => {
    window.__violations.push(
        event.violatedDirective + ' ' + event.blockedURI
    );
});
"""
# What the engines write in the console when a policy blocks something.
CONSOLE_MARKERS = ("content security policy", "content-security-policy", "refused to")
TYPED_CELL = (1, 0)
PAGES = ["library", "room", "ops"]


class Reports:
    """What a page reported: its console messages and the responses it got."""

    def __init__(self, page: Page) -> None:
        self.console_texts: list[str] = []
        self.responses: list[Response] = []
        page.on("console", self.keep_message)
        page.on("response", self.keep_response)

    def keep_message(self, message: ConsoleMessage) -> None:
        self.console_texts.append(message.text)

    def keep_response(self, response: Response) -> None:
        self.responses.append(response)

    def policy_messages(self) -> list[str]:
        """The console messages that speak of a policy."""
        found: list[str] = []
        for text in self.console_texts:
            lowered = text.lower()
            for marker in CONSOLE_MARKERS:
                if marker in lowered:
                    found.append(text)
                    break
        return found

    def responses_missing_headers(self) -> list[str]:
        """The URLs of the responses that lack one of rule 12's headers."""
        missing: list[str] = []
        for response in self.responses:
            carried = {name: response.headers.get(name) for name in EDGE_HEADERS}
            if carried != EDGE_HEADERS:
                missing.append(response.url)
        return missing

    def document_count(self) -> int:
        """The number of documents the page loaded."""
        return sum(
            1
            for response in self.responses
            if response.request.resource_type == "document"
        )


@pytest.fixture
def server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as running:
        yield running


def use_room(
    page: Page,
    server: OpsServer,
    grid: Grid,
    enter_room: Callable[..., None],
) -> None:
    """Ana joins a room of FX-01 and types `T`; wait until the room holds it."""
    code = server.registry.register_room(grid)
    enter_room(page, f"{server.base_url}/r/{code}", "Ana")
    row, column = TYPED_CELL
    type_across(page, row, column, "t")
    wait_for_room_letters(server.registry, code, {TYPED_CELL: "T"})


@pytest.mark.parametrize("kind", PAGES)
def test_ac11_the_pages_work_under_the_policy_with_no_violation(
    page: Page,
    server: OpsServer,
    fx01_grid: Grid,
    enter_room: Callable[..., None],
    kind: str,
) -> None:
    page.add_init_script(VIOLATION_RECORDER)
    reports = Reports(page)

    if kind == "library":
        open_catalogue(page, server.base_url)
    elif kind == "room":
        use_room(page, server, fx01_grid, enter_room)
    else:
        open_dashboard(page, server.base_url)

    violations = page.evaluate("window.__violations")
    assert violations == []
    assert reports.policy_messages() == []
    assert reports.document_count() >= 1
    assert reports.responses_missing_headers() == []
