"""A click that makes sure the press reached the page (not collected by pytest).

2026-10-23: Firefox under load sometimes loses the press of a click (the page
sees `focusin`, then only `mouseup`: no `mousedown`, no `click`), so a form is
never submitted. `click_until_pressed` clicks, checks that the page dispatched a
`click` event on the element, and clicks once more when it did not. It never
clicks twice when the first click reached the page, so a form is not submitted
twice.
"""

from __future__ import annotations

from playwright.sync_api import Error, Locator

# Sets `state.pressed` when a `click` lands on `element`. The listener
# is on the document (capture) so it survives a re-render that removes the
# element, and it removes itself at the first press.
WATCH_PRESS_SCRIPT = """
element => {
    const state = {pressed: false};
    const listener = event => {
        if (element.contains(event.target)) {
            state.pressed = true;
            document.removeEventListener('click', listener, true);
        }
    };
    document.addEventListener('click', listener, true);
    window.__sureClickState = state;
}
"""
READ_PRESS_SCRIPT = "() => window.__sureClickState.pressed"


def _press_arrived(target: Locator) -> bool:
    """Return whether the page dispatched a `click` on the watched element.

    Args:
        target: The locator passed to `click_until_pressed`.

    Returns:
        True when the click arrived. A page that cannot answer any more (it
        navigated away after the click) counts as clicked: only a click does that.
    """
    try:
        pressed = target.page.evaluate(READ_PRESS_SCRIPT)
    except Error:
        return True
    return pressed is True


def click_until_pressed(target: Locator, timeout: float | None = None) -> None:
    """Click `target`, once more if the first click never reached the page.

    Args:
        target: The element to click (a submit button).
        timeout: Playwright timeout in ms of each click; its default when None.

    Raises:
        AssertionError: When the element got no click after the second click.
    """
    target.evaluate(WATCH_PRESS_SCRIPT)
    target.click(timeout=timeout)
    if _press_arrived(target):
        return
    target.evaluate(WATCH_PRESS_SCRIPT)
    target.click(timeout=timeout)
    assert _press_arrived(
        target
    ), f"lost press: {target} received no click after two clicks"
