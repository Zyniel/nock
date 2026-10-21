"""Settings the server reads from its environment (spec 038).

For now one setting: the operator token of NOCK_OPERATOR_TOKEN, which turns on
the operator pages (the dashboard and the replay of a room). The token is a
secret, so no message of this module ever holds its value.
"""

from __future__ import annotations

import string
from collections.abc import Mapping

OPERATOR_TOKEN_VARIABLE: str = "NOCK_OPERATOR_TOKEN"
OPERATOR_TOKEN_MIN_LENGTH: int = 32
OPERATOR_TOKEN_MAX_LENGTH: int = 256
# The characters of `secrets.token_urlsafe`: ASCII letters, ASCII digits, "_" and
# "-". They are explicit ASCII sets: str.isalnum() also accepts other scripts.
OPERATOR_TOKEN_CHARACTERS: frozenset[str] = frozenset(
    string.ascii_letters + string.digits + "_-"
)


class SettingsError(ValueError):
    """An environment variable holds a value the server cannot use.

    The message names the variable; it never holds the value of a secret.
    """


def operator_token_from_env(environ: Mapping[str, str]) -> str | None:
    """Return the operator token of `environ["NOCK_OPERATOR_TOKEN"]`.

    Args:
        environ: The environment to read, such as `os.environ`.

    Returns:
        The token, or None when the variable is unset or empty (operator pages off).

    Raises:
        SettingsError: the value is not 32 to 256 characters, each one of A-Z,
            a-z, 0-9, "_" and "-". The message names the variable and the rule
            broken, never the value.
    """
    token = environ.get(OPERATOR_TOKEN_VARIABLE, "")
    if token == "":
        return None
    if len(token) < OPERATOR_TOKEN_MIN_LENGTH or len(token) > OPERATOR_TOKEN_MAX_LENGTH:
        raise SettingsError(
            f"{OPERATOR_TOKEN_VARIABLE} must have {OPERATOR_TOKEN_MIN_LENGTH} to "
            f"{OPERATOR_TOKEN_MAX_LENGTH} characters"
        )
    for character in token:
        if character not in OPERATOR_TOKEN_CHARACTERS:
            raise SettingsError(
                f"{OPERATOR_TOKEN_VARIABLE} must be written with the letters A to Z "
                "and a to z, the digits 0 to 9, '_' and '-' only"
            )
    return token
