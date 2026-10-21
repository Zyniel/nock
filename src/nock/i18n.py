"""Server-side texts (spec 033): the French texts of the web client's `fr.json`.

Every text a person reads comes from that one file (spec 040), the e-mails of the
server included.
"""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path

FR_JSON_PATH: Path = (
    Path(__file__).resolve().parents[2] / "web" / "src" / "i18n" / "fr.json"
)
# A placeholder of a text: a name between braces, such as {link}.
_PLACEHOLDER = re.compile(r"\{(\w+)\}")


@functools.cache
def _messages() -> dict[str, str]:
    """Return the texts of fr.json by key, read once."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def t(key: str, **values: object) -> str:
    """Return the French text of `key` from fr.json, as the client's `t` does.

    Each `{name}` with a value is replaced by `str(value)`; the others stay as
    written.

    Args:
        key: The key of the text, such as "email.sign_in.subject".
        **values: The values of the placeholders.

    Returns:
        The text with its placeholders filled in.

    Raises:
        KeyError: no such key.
    """
    text = _messages()[key]

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in values:
            return str(values[name])
        return match.group(0)

    return _PLACEHOLDER.sub(fill, text)
