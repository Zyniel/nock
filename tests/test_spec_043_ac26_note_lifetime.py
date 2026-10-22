"""Tests of spec 043, AC-26: a 3-second note shows for 3 seconds, then fades and
leaves (work package WP-2).

"It still shows 2,700 ms after it appeared, has `data-off` and `opacity` 0 by
3,400 ms, and is gone by 3,700 ms": the times count from the moment the note
appeared. An in-page probe notes them with `performance.now()`, as spec 022 AC-4's
reaction probe does: a `MutationObserver` notes when `room-note` is added, when it
gets `data-off` and when it is removed, and a read at every animation frame notes
when its computed `opacity` first reads 0. The test then compares the noted
times, so the wait between the test and the page does not count.

The other checks of AC-26 are in `test_spec_043_ac26_notes.py`.

Choices where the spec leaves room:

- "Still shows 2,700 ms after it appeared": the note has no `data-off` (so it is
  not fading) and is on the page until then.
- The run is at 360 by 740, where the Salon is closed at load (AC-14).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec043_harness import (
    Reading,
    chat_frame,
    fx01_view,
    open_room,
    players_up_to,
    snapshot_frame,
)

STILL_SHOWS_MS = 2700  # "It still shows 2,700 ms after it appeared"
OFF_BY_MS = 3400  # "has `data-off` and `opacity` 0 by 3,400 ms"
GONE_BY_MS = 3700  # "and is gone by 3,700 ms"
PROBE_TIMEOUT_MS = 8000
PROBE_POLL_MS = 100

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- The probe ---------------------------------------------------------------------

# From now on, note in `window.spec043NoteProbe` when the first `room-note` appears,
# gets `data-off`, reads `opacity` 0 and leaves (`performance.now()` times), and the
# largest number of notes on the page at once.
START_PROBE_SCRIPT = r"""
() => {
  const probe = {appearedAt: null, offAt: null, transparentAt: null, goneAt: null,
    mostNotes: 0, done: false};
  window.spec043NoteProbe = probe;
  const read = () => {
    const now = performance.now();
    const found = document.querySelectorAll('[data-testid="room-note"]');
    probe.mostNotes = Math.max(probe.mostNotes, found.length);
    const note = found.length > 0 ? found[0] : null;
    if (note !== null && probe.appearedAt === null) {
      probe.appearedAt = now;
    }
    if (note !== null && probe.offAt === null && note.hasAttribute('data-off')) {
      probe.offAt = now;
    }
    if (note !== null && probe.offAt !== null && probe.transparentAt === null
        && getComputedStyle(note).opacity === '0') {
      probe.transparentAt = now;
    }
    if (note === null && probe.appearedAt !== null && probe.goneAt === null) {
      probe.goneAt = now;
    }
  };
  new MutationObserver(read).observe(document.body,
    {childList: true, subtree: true, attributes: true});
  const onFrame = () => {
    if (probe.done) {
      return;
    }
    read();
    requestAnimationFrame(onFrame);
  };
  requestAnimationFrame(onFrame);
}
"""
READ_PROBE_SCRIPT = "() => window.spec043NoteProbe"


def read_probe(page: Page) -> Reading:
    found = page.evaluate(READ_PROBE_SCRIPT)
    assert isinstance(found, dict), found
    return found


def wait_until_the_note_is_gone(page: Page) -> Reading:
    """Wait until the probe saw the note leave; return what it noted."""
    waited_ms = 0
    reading = read_probe(page)
    while reading["goneAt"] is None and waited_ms < PROBE_TIMEOUT_MS:
        page.wait_for_timeout(PROBE_POLL_MS)
        waited_ms += PROBE_POLL_MS
        reading = read_probe(page)
    page.evaluate("() => { window.spec043NoteProbe.done = true; }")
    return reading


def since_appeared(reading: Reading, name: str) -> float | None:
    """The time of the probe's `name` reading, in ms after the note appeared."""
    moment = reading[name]
    if moment is None:
        return None
    return float(moment) - float(reading["appearedAt"])


# ---- AC-26: the note's life --------------------------------------------------------


def test_ac26_a_note_shows_3_seconds_then_fades_and_leaves(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    mock = open_room(
        page, live_server, snapshot_frame(fx01_view(fx01_grid), players_up_to(3))
    )
    page.evaluate(START_PROBE_SCRIPT)

    mock.send(chat_frame(6, "p2", "IDES ?"))
    reading = wait_until_the_note_is_gone(page)

    assert reading["appearedAt"] is not None, "no room-note showed"
    off = since_appeared(reading, "offAt")
    transparent = since_appeared(reading, "transparentAt")
    gone = since_appeared(reading, "goneAt")
    assert reading["mostNotes"] == 1, reading
    assert off is not None, reading
    assert STILL_SHOWS_MS <= off <= OFF_BY_MS, reading
    assert transparent is not None, reading
    assert transparent <= OFF_BY_MS, reading
    assert gone is not None, reading
    assert STILL_SHOWS_MS <= gone <= GONE_BY_MS, reading
