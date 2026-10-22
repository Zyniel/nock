"""Wait until a page's fonts are loaded (spec 041, "Edge cases and errors").

With `font-display: swap`, a text is first drawn in the fallback font, which
differs per OS (Segoe UI on Windows, DejaVu Sans in CI), so a size or a position
read then differs per OS too. So every shared helper of `tests/` that opens a page
and returns once it shows its content calls `wait_for_fonts` before it returns,
and a test that reads a size or a position that depends on text calls it again
after a change that shows a face not shown before (an italic pencil letter, a clue
cell's condensed face, a bold text). A test that only reads colours, computed
styles or texts needs no wait.

Pytest does not collect this module (its name does not start with `test_`).
"""

from __future__ import annotations

from playwright.sync_api import Page

FONTS_READY_SCRIPT = "() => document.fonts.ready.then(() => true)"


def wait_for_fonts(page: Page) -> None:
    """Wait for `document.fonts.ready` on `page`.

    Args:
        page: A page that shows the text a test is about to measure.
    """
    page.evaluate(FONTS_READY_SCRIPT)
