"""Test of viewport AC-2 (rule 3): a pinch goes on from where it was when a third finger
joins and one leaves, with no jump of the zoom.

No spec change: the fix is to `GridViewport.svelte`, which kept the distance of the
first two fingers as its baseline, so that after a third finger had come and one of
the first two had left, the pair left on the screen was measured against the old
pair and the zoom jumped. The criterion's words are the rule's: "Two fingers multiply
the zoom by the ratio of their distances".

The room is spec 042's mocked room on FX-02, in spec 019's touch context at 360 by 740;
the fingers go through the Chrome DevTools Protocol, as the pinches of AC-2 do, so the
test runs in Chromium only.

The gesture, in finger positions around the viewport's centre (x, y):

1. Two fingers, A and B, 100 px apart, go to 150 px apart: the zoom is 1.5.
2. A third finger, C, comes down 200 px under A. Nothing moves, so nothing zooms.
3. B leaves. The pair left is A and C, 200 px apart. The zoom stays 1.5: it does not
   jump to 2, the 200 px read against the 100 px the first pair started from.
4. C moves down by 40 px: the pair goes from 200 to 240 px apart, 1.2 times as far,
   and the zoom goes from 1.5 to 1.8.

Readings where the spec leaves room:

- Chromium's `Input.dispatchTouchEvent` presses a point whose id is new in a
  `touchMove`, and releases the points named in a `touchEnd`; a point missing from a
  `touchMove` is not released.
- The zoom is `data-zoom` of the grid's viewport, read to within 0.06 as the pinch
  tests of AC-2 read it.
- A pinch that does not take the zoom above the maximum: FX-02's is above 3.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, CDPSession, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import grid_view
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of, me, open_room

PHONE_WIDTH = 360
PHONE_HEIGHT = 740
ZOOM_TOLERANCE = 0.06
GAP_START = 100.0
GAP_AFTER_PINCH = 150.0
THIRD_FINGER_UNDER_FIRST = 200.0
THIRD_FINGER_MOVE = 40.0
MOVE_STEPS = 8

Finger = dict[str, float]


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


def finger(identifier: int, x: float, y: float) -> Finger:
    """One touch point for `Input.dispatchTouchEvent`."""
    return {"x": x, "y": y, "id": identifier}


def send_touch(session: CDPSession, kind: str, points: list[Finger]) -> None:
    """Send one touch event with the fingers now on the screen."""
    session.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})


def zoom_of(viewport: Locator) -> float:
    """The zoom the grid's viewport reports."""
    value = viewport.get_attribute("data-zoom")
    assert value is not None
    return float(value)


def wait_two_frames(page: Page) -> None:
    """Wait until the page has drawn two frames, so a zoom is on the attribute."""
    page.evaluate(
        "() => new Promise(done => requestAnimationFrame("
        "() => requestAnimationFrame(() => done(null))))"
    )


@pytest.mark.only_browser("chromium")
def test_ac2_a_pinch_goes_on_from_where_it_was_when_a_third_finger_joins_and_one_leaves(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = window(PHONE_WIDTH, PHONE_HEIGHT, True)
    open_room(page, live_server, grid_view(fx02_grid), [me()])
    viewport = page.get_by_test_id("grid-viewport")
    expect(viewport).to_have_attribute("data-zoom", "1")
    box = box_of(viewport)
    centre_x = box.centre_x
    centre_y = box.centre_y
    first_x = centre_x - GAP_AFTER_PINCH / 2
    second_x = centre_x + GAP_AFTER_PINCH / 2
    third_y = centre_y + THIRD_FINGER_UNDER_FIRST
    session = page.context.new_cdp_session(page)
    try:
        send_touch(
            session,
            "touchStart",
            [
                finger(0, centre_x - GAP_START / 2, centre_y),
                finger(1, centre_x + GAP_START / 2, centre_y),
            ],
        )
        for step in range(1, MOVE_STEPS + 1):
            gap = GAP_START + (GAP_AFTER_PINCH - GAP_START) * step / MOVE_STEPS
            send_touch(
                session,
                "touchMove",
                [
                    finger(0, centre_x - gap / 2, centre_y),
                    finger(1, centre_x + gap / 2, centre_y),
                ],
            )
        wait_two_frames(page)
        zoom_after_pinch = zoom_of(viewport)

        send_touch(
            session,
            "touchMove",
            [
                finger(0, first_x, centre_y),
                finger(1, second_x, centre_y),
                finger(2, first_x, third_y),
            ],
        )
        send_touch(session, "touchEnd", [finger(1, second_x, centre_y)])
        send_touch(
            session,
            "touchMove",
            [finger(0, first_x, centre_y), finger(2, first_x, third_y + 1)],
        )
        wait_two_frames(page)
        zoom_after_the_change = zoom_of(viewport)

        for step in range(1, MOVE_STEPS + 1):
            moved = third_y + THIRD_FINGER_MOVE * step / MOVE_STEPS
            send_touch(
                session,
                "touchMove",
                [finger(0, first_x, centre_y), finger(2, first_x, moved)],
            )
        wait_two_frames(page)
        zoom_after_going_on = zoom_of(viewport)
        send_touch(session, "touchEnd", [])
    finally:
        session.detach()

    assert zoom_after_pinch == pytest.approx(1.5, abs=ZOOM_TOLERANCE)
    assert zoom_after_the_change == pytest.approx(zoom_after_pinch, abs=ZOOM_TOLERANCE)
    assert zoom_after_going_on == pytest.approx(
        zoom_after_pinch * 1.2, abs=2 * ZOOM_TOLERANCE
    )
