"""Wait until a page's fonts are loaded (spec 041, "Edge cases and errors").

With `font-display: swap`, a text is first drawn in the fallback font, which
differs per OS (Segoe UI on Windows, DejaVu Sans in CI), so a size or a position
read then differs per OS too. So every shared helper of `tests/` that opens a page
and returns once it shows its content calls `wait_for_fonts` before it returns,
and a test that reads a size or a position that depends on text calls it again
after a change that shows a face not shown before (an italic pencil letter, a clue
cell's condensed face, a bold text). A test that only reads colours, computed
styles or texts needs no wait.

A face is only asked for when the browser lays out a text that uses it, and the
layout may not have run yet since the change that showed the text: then
`document.fonts.ready` is already resolved and the face swaps in after the read
(B-100, 048 AC-5: the error line's weight 500). So the wait forces a layout
first, then waits for `document.fonts.ready`.

Pytest does not collect this module (its name does not start with `test_`).
"""

from __future__ import annotations

from playwright.sync_api import Page

FONTS_READY_SCRIPT = """
async () => {
  document.documentElement.getBoundingClientRect();
  await document.fonts.ready;
  return true;
}
"""


def wait_for_fonts(page: Page) -> None:
    """Wait until the fonts `page`'s text uses are loaded.

    Args:
        page: A page that shows the text a test is about to measure.
    """
    page.evaluate(FONTS_READY_SCRIPT)
