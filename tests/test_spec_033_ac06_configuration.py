"""Tests of spec 033, AC-6: accounts are configured by environment variables.

`account_settings_from_env` is called on plain dicts: accounts are off with no
public URL and no SMTP host, the valid settings give their `AccountSettings`, and
each invalid value raises `SettingsError` naming its variable. The messages follow
"Messages" of "Configuration": a refused value shows as `repr(value)`, except the
password, which never shows; a message about a missing variable shows no value of
its case; every message is one line with no character of categories Cc, Cf, Zl or
Zp; and `SECRET`, which both passwords of the criterion hold, appears in no message
and in no `repr` of valid settings.

`main()` runs with `uvicorn.Server.run` replaced by spec 036's recorder; each of its
cases sets or deletes every variable that `main()` reads. The app of `create_app`
is started with `TestClient` while `nock.server.AccountStore` is a subclass that
records the path of each account store built.

Edge cases checked as well: an app given no `accounts` reads the variables when it
starts and fails its startup with `SettingsError`, or turns accounts on; an app
given `accounts` reads none of them.

Each case changes the valid settings below only by the variables it names. The
values are the spec's Python string literals, or expressions that repeat them;
this file writes each invisible character by its name ("\\N{ZERO WIDTH SPACE}" is
the spec's "\\u200b"), so that its source holds none of them raw.
"""

from __future__ import annotations

import socket
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest
import uvicorn
from fastapi.testclient import TestClient

import nock.server
from spec033_harness import (
    ACCOUNT_PATH,
    RecordingMailer,
    account_settings,
)

if TYPE_CHECKING:
    from nock.settings import AccountSettings

PUBLIC_URL_VARIABLE = "NOCK_PUBLIC_URL"
SMTP_HOST_VARIABLE = "NOCK_SMTP_HOST"
SMTP_PORT_VARIABLE = "NOCK_SMTP_PORT"
SMTP_SECURITY_VARIABLE = "NOCK_SMTP_SECURITY"
SMTP_USER_VARIABLE = "NOCK_SMTP_USER"
SMTP_PASSWORD_VARIABLE = "NOCK_SMTP_PASSWORD"
SMTP_FROM_VARIABLE = "NOCK_SMTP_FROM"
ACCOUNT_VARIABLES = (
    PUBLIC_URL_VARIABLE,
    SMTP_HOST_VARIABLE,
    SMTP_PORT_VARIABLE,
    SMTP_SECURITY_VARIABLE,
    SMTP_USER_VARIABLE,
    SMTP_PASSWORD_VARIABLE,
    SMTP_FROM_VARIABLE,
)
# What `main()` reads besides: specs 036 and 038.
OTHER_MAIN_VARIABLES = (
    "NOCK_HOST",
    "NOCK_PORT",
    "NOCK_DATABASE",
    "NOCK_OPERATOR_TOKEN",
)
DATABASE_VARIABLE = "NOCK_DATABASE"
MEMORY_DATABASE = ":memory:"

SECRET_MARK = "SECRET"  # in both passwords of the criterion
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})

VALID = {
    PUBLIC_URL_VARIABLE: "https://nock.example/",
    SMTP_HOST_VARIABLE: "smtp.example",
    SMTP_FROM_VARIABLE: "nock@nock.example",
}


def changes(*pairs: tuple[str, str | None]) -> dict[str, str]:
    """The valid variables changed by (variable, value) pairs; None deletes one."""
    environ = dict(VALID)
    for name, value in pairs:
        if value is None:
            environ.pop(name, None)
        else:
            environ[name] = value
    return environ


# ---- Cases --------------------------------------------------------------------------


class Refusal(NamedTuple):
    """An invalid case: its variables, the variable named, and the kind of message.

    `kind` is `value` for a refused value that the message shows as `repr`,
    `secret` for a refused password, which never shows, and `missing` for a
    missing variable, whose message shows no value of the case.
    """

    name: str
    environ: dict[str, str]
    variable: str
    kind: str
    value: str


def refused_value(
    name: str, variable: str, value: str, *extra: tuple[str, str]
) -> Refusal:
    """A case whose `variable` holds a refused `value`, shown as its repr."""
    environ = changes((variable, value), *extra)
    return Refusal(name, environ, variable, "value", value)


def refused_secret(name: str, value: str, *extra: tuple[str, str]) -> Refusal:
    """A case whose password is refused; the message never shows it."""
    environ = changes((SMTP_PASSWORD_VARIABLE, value), *extra)
    return Refusal(name, environ, SMTP_PASSWORD_VARIABLE, "secret", value)


def missing(name: str, variable: str, *pairs: tuple[str, str | None]) -> Refusal:
    """A case where `variable` is missing; the message shows no value."""
    return Refusal(name, changes(*pairs), variable, "missing", "")


WITH_GOOD_PASSWORD = (SMTP_PASSWORD_VARIABLE, "pw SECRET 9")
WITH_USER = (SMTP_USER_VARIABLE, "nock")

REFUSAL_CASES = [
    refused_value("url-no-scheme", PUBLIC_URL_VARIABLE, "nock.example"),
    refused_value("url-ftp", PUBLIC_URL_VARIABLE, "ftp://nock.example"),
    refused_value("url-path", PUBLIC_URL_VARIABLE, "https://nock.example/app"),
    refused_value("url-query", PUBLIC_URL_VARIABLE, "https://nock.example?x=1"),
    refused_value("url-user", PUBLIC_URL_VARIABLE, "https://u@nock.example"),
    refused_value("url-no-host", PUBLIC_URL_VARIABLE, "https://"),
    # Only one of the public URL and the SMTP host: the message names the other.
    missing("no-smtp-host", SMTP_HOST_VARIABLE, (SMTP_HOST_VARIABLE, None)),
    missing("no-public-url", PUBLIC_URL_VARIABLE, (PUBLIC_URL_VARIABLE, None)),
    refused_value("security-capitals", SMTP_SECURITY_VARIABLE, "STARTTLS"),
    refused_value("port-letters", SMTP_PORT_VARIABLE, "abc"),
    refused_value("port-zero", SMTP_PORT_VARIABLE, "0"),
    refused_value("port-65536", SMTP_PORT_VARIABLE, "65536"),
    refused_value("port-leading-space", SMTP_PORT_VARIABLE, " 587"),
    missing("no-sender", SMTP_FROM_VARIABLE, (SMTP_FROM_VARIABLE, None)),
    refused_value("bad-sender", SMTP_FROM_VARIABLE, "not-an-address"),
    missing(
        "user-without-password",
        SMTP_PASSWORD_VARIABLE,
        (SMTP_USER_VARIABLE, "mailer-login"),
    ),
    refused_secret("password-without-user", "pw-SECRET-9"),
    refused_secret(
        "password-over-a-plain-connection",
        "pw-SECRET-9",
        WITH_USER,
        (SMTP_SECURITY_VARIABLE, "none"),
    ),
    # Special characters (decisions 13 and 14).
    refused_value("url-newline", PUBLIC_URL_VARIABLE, "https://nock.example\n"),
    refused_value("url-empty-label", PUBLIC_URL_VARIABLE, "https://nock..example"),
    refused_value("url-port-0", PUBLIC_URL_VARIABLE, "https://nock.example:0"),
    refused_value("url-bare-ipv6", PUBLIC_URL_VARIABLE, "https://::1"),
    refused_value("url-ipv6", PUBLIC_URL_VARIABLE, "http://[::1]:8000"),
    refused_value("host-newline", SMTP_HOST_VARIABLE, "smtp.example\n"),
    refused_value(
        "host-zero-width-space", SMTP_HOST_VARIABLE, "smtp\N{ZERO WIDTH SPACE}.example"
    ),
    refused_value("host-empty-label", SMTP_HOST_VARIABLE, "smtp..example"),
    refused_value("host-label-of-64", SMTP_HOST_VARIABLE, "a" * 64 + ".example"),
    refused_value("host-brackets", SMTP_HOST_VARIABLE, "[::1]"),
    refused_value("host-with-port", SMTP_HOST_VARIABLE, "smtp.example:25"),
    refused_value("port-newline", SMTP_PORT_VARIABLE, "587\n"),
    refused_value("security-newline", SMTP_SECURITY_VARIABLE, "tls\n"),
    refused_value("user-newline", SMTP_USER_VARIABLE, "nock\n", WITH_GOOD_PASSWORD),
    refused_value(
        "user-line-separator",
        SMTP_USER_VARIABLE,
        "nock\N{LINE SEPARATOR}",
        WITH_GOOD_PASSWORD,
    ),
    refused_value(
        "user-outside-ascii",
        SMTP_USER_VARIABLE,
        "fran\N{LATIN SMALL LETTER C WITH CEDILLA}ois",
        WITH_GOOD_PASSWORD,
    ),
    refused_value("sender-tab", SMTP_FROM_VARIABLE, "\tnock@nock.example"),
    refused_value(
        "sender-zero-width-space",
        SMTP_FROM_VARIABLE,
        "nock\N{ZERO WIDTH SPACE}@nock.example",
    ),
    refused_value(
        "sender-outside-ascii",
        SMTP_FROM_VARIABLE,
        "fran\N{LATIN SMALL LETTER C WITH CEDILLA}ois@nock.example",
    ),
    refused_secret("password-newline", "pw-SECRET-9\n", WITH_USER),
    refused_secret(
        "password-right-to-left-override",
        "pw-SECRET\N{RIGHT-TO-LEFT OVERRIDE}-9",
        WITH_USER,
    ),
    refused_secret(
        "password-outside-ascii",
        "mot-de-pass\N{LATIN SMALL LETTER E WITH ACUTE}",
        WITH_USER,
    ),
]
REFUSALS = [pytest.param(case, id=case.name) for case in REFUSAL_CASES]


def cases_of_kind(kind: str) -> list[object]:
    """The refusal cases of one kind, as pytest parameters."""
    found: list[object] = []
    for case in REFUSAL_CASES:
        if case.kind == kind:
            found.append(pytest.param(case, id=case.name))
    return found


def settings_error() -> type[Exception]:
    from nock.settings import SettingsError

    return SettingsError


def read_settings(environ: dict[str, str]) -> AccountSettings | None:
    from nock.settings import account_settings_from_env

    return account_settings_from_env(environ)


def refusal_message(environ: dict[str, str]) -> str:
    """The message of the `SettingsError` that `environ` raises."""
    with pytest.raises(settings_error()) as caught:
        read_settings(environ)
    return str(caught.value)


def invisible_characters(text: str) -> list[str]:
    """The characters of `text` of general category Cc, Cf, Zl or Zp."""
    found: list[str] = []
    for character in text:
        if unicodedata.category(character) in INVISIBLE_CATEGORIES:
            found.append(character)
    return found


def values_set(environ: dict[str, str]) -> list[str]:
    """The values that a case sets, empty ones left out."""
    return [value for value in environ.values() if value != ""]


# ---- account_settings_from_env: accounts off ----------------------------------------


@pytest.mark.parametrize(
    "environ",
    [
        pytest.param({}, id="nothing-set"),
        pytest.param(
            {PUBLIC_URL_VARIABLE: "", SMTP_HOST_VARIABLE: ""}, id="both-empty"
        ),
        pytest.param(
            {
                PUBLIC_URL_VARIABLE: "",
                SMTP_HOST_VARIABLE: "",
                SMTP_PORT_VARIABLE: "abc",
            },
            id="both-empty-and-a-port-not-read",
        ),
    ],
)
def test_ac6_without_public_url_and_smtp_host_accounts_are_off(
    environ: dict[str, str],
) -> None:
    assert read_settings(environ) is None


# ---- account_settings_from_env: valid settings --------------------------------------


def expected_settings(
    *,
    host: str = "smtp.example",
    port: int = 587,
    security: str = "starttls",
    user: str | None = None,
) -> object:
    from nock.settings import AccountSettings

    smtp = {
        "host": host,
        "port": port,
        "security": security,
        "user": user,
        "password": None,
        "sender": "nock@nock.example",
    }
    return AccountSettings.model_validate(
        {"public_url": "https://nock.example", "smtp": smtp}
    )


def test_ac6_the_valid_settings_give_their_account_settings() -> None:
    assert read_settings(dict(VALID)) == expected_settings()


@pytest.mark.parametrize(
    ("security", "port"), [("tls", 465), ("none", 25), ("starttls", 587)]
)
def test_ac6_each_security_has_its_default_port(security: str, port: int) -> None:
    environ = changes((SMTP_SECURITY_VARIABLE, security))

    assert read_settings(environ) == expected_settings(security=security, port=port)


@pytest.mark.parametrize(
    "port_text", [pytest.param("2525", id="2525"), pytest.param("0" * 5000 + "2525")]
)
def test_ac6_the_port_variable_gives_the_port(port_text: str) -> None:
    environ = changes((SMTP_PORT_VARIABLE, port_text))

    assert read_settings(environ) == expected_settings(port=2525)


@pytest.mark.parametrize(
    "host",
    [
        pytest.param("smtp.example.", id="name-ending-with-a-dot"),
        pytest.param("::1", id="ipv6"),
        pytest.param("a" * 63 + ".example", id="label-of-63"),
    ],
)
def test_ac6_the_smtp_host_takes_the_rule_of_nock_host(host: str) -> None:
    environ = changes((SMTP_HOST_VARIABLE, host))

    assert read_settings(environ) == expected_settings(host=host)


def test_ac6_a_user_and_a_password_with_spaces_are_read() -> None:
    environ = changes((SMTP_USER_VARIABLE, "nock team"), WITH_GOOD_PASSWORD)

    settings = read_settings(environ)

    assert settings is not None
    assert settings.smtp.user == "nock team"
    assert settings.smtp.password is not None
    assert settings.smtp.password.get_secret_value() == "pw SECRET 9"


@pytest.mark.parametrize(
    "password", [pytest.param("pw SECRET 9"), pytest.param("pw-SECRET-9")]
)
def test_ac6_the_repr_of_valid_settings_shows_no_password(password: str) -> None:
    environ = changes(WITH_USER, (SMTP_PASSWORD_VARIABLE, password))

    settings = read_settings(environ)

    assert settings is not None
    assert SECRET_MARK not in repr(settings)
    assert SECRET_MARK not in str(settings)


# ---- account_settings_from_env: refused values --------------------------------------


@pytest.mark.parametrize("case", REFUSALS)
def test_ac6_an_invalid_value_raises_settings_error_naming_the_variable(
    case: Refusal,
) -> None:
    message = refusal_message(case.environ)

    assert case.variable in message


@pytest.mark.parametrize("case", REFUSALS)
def test_ac6_the_message_is_one_line_without_invisible_characters(
    case: Refusal,
) -> None:
    message = refusal_message(case.environ)

    assert len(message.splitlines()) == 1, repr(message)
    assert invisible_characters(message) == []


@pytest.mark.parametrize("case", REFUSALS)
def test_ac6_no_message_holds_secret(case: Refusal) -> None:
    message = refusal_message(case.environ)

    assert SECRET_MARK not in message


@pytest.mark.parametrize("case", cases_of_kind("value"))
def test_ac6_a_refused_value_shows_as_its_repr(case: Refusal) -> None:
    message = refusal_message(case.environ)

    assert repr(case.value) in message


@pytest.mark.parametrize("case", cases_of_kind("missing"))
def test_ac6_a_missing_variable_message_shows_no_value_of_its_case(
    case: Refusal,
) -> None:
    message = refusal_message(case.environ)

    shown = [value for value in values_set(case.environ) if value in message]
    assert shown == []


@pytest.mark.parametrize("case", cases_of_kind("secret"))
def test_ac6_a_refused_password_never_shows(case: Refusal) -> None:
    message = refusal_message(case.environ)

    assert case.value not in message
    assert repr(case.value) not in message


def test_ac6_the_password_outside_ascii_shows_not_even_in_part() -> None:
    password = "mot-de-pass\N{LATIN SMALL LETTER E WITH ACUTE}"
    environ = changes(WITH_USER, (SMTP_PASSWORD_VARIABLE, password))

    message = refusal_message(environ)

    assert password not in message
    assert "mot-de-pass" not in message


# ---- main() -------------------------------------------------------------------------


@pytest.fixture
def server_runs(monkeypatch: pytest.MonkeyPatch) -> list[uvicorn.Config]:
    """Replace `uvicorn.Server.run` by spec 036's recorder; return what it keeps."""
    configs: list[uvicorn.Config] = []

    def record_run(
        server: uvicorn.Server, sockets: list[socket.socket] | None = None
    ) -> None:
        configs.append(server.config)

    async def refuse_serve(
        server: uvicorn.Server, sockets: list[socket.socket] | None = None
    ) -> None:
        raise AssertionError("main() must start its server with uvicorn.Server.run")

    monkeypatch.setattr(uvicorn.Server, "run", record_run)
    monkeypatch.setattr(uvicorn.Server, "serve", refuse_serve)
    return configs


def set_main_environment(
    monkeypatch: pytest.MonkeyPatch, environ: dict[str, str]
) -> None:
    """Set the variables of `environ`; delete every other variable main() reads."""
    for name in (*OTHER_MAIN_VARIABLES, *ACCOUNT_VARIABLES):
        if name in environ:
            monkeypatch.setenv(name, environ[name])
        else:
            monkeypatch.delenv(name, raising=False)


def entry_point() -> Callable[[], None]:
    """Import `nock.__main__` once the recorder is in place; return its `main`."""
    from nock.__main__ import main

    return main


def exit_message(main: Callable[[], None]) -> str:
    """Call `main`, which must raise SystemExit with a `str` code; return it."""
    with pytest.raises(SystemExit) as caught:
        main()
    code = caught.value.code
    assert isinstance(code, str), f"the SystemExit code {code!r} is no message"
    return code


MAIN_REFUSALS = [
    pytest.param(changes((SMTP_PORT_VARIABLE, "abc")), SMTP_PORT_VARIABLE, id="port"),
    pytest.param(changes((SMTP_HOST_VARIABLE, None)), SMTP_HOST_VARIABLE, id="no-host"),
    pytest.param(
        changes((PUBLIC_URL_VARIABLE, "ftp://nock.example")),
        PUBLIC_URL_VARIABLE,
        id="url",
    ),
    pytest.param(changes((SMTP_FROM_VARIABLE, None)), SMTP_FROM_VARIABLE, id="sender"),
]


@pytest.mark.parametrize(("environ", "variable"), MAIN_REFUSALS)
def test_ac6_main_with_an_invalid_variable_exits_naming_it_and_never_runs(
    monkeypatch: pytest.MonkeyPatch,
    server_runs: list[uvicorn.Config],
    environ: dict[str, str],
    variable: str,
) -> None:
    set_main_environment(monkeypatch, environ)
    main = entry_point()

    message = exit_message(main)

    assert variable in message
    assert server_runs == []


def test_ac6_main_shows_the_repr_of_a_host_with_a_newline_on_one_line(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_main_environment(monkeypatch, changes((SMTP_HOST_VARIABLE, "smtp.example\n")))
    main = entry_point()

    message = exit_message(main)

    assert repr("smtp.example\n") in message
    assert len(message.splitlines()) == 1, repr(message)
    assert server_runs == []


def test_ac6_main_with_a_password_over_a_plain_connection_never_shows_it(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    environ = changes(
        WITH_USER,
        (SMTP_PASSWORD_VARIABLE, "pw-SECRET-9"),
        (SMTP_SECURITY_VARIABLE, "none"),
    )
    set_main_environment(monkeypatch, environ)
    main = entry_point()

    message = exit_message(main)

    assert SMTP_PASSWORD_VARIABLE in message
    assert SECRET_MARK not in message
    assert server_runs == []


def test_ac6_main_with_valid_settings_runs_the_server(
    monkeypatch: pytest.MonkeyPatch, server_runs: list[uvicorn.Config]
) -> None:
    set_main_environment(monkeypatch, dict(VALID))
    main = entry_point()

    main()

    assert len(server_runs) == 1


# ---- The app's account store, and the variables read at its start ------------------


@pytest.fixture
def account_store_paths(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace `nock.server.AccountStore` by the harness's recording subclass.

    Returns the list where the subclass's `__init__` appends `str(path)`, for each
    store built, before it calls `AccountStore.__init__`.
    """
    from nock.accounts import AccountStore

    paths: list[str] = []

    class RecordingAccountStore(AccountStore):
        """An AccountStore that records the path it is built with."""

        def __init__(self, path: str | Path) -> None:
            """Record `str(path)`, then open the store as AccountStore does."""
            paths.append(str(path))
            AccountStore.__init__(self, path)

    monkeypatch.setattr(nock.server, "AccountStore", RecordingAccountStore)
    return paths


@pytest.mark.parametrize(
    "nock_database", [pytest.param(None, id="unset"), pytest.param("", id="empty")]
)
def test_ac6_the_app_keeps_its_accounts_in_memory_without_a_database_file(
    monkeypatch: pytest.MonkeyPatch,
    account_store_paths: list[str],
    tmp_path: Path,
    nock_database: str | None,
) -> None:
    if nock_database is None:
        monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(DATABASE_VARIABLE, nock_database)
    app = nock.server.create_app(
        dist_dir=tmp_path, accounts=account_settings(), mailer=RecordingMailer()
    )

    with TestClient(app):
        pass

    assert len(account_store_paths) >= 1, "the app built no account store"
    assert "" not in account_store_paths
    assert account_store_paths == [MEMORY_DATABASE] * len(account_store_paths)


def delete_account_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ACCOUNT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def test_ac6_an_app_given_no_accounts_fails_its_start_on_an_invalid_variable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    delete_account_variables(monkeypatch)
    monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    for name, value in changes((SMTP_HOST_VARIABLE, "smtp.example\n")).items():
        monkeypatch.setenv(name, value)
    app = nock.server.create_app(dist_dir=tmp_path, mailer=RecordingMailer())

    with pytest.raises(settings_error()) as caught, TestClient(app):
        pass

    assert SMTP_HOST_VARIABLE in str(caught.value)
    assert repr("smtp.example\n") in str(caught.value)


def test_ac6_an_app_given_no_accounts_turns_them_on_from_valid_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    delete_account_variables(monkeypatch)
    monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    for name, value in VALID.items():
        monkeypatch.setenv(name, value)
    app = nock.server.create_app(dist_dir=tmp_path, mailer=RecordingMailer())

    with TestClient(app) as client:
        response = client.get(ACCOUNT_PATH)

    assert response.status_code == 200
    assert response.json() == {"signed_in": False, "email": None}


def test_ac6_an_app_given_accounts_reads_none_of_the_variables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    delete_account_variables(monkeypatch)
    monkeypatch.delenv(DATABASE_VARIABLE, raising=False)
    monkeypatch.setenv(SMTP_HOST_VARIABLE, "smtp.example\n")
    monkeypatch.setenv(SMTP_PORT_VARIABLE, "abc")
    app = nock.server.create_app(
        dist_dir=tmp_path, accounts=account_settings(), mailer=RecordingMailer()
    )

    with TestClient(app) as client:
        response = client.get(ACCOUNT_PATH)

    assert response.status_code == 200
    assert response.json() == {"signed_in": False, "email": None}
