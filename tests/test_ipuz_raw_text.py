"""Tests of content/ipuz AC-17 and AC-18: the raw text of a file.

A duplicate key and a byte order mark cannot be written through the plain data a
test changes (a Python dict holds a key once), so these tests work on the JSON
text that `grid_files_harness.dump` gives. The shared setup is in
`grid_files_harness`.

Choices where the spec leaves room:

- AC-18: a file's bytes are read as UTF-8, so U+FEFF at the start of the text
  stands for the bytes `EF BB BF`; `read_ipuz` is given that text.
"""

from __future__ import annotations

import pytest

from grid_files_harness import (
    clue_named,
    dump,
    fx01_ipuz_data,
)
from nock.ipuz import IpuzError, read_ipuz

BYTE_ORDER_MARK = "\N{ZERO WIDTH NO-BREAK SPACE}"

# ---- AC-17: a key written twice ---------------------------------------------------


def written_twice(text: str, member: str, second: str | None = None) -> str:
    """Write the `"key": value` member of a JSON text a second time after itself.

    Args:
        text: JSON text holding `member` exactly once.
        member: The member to repeat, as `dump` writes it.
        second: The text of the second member, `member` itself by default.

    Returns:
        The text with the member written twice in a row.
    """
    assert text.count(member) == 1, member
    again = member if second is None else second
    return text.replace(member, f"{member}, {again}")


@pytest.mark.parametrize(
    ("member", "second", "key"),
    [
        pytest.param('"author": "Équipe Nock"', None, "author", id="top-level"),
        pytest.param(
            '"author": "Équipe Nock"', '"author": "Autre"', "author", id="other-value"
        ),
        pytest.param('"answer": "SENT"', None, "answer", id="clue"),
    ],
)
def test_ac17_a_key_written_twice_is_refused_naming_it(
    member: str, second: str | None, key: str
) -> None:
    text = written_twice(dump(fx01_ipuz_data()), member, second)

    with pytest.raises(IpuzError) as error_info:
        read_ipuz(text)

    assert key in str(error_info.value)


@pytest.mark.parametrize("where", ["top", "clues", "clue"])
def test_ac17_a_namespaced_key_twice_in_one_object_is_refused(where: str) -> None:
    data = fx01_ipuz_data()
    if where == "top":
        data["com.example:x"] = 1
    elif where == "clues":
        data["clues"]["com.example:x"] = 1
    else:
        clue_named(data, "Flaire")["com.example:x"] = 1
    member = '"com.example:x": 1'
    text = dump(data)
    assert text.count(member) == 1

    with pytest.raises(IpuzError) as error_info:
        read_ipuz(written_twice(text, member))

    assert "com.example:x" in str(error_info.value)


# ---- AC-18: a byte order mark ------------------------------------------------------


def test_ac18_a_byte_order_mark_at_the_start_is_refused_as_not_valid_json() -> None:
    text = BYTE_ORDER_MARK + dump(fx01_ipuz_data())

    with pytest.raises(IpuzError, match="not valid JSON"):
        read_ipuz(text)
