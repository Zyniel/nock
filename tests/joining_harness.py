"""Shared checks of the tests of `lobby/joining.md` about the nickname field (AC-4).

Pytest does not collect this module (its name does not start with `test_`). It holds
what the tests of spec 012 (AC-1) and spec 046 (AC-16), which prove AC-4, share:
while an error shows under the nickname field, the field is `aria-invalid` and
described by it; otherwise it has neither.

Readings where the spec leaves room:

- "Neither" is: `aria-invalid` is not `true`, and the field's accessible description
  is empty (so it has no `aria-describedby` to an element with text).
- "Described by that text" is: `aria-invalid` is `true` and the field's accessible
  description is exactly the text of the error.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

NICKNAME_FIELD_ID = "nickname-input"


def expect_field_neither_invalid_nor_described(page: Page) -> None:
    """Wait until the nickname field is not invalid and has no description."""
    field = page.get_by_test_id(NICKNAME_FIELD_ID)
    expect(field).not_to_have_attribute("aria-invalid", "true")
    expect(field).to_have_accessible_description("")


def expect_field_invalid_and_described_by(page: Page, error_text: str) -> None:
    """Wait until the nickname field is invalid and described by `error_text`."""
    field = page.get_by_test_id(NICKNAME_FIELD_ID)
    expect(field).to_have_attribute("aria-invalid", "true")
    expect(field).to_have_accessible_description(error_text)
