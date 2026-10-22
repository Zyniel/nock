---
id: "033"
title: Optional account
status: done
---

# 033 - Optional account

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

(Note from the lead, 2026-10-15: folded in. The answers are decisions 11 and 12,
and "Open questions" is empty. Spec 005 is refined by the lead before this spec's
tests are written.)

(Note from the lead, 2026-10-16: refined under the human's rule of the same day,
"Technical variables should not contain special characters", which covers the
variables of this spec. Each variable takes the rule of its kind in spec 036, a
refused value shows as `repr(value)` on one line, and the account store is in
memory when `NOCK_DATABASE` is empty (decision 13). The SMTP user, password and
sender then take printable ASCII only, the answer to open question 1 (decision
14). Changed: "Configuration", the comment of `account_store` in `create_app`,
"Test harness", AC-6, "Edge cases and errors", the new decisions 13 and 14 and
"Open questions", which now holds open question 2, on players' addresses outside
ASCII. No test of this spec exists yet (review of spec 036's refinement).)

(Note from the lead, 2026-10-16: refined for the human's rule that nicknames are
stored in capitals and shown with capitalised words (spec 012 decision 12; spec
039's "Nicknames in capitals"). Changed: AC-4, whose search of the database files
now looks for the nicknames as stored, and one sentence on `--` after "Former
players". This spec has no tests yet (human's rule of 2026-10-16: nicknames in
capitals).)

(Note from the lead, 2026-10-21: prepared for this spec's tests, which do not exist
yet, by a check against the code built for specs 032, 036 and 038 and against the
specs refined since this spec was approved: 032, 036, 038 and the nickname rule of
2026-10-16 (specs 012, 039 and 040). Each change has a dated note where it is.
Folded in: open question 2, answered with option (b), is decision 15:
`normalize_email` refuses a local part outside ASCII. Carried over: a former player
seated back keeps `--`, with no suffix (from spec 032's pass); spec 005 allows
`smtplib` and `ssl` in `src/nock/mailer.py` only (spec 005 decision 7, refined the
same day). Cut under the human's rule of 2026-10-16, decision 16: an IPv6 address in
`NOCK_PUBLIC_URL`, the end of the carried session at sign-in, `forget_rooms` and its
sweep call, the used state of a link, the identity kept in a link, the length limits
of `SignInLinkRequest.email`, the account store while accounts are off, and a room
page's second `PUT /api/account/rooms`. Fixed: the identities served (members only,
since a new room can draw an old code), the order and the counting of a link
request's checks, the forgetting of its limits, the WAL checkpoint of
`delete_account`, `MailError`'s traceback, the logs' formatter (spec 038), the
nicknames in capitals of AC-1 and AC-11, `account-open` as the toolbar's last
`button`, `--` shown through `displayNickname` (spec 040), and what the accounts
keep (spec 038's row "Accounts"). Criteria changed: AC-1, AC-4 and AC-6 to AC-11.
No criterion was added or removed.)

Epic E9 Accounts and resume (US-9.2) · Release: V1 · Epic depends on: E3
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine and its
harness are defined in spec 011; joining, the stored identity and the room page flow
in spec 012; the room page layout guarantees in specs 006, 009 and 013 (AC-6) and
the room toolbar in spec 024;
accessibility in spec 035; the store in spec 018; the entry point `python -m nock` in
spec 036; members, `RoomKey`, "My rooms" and the expiry sweep in spec 032; privacy
(secure delete, logs, `nock.settings`) in spec 038; the recap in spec 028. The
messages are those of spec 039. This spec is built after specs 032, 038 and 034.

## Goal

As a regular player, I want an account, so that my history follows me across devices.

The MVP ships with guests only: a guest can do everything needed to finish a grid. Accounts arrive in V1 and only add memory across devices.

## Public interface

### Terms

- **Account**: an e-mail address and a random account id. It is created the first
  time a sign-in link sent to that address is used; asking for a link creates nothing.
- **Sign-in link**: `<NOCK_PUBLIC_URL>/account#<token>`, where the token is
  `secrets.token_urlsafe(32)` (43 characters). It is sent by e-mail, works once, and
  for `LINK_LIFE_SECONDS` (30 minutes). The token is in the URL's fragment, which a
  browser never sends to a server, so no server log can hold it.
- **Session**: the cookie `nock_session`, set when a link is used, valid for
  `SESSION_LIFE_SECONDS` (90 days). Its value is `secrets.token_urlsafe(32)` (43
  characters). It is the only cookie of the app, and only a signed-in player has it
  (spec 038 AC-2). (Note from the lead, 2026-10-21: the sentence on its value was
  added; the spec did not say how a session value is drawn.)
- **Identity of an account in a room**: the room code, player id, resume token and
  nickname of a member (spec 032) that the account linked. A room can have several
  (one per player id); "the account's identity" of a room is the latest one linked.
- **Former player**: the player of an identity of a deleted account. The server
  replaces their nickname with `FORMER_PLAYER_NICKNAME` (`--`), which no real
  nickname can be (spec 012 needs a letter or a digit), and spec 040's
  `displayNickname` shows it as `t("player.former")` (`Ancien joueur`; see "Former
  players" in "Client"). (Note from the lead, 2026-10-21: "the client shows
  `t("player.former")` for it" became the text from "spec 040's" (check against spec
  040).)
- **Accounts on**: `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both set, or the app
  was given `AccountSettings`. Accounts off: every account route and page answers 404
  and the client shows no account control.

### Configuration

| Variable | Default | Valid values | Any other value |
| --- | --- | --- | --- |
| `NOCK_PUBLIC_URL` | unset or empty: accounts off | `http://` or `https://`, a host, and optionally `:` and a port; nothing else (no user, no path other than one trailing `/`, which is dropped, no query, no fragment). The host is a value that `NOCK_SMTP_HOST` takes and that holds no `:`, so a host name or an IPv4 address, never an IPv6 address (decision 16); the port is a value that `NOCK_SMTP_PORT` takes. The links of the e-mails start with it; it is never taken from a request's `Host` header | `SettingsError` naming `NOCK_PUBLIC_URL` and showing the value |
| `NOCK_SMTP_HOST` | unset or empty: accounts off | a host name or an IP address, under the rule of spec 036's `NOCK_HOST`: each character is an ASCII letter, an ASCII digit, `.`, `-` or `:`; a value that holds `:` is an IPv6 address that `ipaddress.IPv6Address` accepts, written without brackets (`::1`); a value that holds no `:` is cut at each `.` into labels, each label holds 1 to 63 characters, and only the last label may be empty (`smtp.example.`) | `SettingsError` naming the variable and showing the value |
| `NOCK_SMTP_PORT` | `587` with `starttls`, `465` with `tls`, `25` with `none` | ASCII digits only, for a number from 1 to 65535, leading zeros accepted however many (spec 036's `NOCK_PORT`) | `SettingsError` naming the variable and showing the value |
| `NOCK_SMTP_SECURITY` | `starttls` | exactly `starttls`, `tls` or `none` | `SettingsError` naming the variable and showing the value |
| `NOCK_SMTP_USER` | unset or empty: no login | text in printable ASCII only, U+0020 SPACE to U+007E TILDE (see "Refused characters" below) | `SettingsError` naming the variable and showing the value |
| `NOCK_SMTP_PASSWORD` | unset or empty: no login | text in printable ASCII only, as `NOCK_SMTP_USER`; a secret | `SettingsError` naming the variable, never the value, when it holds a refused character, is set without `NOCK_SMTP_USER`, or is set with `NOCK_SMTP_SECURITY=none` |
| `NOCK_SMTP_FROM` | none | an address that `normalize_email` accepts, in printable ASCII only, as `NOCK_SMTP_USER`; required when accounts are on | `SettingsError` naming the variable and showing the value |

(Note from the lead, 2026-10-16: the table refined with decisions 13 and 14. The
host and the port of `NOCK_PUBLIC_URL` had no rule of their own;
`NOCK_SMTP_HOST` was "a host name or address, without spaces"; `NOCK_SMTP_PORT`
did not say that leading zeros pass; `NOCK_SMTP_USER` and `NOCK_SMTP_PASSWORD`
were "any non-empty text", whose default said "unset", and the user could not
be refused (its last cell was "—"); `NOCK_SMTP_FROM` had no refused character;
the last column said "the value" where it now says "showing the value", as
`repr(value)` (see "Messages") (review of spec 036's refinement).) (Note from the
lead, 2026-10-21: the host of `NOCK_PUBLIC_URL` could also be an IPv6 address that
`NOCK_SMTP_HOST` takes, between `[` and `]` (`http://[::1]:8000`); that form is cut,
decision 16.)

- An empty value counts as unset, as in spec 036. `NOCK_SMTP_USER` set without
  `NOCK_SMTP_PASSWORD` is a `SettingsError` naming the missing one.
- Refused characters (`NOCK_SMTP_USER`, `NOCK_SMTP_PASSWORD`, `NOCK_SMTP_FROM`):
  every character outside the printable ASCII characters, U+0020 SPACE to U+007E
  TILDE. That is the set that spec 036 refuses in `NOCK_DATABASE` (spec 036's
  decision 14: Unicode general categories Cc, Cf, Zl and Zp, as
  `unicodedata.category` gives them, except U+200C and U+200D), plus every
  character outside ASCII, the two joiners included (this spec's decision 14).
  Spaces are allowed, meaning U+0020 SPACE only, which printable ASCII holds. No
  other space character passes: a tab (`"\t"`, U+0009) is a control character,
  and a no-break space (`"\u00a0"`, U+00A0) or an em space (`"\u2003"`, U+2003)
  is outside ASCII. The other variables take only ASCII letters, ASCII digits
  and a few marks, so they refuse all of these already. Each check reads the
  value as given, before anything strips it: `"\tnock@nock.example"` is refused,
  although `normalize_email` would strip the tab. (Note from the lead,
  2026-10-16: added with decisions 13 and 14 (review of spec 036's
  refinement).) (Note from the lead, 2026-10-16: "Spaces are allowed" did not
  say which spaces, and could be read as every space character, a tab or a
  no-break space included; it now means U+0020 SPACE only (second review of
  spec 036's refinement).)
- Messages: every `SettingsError` message about a variable of the table above
  is one line (one item in `str.splitlines()`) and holds no character of
  categories Cc, Cf, Zl or Zp. A message that refuses the value of one of those
  variables other than `NOCK_SMTP_PASSWORD` shows it as `repr(value)` (spec 036
  decision 12), so that `\n` in it always stands for a newline. A message about
  `NOCK_SMTP_PASSWORD` names it and never shows its value, whole or in part, as
  spec 038 does for the operator token. A message that names a missing variable
  instead of refusing a value (only one of `NOCK_PUBLIC_URL` and
  `NOCK_SMTP_HOST` set, `NOCK_SMTP_USER` set without `NOCK_SMTP_PASSWORD`, a
  missing `NOCK_SMTP_FROM`) names that variable and shows no value. Should the
  value of a variable that is set appear in such a message all the same, it
  follows the two rules above: `repr(value)`, and never the password. These
  rules cover the variables of the table only: `SettingsError` is also spec
  038's class, and its message about `NOCK_OPERATOR_TOKEN` follows spec 038 (the
  variable and the rule broken, never the value). The rest of the wording is
  free. (Note from the lead, 2026-10-16: added with decision 13; the messages
  used to name the variable and "the value", with no rule for escaping it
  (review of spec 036's refinement).) (Note from the lead, 2026-10-16: the rules
  are limited to the variables of the table: read literally, "a variable other
  than `NOCK_SMTP_PASSWORD`" also covered spec 038's `NOCK_OPERATOR_TOKEN`,
  whose message never shows the value (spec 038); and the rule for a message
  that names a missing variable was added, since the bullet did not say what
  such a message shows (second review of spec 036's refinement).)
- Exactly one of `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` set is a `SettingsError`
  naming the missing one. With accounts off, the other `NOCK_SMTP_*` variables are
  not read, so none of them is checked, whatever it holds. (Note from the lead,
  2026-10-16: ", so none of them is checked, whatever it holds" added with
  decision 13 (review of spec 036's refinement).)
- `main()` (spec 036, as spec 038 extends it) also calls
  `account_settings_from_env(os.environ)` before it builds a server; a
  `SettingsError` becomes `SystemExit(str(error))`, so `python -m nock` prints it and
  exits with status 1. An app built otherwise reads the same variables when it
  starts and fails its startup with the same error. The checks run at these two
  moments only, and the app makes them only when it is given no `accounts`
  (`create_app(accounts=...)` reads none of these variables). When several
  variables are invalid, which one the message is about is not specified, as in
  spec 036. (Note from the lead, 2026-10-16: the last two sentences added with
  decision 13 (review of spec 036's refinement).) So `python -m nock` also reads
  the variables of the table above, besides the four that spec 036's "Out of scope"
  names. (Note from the lead, 2026-10-21: the sentence before this note was added;
  spec 036 says that `python -m nock` reads only `NOCK_HOST`, `NOCK_PORT`,
  `NOCK_DATABASE` and `NOCK_OPERATOR_TOKEN` (check against spec 036).)
- Secrets: the SMTP password, the link tokens, the session tokens and the resume
  tokens are never written to a log, an error message or a `repr`; nor are the
  e-mail addresses of players. The other values of "Configuration", the sender
  address and the SMTP user included, are not secrets: a message that refuses one
  shows it (see "Messages"). (Note from the lead, 2026-10-16: "nor are e-mail
  addresses" became "nor are the e-mail addresses of players", and the last
  sentence was added with decision 13; the table already showed a refused
  `NOCK_SMTP_FROM` in its message (review of spec 036's refinement).)

```python
# src/nock/settings.py (additions to spec 038)
from pydantic import SecretStr


class SmtpSettings(BaseModel):
    """How the server sends e-mail."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535, strict=True)
    security: Literal["starttls", "tls", "none"]
    user: str | None = None
    password: SecretStr | None = None  # its repr and str show no secret
    sender: str  # an address normalize_email accepts


class AccountSettings(BaseModel):
    """Accounts are on, with these settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    public_url: str  # "<scheme>://<host>[:<port>]", no trailing "/"
    smtp: SmtpSettings


def account_settings_from_env(environ: Mapping[str, str]) -> AccountSettings | None:
    """Return the account settings of `environ`, or None when accounts are off.

    Raises:
        SettingsError: a variable breaks the rules of "Configuration".
    """
```

### Spec 005 amendment: sending mail

Spec 005's server scan (AC-4) forbade `smtplib` and `ssl` in every `.py` file under
`src/`, and the human asked on 2026-10-14 to send the sign-in link with `smtplib`.
Spec 005's scan now allows `smtplib` and `ssl` in `src/nock/mailer.py` only (sending
mail is not fetching grids), and keeps flagging them in every other file (spec 005
decision 7). No other module of this spec opens a connection. (Note from the lead,
2026-10-21: done; this section said that the lead refines spec 005 before this
spec's tests run. Spec 005's AC-4 changed, so its tests follow before this spec's
implementer runs.)

### `nock.i18n` (new): server-side texts

```python
# src/nock/i18n.py
FR_JSON_PATH: Path  # <repository root>/web/src/i18n/fr.json, from the module file


def t(key: str, **values: object) -> str:
    """Return the French text of `key` from fr.json, as the client's `t` does:
    each `{name}` with a value is replaced by `str(value)`, others stay as written.

    Raises:
        KeyError: no such key.
    """
```

The e-mail's subject and body come from `fr.json` through it, so every text a person
reads comes from that file (spec 040).

### `nock.mailer` (new): the only module that opens a network connection

```python
# src/nock/mailer.py
from email.message import EmailMessage


class MailError(Exception):
    """A message could not be sent.

    Neither its text nor its traceback (`traceback.format_exception`) holds a
    password, a token or a player's address: the `smtplib` error behind it, whose
    text may hold the address, does not show in that traceback (for example
    `raise MailError(...) from None`).
    """


class Mailer(Protocol):
    def send(self, message: EmailMessage) -> None:
        """Send one message. Raises MailError when it is not sent."""


class SmtpMailer:
    """A Mailer that sends with `smtplib`."""

    def __init__(self, settings: SmtpSettings) -> None: ...

    def send(self, message: EmailMessage) -> None:
        """Send `message` through the SMTP server of `settings`, with a timeout of
        10 seconds:

        - `tls`: `smtplib.SMTP_SSL(host, port, context=<context>, timeout=10)`;
        - `starttls`: `smtplib.SMTP(host, port, timeout=10)`, then
          `starttls(context=<context>)`;
        - `none`: `smtplib.SMTP(host, port, timeout=10)`, no TLS;

        where `<context>` is `ssl.create_default_context()`, which checks the
        server's certificate and host name. Then `login(user, password)` when a user
        is set, `send_message(message)` and `quit()`.

        Raises:
            MailError: any failure (connection, TLS, login, refusal, timeout).
        """


def sign_in_message(settings: AccountSettings, to: str, token: str) -> EmailMessage:
    """Return the sign-in e-mail: `From` the sender, `To` the address, `Subject`
    `t("email.sign_in.subject")`, and a plain-text UTF-8 body
    `t("email.sign_in.body", link=f"{settings.public_url}/account#{token}")`."""
```

(Note from the lead, 2026-10-21: the docstring of `MailError` read "A message could
not be sent. Its text holds no password, token or address." `smtplib`'s refusals
name the recipient (`SMTPRecipientsRefused`), and a chained error shows in the
traceback that a log adds; AC-7 checks the traceback.)

### `nock.accounts` (new)

```python
# src/nock/accounts.py
# RoomCode and RoomKey come from nock.room (specs 011 and 032); PlayerId,
# ResumeToken and Nickname from nock.protocol (spec 039).
SESSION_COOKIE: str = "nock_session"
LINK_LIFE_SECONDS: float = 1_800.0  # 30 minutes (decision 11)
SESSION_LIFE_SECONDS: float = 7_776_000.0  # 90 days (decision 11)
LINKS_PER_EMAIL_PER_HOUR: int = 3  # decision 11
LINKS_PER_ADDRESS_PER_HOUR: int = 10  # decision 11
EMAIL_MAX_LENGTH: int = 254


def normalize_email(text: str) -> str:
    """Return the address as stored: `strip()`ped, then lower-cased.

    Rules, on the result: at most EMAIL_MAX_LENGTH characters; exactly one `@`; a
    local part of 1 to 64 characters, each an ASCII letter, an ASCII digit, `.` or
    one of these 19 characters: ! # $ % & ' * + - / = ? ^ _ ` { | } ~ (with the
    letters and digits, RFC 5322's `atext`; decision 15); a domain of two or more
    labels separated by `.`, each 1 to 63 ASCII letters, digits and hyphens, not
    starting or ending with a hyphen.

    Raises:
        ValueError: a rule is broken; the message names the rule, not the address.
    """


class AccountModel(BaseModel):
    """Base of the account models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RoomIdentity(AccountModel):
    """An account's identity in a room, as a device stores it (spec 012)."""

    code: RoomCode
    player_id: PlayerId
    resume_token: ResumeToken
    nickname: Nickname


class Account(AccountModel):
    account_id: str
    email: str


class AccountStatus(AccountModel):
    """The answer of GET /api/account."""

    signed_in: StrictBool
    email: str | None  # None when signed_in is False


class SignInLinkRequest(AccountModel):
    """The body of POST /api/account/link."""

    email: str  # checked by normalize_email only, so every refused address gets one answer
    room: RoomKey | None = None  # the room the player asks from (spec 032 RoomKey)


class SignInRequest(AccountModel):
    """The body of POST /api/account/sign-in."""

    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class SignInResult(AccountModel):
    """The answer of POST /api/account/sign-in."""

    email: str
    room_code: RoomCode | None  # the room the link was asked from, when linked
    rooms: tuple[RoomIdentity, ...]  # as GET /api/account/rooms


class LinkUse(AccountModel):
    email: str
    room: RoomKey | None  # the room the link was asked from


class SessionStart(AccountModel):
    account_id: str
    session: str  # the raw cookie value; only its SHA-256 is stored


class AccountStore:
    """Accounts on disk, in the database file of the rooms (NOCK_DATABASE).

    A plain class (a service). Safe to call from several threads. It uses its own
    connection with secure_delete ON and, on a file database, journal_mode WAL and
    synchronous FULL, like RoomStore (specs 018, 038). Link and session tokens are
    stored as their SHA-256 only; addresses, room keys and identities are stored as
    given.
    """

    def __init__(self, path: str | Path) -> None: ...

    def add_link(self, email: str, room: RoomKey | None, now: float) -> str:
        """Record a sign-in link for `email` (normalised by the caller) and the
        room it was asked from; return its raw token."""

    def use_link(self, token: str, now: float) -> LinkUse | None:
        """Delete the link and return it; None when the token is unknown or the
        link is older than LINK_LIFE_SECONDS."""

    def sign_in(self, email: str, now: float) -> SessionStart:
        """Create the account of `email` when there is none, then a session."""

    def account_of_session(self, session: str, now: float) -> Account | None:
        """The account of a session that exists and is not older than
        SESSION_LIFE_SECONDS; None otherwise."""

    def end_session(self, session: str) -> None: ...

    def link_identity(self, account_id: str, identity: RoomIdentity, now: float) -> bool:
        """Link an identity to the account; linking the same player again updates
        its token and nickname and makes it the newest. Inside its one
        `BEGIN IMMEDIATE` transaction it writes only while the account row exists.

        Returns:
            True when it linked; False, with nothing written, when the account no
            longer exists (it was deleted, so an erased player's nickname cannot
            come back into the file).
        """

    def identities(self, account_id: str) -> list[RoomIdentity]:
        """The account's identity of each of its rooms (the latest linked per
        room), newest link first."""

    def delete_account(self, account_id: str) -> list[RoomIdentity]:
        """Delete the account, its sessions, its identities and every sign-in link
        of its address, in one transaction, then checkpoint the WAL
        (`PRAGMA wal_checkpoint(TRUNCATE)`) on a file database, as spec 038's
        `delete_room`; return every identity it held (not only the latest)."""

    def purge(self, now: float) -> None:
        """Delete the links older than LINK_LIFE_SECONDS and the sessions older than
        SESSION_LIFE_SECONDS, then checkpoint the WAL on a file database
        (`PRAGMA wal_checkpoint(TRUNCATE)`), as `delete_account` does, so that no
        purged address stays in the WAL file (spec 038)."""

    def close(self) -> None:
        """Close the database. Idempotent."""
```

(Note from the lead, 2026-10-15: the comments of `LINK_LIFE_SECONDS`,
`SESSION_LIFE_SECONDS`, `LINKS_PER_EMAIL_PER_HOUR` and `LINKS_PER_ADDRESS_PER_HOUR`
said "proposed, open question 1"; the human kept these values, decision 11.)

(Note from the lead, 2026-10-21: in this block, the comment on the imported types
was added; the docstring of `normalize_email` read "a local part of 1 to 64
characters with no whitespace or control character", decision 15;
`SignInLinkRequest.email` was `Field(min_length=1, max_length=320)`, so that `""`
and an address of 321 characters got FastAPI's validation body, which repeats the
address, instead of the answer of every refused address (decision 16); the
pragmas of `AccountStore` follow `RoomStore`, which uses WAL and synchronous FULL
on a file only; `add_link` and `LinkUse.room` took a `RoomIdentity`, and a link now
keeps the request's `RoomKey`, since the sign-in reads the member from the room
(decision 16); `use_link` marked the link used, and now deletes it (decision 16);
`delete_account` gained its checkpoint, without which the WAL file kept the address
(AC-4); and `forget_rooms(self, codes: Sequence[str]) -> None`, "Delete the
identities of those rooms (they expired, spec 032)", is gone with its sweep call
(decision 16).)

(Note from the lead, 2026-10-21, first review of spec 033: in this block, the
docstring of `normalize_email` read "each a printable ASCII character other than the
space, U+0021 to U+007E (decision 15)". The review found that `,`, `<`, `>` and `"`
in the local part get around AC-8's limit of 3 links per address: with the test SMTP
server, `x1,victim@example.org` and `x2,victim@example.org` counted as two addresses
yet both reached `victim@example.org`, and `a"b<victim@example.org` reached it with
no comma at all. The local part now takes RFC 5322's `atext` characters and `.`
only: of the printable ASCII characters, it refuses `"`, `(`, `)`, `,`, `:`, `;`,
`<`, `>`, `[`, `\` and `]`, besides `@`, which the single-`@` rule already kept out
(the space, the control characters and the characters outside ASCII were refused
already). No rule on where a `.` stands is added: the spec had none and keeps none, so
`.ana@example.org`, `ana.@example.org` and `a..b@example.org` pass, as they did
(the domain keeps its rule, which refuses an empty label). Decision 15 has the
reason.)

(Note from the lead, 2026-10-21, second review of spec 033: `link_identity` returned
None and did not check that the account exists, and foreign keys are off. A
`PUT /api/account/rooms` whose session was checked before a `DELETE /api/account`
could link after the erasure, and the erased player's nickname stayed in the file for
good, against the erasure rule. It now returns a `bool` and writes only while the
account row exists; the route answers 401 on False; AC-4 checks it.)

(Note from the lead, 2026-10-21, first review of spec 033: in this block, the
docstring of `purge` ended after "SESSION_LIFE_SECONDS". It now ends with the
checkpoint that `delete_account` has: without it, a purged address could stay in
`nock.sqlite3-wal` until the next checkpoint, against spec 038's rule that a deletion
leaves no copy in the write-ahead log. AC-1 checks the bytes of the files.)

### What the accounts keep, and for how long

Spec 038's table of what the server keeps says "defined there" for the accounts:

| Where | What | How long |
| --- | --- | --- |
| SQLite `NOCK_DATABASE` (memory when it is unset or empty), accounts | each account's id and address | until the account is deleted |
| the same, sessions | the SHA-256 of each session value, with its account and its start time | until sign-out, the account's deletion, or the first sweep after `SESSION_LIFE_SECONDS` |
| the same, sign-in links | the SHA-256 of each token, with its address, the `RoomKey` it was asked from (if any) and its time | until it is used, the account of its address is deleted, or the first sweep after `LINK_LIFE_SECONDS` |
| the same, identities | per account, the `RoomIdentity` of each player it linked, with the time of the link | until the account is deleted, also after the room is deleted |
| Process memory | the two limits of a link request: the times of the counted requests of the last hour, per normalised address and per client address | an hour after a key's last counted request, and at most until the next request counted after that ("A link request") |
| Process logs | no player's address, link token, session value or SMTP password (AC-10) | - |

(Note from the lead, 2026-10-21: added from the check against spec 038; this spec
did not say what its accounts keep.)

### `nock.room`, `nock.store` and `nock.hub`: erasing a player

```python
# src/nock/room.py (addition)
FORMER_PLAYER_NICKNAME: str = "--"


# src/nock/store.py (addition)
class RoomStore:
    def erase_player(self, code: str, player_id: str) -> bool:
        """Replace the nickname of `player_id` with FORMER_PLAYER_NICKNAME in every
        stored snapshot of the room (its record in `players` or `past_players`) and
        in every logged `player_joined` of that player, in one transaction, then
        checkpoint the WAL (`PRAGMA wal_checkpoint(TRUNCATE)`) on a file
        database, as `delete_room` (spec 038). Seqs, order and everything else
        stay.

        Returns:
            True when the room exists.
        """


# src/nock/hub.py (addition)
class RoomRegistry:
    def erase_player(self, code: str, player_id: str) -> bool:
        """Erase a player's nickname from a room, live state included.

        For a live room, the room's task does it between two steps: the player's
        record (in `players` or `past_players`) gets FORMER_PLAYER_NICKNAME, then
        `store.erase_player`. For a room only in the store, `store.erase_player`.
        No event is logged or sent: a snapshot built afterwards shows the new
        nickname. Returns once it is done; False when the room is unknown or
        expired (spec 032's lookups).
        """
```

(Note from the lead, 2026-10-21: "on a file database, as `delete_room`" was added to
the store's checkpoint, as spec 038's store does it, and "or expired (spec 032's
lookups)" to the registry's, since spec 032 deletes an expired room at any lookup.)

This is the second exception to spec 018's "the log is never rewritten" (the first
is spec 032's deletion at expiry): privacy erasure rewrites the nickname in place.

Seat back of a former player (amends spec 012's step 4a and spec 032's "Seat back"):
a past player whose nickname is `FORMER_PLAYER_NICKNAME` is seated back with the
nickname `--` as it is, without spec 012's "Duplicate nicknames" rule, even when a
player of `players` is `--` too. A room may thus hold several former players, and
each reads `Ancien joueur`, where `-- 2` would show as it is. Every other nickname
keeps spec 012's rule. (Note from the lead, 2026-10-21: added from spec 032's pass,
which found that spec 012's rule turns a second `--` into `-- 2`; AC-4 checks it.)

### HTTP routes

All answers of the routes under `/api/account` carry `Cache-Control: no-store`.
"Session" below is the account of the request's `nock_session` cookie
(`account_of_session`). A refusal for lack of a session is 401 with
`{"detail": "Not authorized"}`, checked before anything else of the request. Each
404 of the table has the body `{"detail": "Not Found"}`. Times come from
`rooms.clock()`, with `now` the time of the request. (Note from the lead,
2026-10-21: "All account answers" became "All answers of the routes under
`/api/account`"; "checked before anything else of the request", the body of each
404 and the sentence on times were added: the table gave some 404s no body, and
"Times come from `rooms.clock`" stood after `create_app`.)

| Method and path | Answer |
| --- | --- |
| any route below, or `GET /account`, accounts off | 404, `{"detail": "Not Found"}` |
| `GET /account` | `index.html` (503 when the client is not built), as `/r/{code}` |
| `GET /api/account` | 200, `AccountStatus`: signed in with the session's address, or `{"signed_in": false, "email": null}` |
| `POST /api/account/link`, body `SignInLinkRequest` | 202 with `{}`, after `sign_in_message` was sent to `normalize_email(email)`; the answer is the same whether the address has an account |
| the same, `normalize_email` refuses the address | 422, `{"detail": "Invalid e-mail address"}`, which does not repeat the address |
| the same, `room` given and its token is no member's of that room (`rooms.member_id`, spec 032) | 404 |
| the same, `LINKS_PER_EMAIL_PER_HOUR` counted requests for that address, or `LINKS_PER_ADDRESS_PER_HOUR` from that client address (as spec 011 reads it), whose time `t` satisfies `t > now - 3600` | 429, `{"detail": "Too Many Requests"}`, nothing sent |
| the same, the mailer raises `MailError` | 503, `{"detail": "Mail not sent"}`; the failure is logged at `warning` or above, without secret or address |
| `POST /api/account/sign-in`, body `SignInRequest` | 200, `SignInResult`, with `Set-Cookie: nock_session=<session>; HttpOnly; Max-Age=7776000; Path=/; SameSite=Lax`, plus `; Secure` when the public URL starts with `https://` |
| the same, the link is unknown or expired (a used link is deleted) | 404 |
| `POST /api/account/sign-out` | 204, the session ended (if any) and `Set-Cookie: nock_session=""; Max-Age=0; Path=/` |
| `GET /api/account/rooms` | 200, JSON array of `RoomIdentity`: `identities(account)`, without those whose token is no member's of their room (`rooms.member_id(code, resume_token)` is None); 401 without a session |
| `PUT /api/account/rooms`, body `RoomKey` | 204 after `link_identity` of that member (player id and nickname from the room); 404 when the token is no member's; 401 without a session, and also when `link_identity` returns False (the session was deleted with its account after it was checked) |
| `DELETE /api/account` | 204 after the erasure below, with the cookie cleared as for sign-out; 401 without a session |

(Note from the lead, 2026-10-21: in this table, the sign-in row lost "; a session the
request carried is ended first" (decision 16), and its 404 row read "unknown, used
or expired"; `GET /api/account/rooms` read "`identities(account)` of the rooms that
still exist", which served the identity of a deleted room once a new room drew its
code (spec 032's "Code reused"); the 429 row read "links already asked for that
address, or `LINKS_PER_ADDRESS_PER_HOUR` from that client address, in the last
3,600 seconds of `rooms.clock`" and ended with "this refusal is not counted", which
"A link request" below now says.)

(Note from the lead, 2026-10-21, first review of spec 033: in the mailer row, "the
failure is logged" became "the failure is logged at `warning` or above". Specs 036
and 038 set the default log level to `warning` (`server_config`), so a lower record
would not reach the operator, and decision 14 relies on the operator seeing the
failure.)

A link request (`POST /api/account/link`) is checked in this order: its body
(FastAPI's 422 for a body that `SignInLinkRequest` refuses), the address (422), the
room (404), the limits (429); then the mail is sent (202, or 503). Only a request
that reaches the mailer, answered 202 or 503, counts toward the two limits; a request
answered 422, 404 or 429 counts toward neither. Each limit keeps in process memory,
per key (the normalised address, or the client address), the times of its counted
requests, and forgets them as spec 011's throttle forgets its failures: each time it
counts a request, it first forgets every key whose counted requests all have
`t <= now - 3600`. (Note from the lead, 2026-10-21: added. The spec gave no order of
the checks, did not say whether a request refused 422 or 404 counts, and kept the
addresses in memory with no rule to forget them, which spec 038's first review made
spec 011's throttle follow.)

No account route checks or counts spec 011's wrong-code throttle or spec 038's ops
throttle: a room key with an unknown code and one with a wrong token both answer
404, so neither tells anything about room codes (as spec 032's summaries route), and
link tokens and session values are 43 random characters. (Note from the lead,
2026-10-21: added from the check against spec 038, whose ops API reuses spec 011's
throttle; the spec did not say whether these routes use it.)

Sign-in, in order: `use_link(token)`; `sign_in(email)`; when the link carries a room
key whose token is still a member's of its room (`rooms.member_id(code,
resume_token)`), `link_identity` of that member, with the player id and nickname
from the room, as `PUT /api/account/rooms` does (the account was just created or found, so the
returned value is ignored here), and `room_code` is that room's code
(else `room_code` is None); `rooms` is then the list that `GET /api/account/rooms`
gives. (Note from the lead, 2026-10-21: this read "when the link carries a room
identity whose room still exists and whose token is still a member's,
`link_identity`, ...; `rooms` is then `identities(account)` of the rooms that still
exist"; a link keeps the request's room key, and the member is read from the room
when the link is used, decision 16.)

Erasure (`DELETE /api/account`), before answering:

1. `delete_account(account_id)` removes the address, the sessions, the identities and
   the address's links, and returns every identity the account held; nothing else of
   the account is kept. (Note from the lead, 2026-10-21: "unused links" became
   "links", since a used link is deleted, decision 16.)
2. For each of those identities whose room exists,
   `rooms.erase_player(code, player_id)`.

So no copy of the address or of those nicknames stays in the database files (spec
038's `secure_delete` and checkpoints), at once, well within the 30 days of the
backlog.

While accounts are on, the app's sweep (spec 032) also calls
`account_store.purge(rooms.clock())` right after each `expire_rooms()`; a failure of
either is logged as spec 032's failed sweep is, and the next sweep runs as planned.
(Note from the lead, 2026-10-21: this read "The app (spec 032's sweep) also calls
`account_store.forget_rooms(<deleted codes>)` after each `expire_rooms()`, and
`account_store.purge(now)`, every sweep." `forget_rooms` is cut, decision 16:
`expire_rooms()` returns the rooms that the sweep deletes, not those that a lookup
deletes, and the identities served are now those of members only.)

`create_app` (changes):

```python
def create_app(
    rooms: RoomRegistry | None = None,
    dist_dir: Path | None = None,
    catalogue: Catalogue | None = None,
    *,
    operator_token: str | None = None,  # spec 038
    accounts: AccountSettings | None = None,  # None: account_settings_from_env(os.environ) at startup
    account_store: AccountStore | None = None,  # None, accounts on: AccountStore(NOCK_DATABASE, ":memory:" when unset or empty), opened at startup, closed at stop; accounts off: none
    mailer: Mailer | None = None,  # None: SmtpMailer(accounts.smtp)
) -> FastAPI: ...
```

(Note from the lead, 2026-10-21: in the comment of `account_store`, "accounts on"
and "accounts off: none" were added: an app with accounts off opened an account
store that it never used, decision 16.)

(Note from the lead, 2026-10-16: in the comment of `account_store`, "when unset"
became "when unset or empty", as for the rooms' store (spec 018, spec 036
decision 15), with decision 13. `AccountStore("")` would have opened a private
temporary file (review of spec 036's refinement).)

A store or mailer given is never closed by the app.

### Client

Accounts on or off: the room page, the catalogue page and the account page ask
`GET /api/account` once when they load. The room page and the catalogue page show no
account control unless it answers 200 (it answers 404 while accounts are off).
(Note from the lead, 2026-10-21: "a 404 means off, and then no account control is
shown" became the sentence before this note, which also covers a failed request.)

Room page (once `data-status="joined"`, accounts on):

- `data-testid="account-open"`: a `<button type="button">` with the text
  `t("account.open")`, the last `button` element of spec 024's `room-toolbar`
  (after the controls that specs 019 to 028 put there; spec 024's
  `room-toolbar-more`, an `aria-hidden` mark with no text, stays after it). (Note
  from the lead, 2026-10-21: "the last control" became "the last `button` element",
  with the parenthesis on `room-toolbar-more`, which is the toolbar's last child in
  the code.) Spec 024's toolbar rules apply to it:
  on a small window the toolbar stays one row that scrolls sideways, so the button
  adds no height, and spec 013 AC-6 still holds (AC-9).
- It opens `data-testid="account-dialog"`, a `<dialog>` shown with `showModal()`,
  placed after `room-toolbar` in document order (the toolbar's sideways scrolling
  would clip it), `aria-labelledby` its heading. The focus moves into it (to `account-email-input`
  when shown, else to its first control); `Escape` and `data-testid="account-close"`
  (`t("account.close")`) close it, and the focus goes back to `account-open`.
- Signed out, the dialog shows the heading `t("account.dialog_heading")`, the text
  `t("account.dialog_intro")`, and a form `data-testid="account-email-form"`: an
  input `data-testid="account-email-input"` (`type="email"`,
  `autocomplete="email"`, labelled `t("account.email_label")`) and a submit button
  `data-testid="account-email-submit"` (`t("account.send")`), disabled while its
  request runs. Submitting sends `POST /api/account/link` with
  `{"email": <input>, "room": {"code": <code>, "resume_token": <snapshot.resume_token>}}`.
  202 shows `data-testid="account-sent"` (`role="status"`) with
  `t("account.sent", {email})`, `email` being the value sent; 422 shows `data-testid="account-error"`
  (`role="alert"`) with `t("account.error.email")`; 429 with
  `t("account.error.too_many")`; anything else with `t("account.error.send")`.
  (Note from the lead, 2026-10-21: ", `email` being the value sent" was added; the
  text did not say which address it shows.)
- Signed in, it shows `t("account.signed_in_heading")`,
  `t("account.signed_in_as", {email})` and a link
  `data-testid="account-page-link"` to `/account` (`t("account.manage")`).
- Once a room page has its first snapshot and a `GET /api/account` answer that says
  signed in, it sends one `PUT /api/account/rooms` with its code and that snapshot's
  `resume_token`; its answer changes nothing on the page. (Note from the lead,
  2026-10-21: this read "A signed-in page sends `PUT /api/account/rooms` with its
  code and `snapshot.resume_token` after the first snapshot of a page load, and after
  each later snapshot whose `you` differs"; the second request is cut, decision 16.)

Catalogue page (accounts on): a link `data-testid="account-link"` to `/account`
with the text `t("account.open")`, after the `h1`. When signed in, before spec 032's
"My rooms" request, the page asks `GET /api/account/rooms` and stores each identity
whose room has no valid identity on this device yet, as spec 012's
`nock.identity.<CODE>` record (`player_id`, `resume_token`, `nickname`); an identity
already stored on the device is never replaced.

Account page `/account` (routing of spec 040 gains it; the server serves it only
while accounts are on): root `data-testid="account-page"`, heading
`t("account.page_heading")`, `data-state`:

| State | When | Shows |
| --- | --- | --- |
| `signing_in` | the URL's fragment, without `#`, matches `^[A-Za-z0-9_-]{43}$` | `t("account.signing_in")`. The page first replaces its URL with `/account` (`history.replaceState`), then sends `POST /api/account/sign-in` |
| `signed_in` | sign-in answered 200, or `GET /api/account` says signed in | `data-testid="account-email"` with `t("account.signed_in_as", {email})`; after a sign-in with a `room_code`, `data-testid="account-room-link"` to `/r/<code>` (`t("account.back_to_room", {code})`); `data-testid="account-sign-out"` (`t("account.sign_out")`); `data-testid="account-delete"` (`t("account.delete")`) |
| `link_invalid` | sign-in answered 404 | `t("account.link_invalid")`, and the form of `signed_out` |
| `signed_out` | not signed in | `t("account.signed_out_intro")` and the e-mail form of the dialog (same test ids), sending `"room": null` |
| `deleted` | `DELETE /api/account` answered 204 | `t("account.deleted")` |
| `error` | any other failure | `t("account.error.generic")` |

- A sign-in that answers 200 stores each `rooms` identity whose room has no valid
  identity on this device, as on the catalogue page.
- `account-delete` shows `data-testid="account-delete-warning"`
  (`t("account.delete_warning")`), `data-testid="account-delete-confirm"`
  (`t("account.delete_confirm")`) and `data-testid="account-delete-cancel"`
  (`t("account.delete_cancel")`); only the confirm sends `DELETE /api/account`.
- `account-sign-out` sends `POST /api/account/sign-out` and shows `signed_out`.

Former players: spec 040's `displayNickname` returns `t("player.former")` for a
nickname equal to `--` (`FORMER_PLAYER_NICKNAME`), and writes every other nickname
as spec 040 says (an amendment of spec 040's "Nicknames on screen"). A page shows a
nickname only through it (spec 040), so a former player reads `Ancien joueur`
everywhere a nickname is shown: the roster's `roster-nickname`, the
`host.remove_label` of spec 014, the feed's `{name}` of specs 013 and 034, "My rooms"
of spec 032, the recap dialog and the share page of spec 028, the ops replay of spec
038, and the other views of specs 019 to 029 that name a player. `--` has no letter,
so spec 012's capitals leave it as it is. (Note from the lead, 2026-10-16: the
sentence before this note was added (human's rule of 2026-10-16: nicknames in
capitals).) (Note from the lead, 2026-10-21: the rule now lives in `displayNickname`,
the one function that spec 040 gives every page for a nickname. The paragraph said
that each of these places shows `--` as `t("player.former")`, and that
`displayNickname` leaves `--` as it is; "and the share page" was added (check
against spec 040).)

Accessibility (spec 035): every control above is reachable with `Tab` (the links
`account-link`, `account-page-link` and `account-room-link` have `tabindex="0"`,
since WebKit puts a link in the Tab order only with one, as spec 035 does for
`share-link`), shows AC-2's visible focus, has a label from `fr.json`, and its texts
meet 4.5:1; the dialog keeps
the focus inside while open (a modal `<dialog>`); messages use `role="status"` or
`role="alert"` as written. The account page has no horizontal scroll at the sizes of
spec 006 AC-5.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `account.open` | `Compte` |
| `account.dialog_heading` | `Retrouver vos parties sur tous vos appareils` |
| `account.dialog_intro` | `Recevez par e-mail un lien de connexion. Vous gardez votre place, votre couleur et vos lettres dans ce salon.` |
| `account.email_label` | `Adresse e-mail` |
| `account.send` | `Recevoir le lien` |
| `account.sent` | `Lien envoyé à {email}. Il est valable 30 minutes.` |
| `account.error.email` | `Adresse e-mail non valide.` |
| `account.error.too_many` | `Trop de demandes. Réessayez dans une heure.` |
| `account.error.send` | `Impossible d'envoyer le lien. Réessayez plus tard.` |
| `account.error.generic` | `Une erreur est survenue. Réessayez.` |
| `account.close` | `Fermer` |
| `account.signed_in_heading` | `Votre compte` |
| `account.signed_in_as` | `Connecté avec {email}` |
| `account.manage` | `Gérer mon compte` |
| `account.page_heading` | `Mon compte` |
| `account.signing_in` | `Connexion…` |
| `account.link_invalid` | `Ce lien n'est plus valable. Demandez-en un nouveau.` |
| `account.signed_out_intro` | `Recevez par e-mail un lien pour vous connecter.` |
| `account.back_to_room` | `Retourner au salon {code}` |
| `account.sign_out` | `Se déconnecter` |
| `account.delete` | `Supprimer mon compte` |
| `account.delete_warning` | `Votre adresse et la liste de vos salons seront effacées. Dans vos salons, votre pseudo deviendra « Ancien joueur ».` |
| `account.delete_confirm` | `Supprimer définitivement` |
| `account.delete_cancel` | `Garder mon compte` |
| `account.deleted` | `Votre compte a été supprimé.` |
| `player.former` | `Ancien joueur` |
| `email.sign_in.subject` | `Votre lien de connexion à Nock` |
| `email.sign_in.body` | `Bonjour,\n\nOuvrez ce lien pour vous connecter à Nock :\n{link}\n\nIl est valable 30 minutes et ne sert qu'une fois. Si vous n'avez rien demandé, ignorez ce message.` (`\n` is a line break in the JSON string) |

### Test harness

- `SETTINGS = AccountSettings(public_url="http://testserver", smtp=SmtpSettings(host="smtp.invalid", port=587, security="starttls", sender="nock@example.org"))`.
  A recording mailer (a test class with a `send` that keeps each `EmailMessage`) and
  a failing one (whose `send` raises `MailError`) stand for `SmtpMailer`.
- HTTP criteria: `TestClient(create_app(rooms=registry, dist_dir=tmp_path, accounts=SETTINGS, account_store=AccountStore(path), mailer=recorder))`,
  with `registry = RoomRegistry(clock=fake_clock, store=RoomStore(path))` and
  `path = tmp_path / "nock.sqlite3"` for both stores; players join through the
  TestClient's sockets (spec 011). The TestClient keeps the cookie between requests.
- Accounts off (AC-8): `TestClient(create_app(rooms=registry, dist_dir=tmp_path))`
  with `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` deleted by `monkeypatch`. (Note from
  the lead, 2026-10-21: added; the harness did not say how a test turns accounts
  off.)
- Addresses (AC-8) are Python string literals, or expressions that join or repeat
  them, as in "Configuration" below: `"françois@example.org"` holds U+00E7
  LATIN SMALL LETTER C WITH CEDILLA, and the address of 255 characters is
  `"ana@" + "a" * 63 + "." + "b" * 63 + "." + "c" * 63 + "." + "d" * 59`, whose
  local part and labels keep their rules, so that it breaks the length rule only.
  (Note from the lead, 2026-10-21: added with decision 15; AC-8 said "255
  characters" with no value.)
- The link token is read from the recorded message's body: the 43 characters after
  `/account#`.
- Database bytes: as spec 038's harness (`nock.sqlite3` and `nock.sqlite3-wal`).
- Test SMTP server (AC-7): a minimal SMTP server written in the test with asyncio
  streams on 127.0.0.1 and a free port (no new dependency): it greets with `220`,
  answers `EHLO`/`HELO` with `250`, `MAIL` and `RCPT` with `250` (or `550` when the
  case says so), `DATA` with `354` then `250` after the line `.`, `QUIT` with `221`,
  and records the envelope and the data.
- smtplib replaced (AC-7): `monkeypatch.setattr` of `smtplib.SMTP` and
  `smtplib.SMTP_SSL` with recorders that keep their arguments and calls.
- Configuration (AC-6): `account_settings_from_env` on plain dicts; `main()` with
  spec 036's recorder of `uvicorn.Server.run` and `monkeypatch` on the variables.
  Each case of `main()` sets or deletes every variable that `main()` reads (those
  of specs 036 and 038 and of "Configuration"), so that a variable left in the
  environment cannot change a case. Values are Python string literals, or
  expressions that join or repeat them, as in spec 036's harness: `"\n"` is a
  newline (U+000A), `"\t"` a tab (U+0009), `"\u200b"` U+200B ZERO WIDTH SPACE,
  `"\u202e"` U+202E RIGHT-TO-LEFT OVERRIDE, `"\u2028"` U+2028 LINE SEPARATOR,
  `"\u00e7"` U+00E7 LATIN SMALL LETTER C WITH CEDILLA, `"\u00e9"` U+00E9 LATIN
  SMALL LETTER E WITH ACUTE, and `"a" * 64 + ".example"` is 64 `a` followed by
  `.example`. (Note from the lead, 2026-10-16: the last two sentences added with
  decisions 13 and 14 (review of spec 036's refinement).)
- The app's account store (AC-6): the test replaces `nock.server.AccountStore`
  (`monkeypatch.setattr`) with an `AccountStore` subclass whose `__init__` appends
  `str(path)` to a list, then calls `AccountStore.__init__`. The app of
  `create_app` builds its account store with that name when it starts, so
  `with TestClient(app):` makes the subclass record the path, as spec 036's
  harness does for `RoomStore`. (Note from the lead, 2026-10-16: added with
  decision 13 (review of spec 036's refinement).)
- Browser with live server: the test module starts its own server as spec 040's
  `live_server` does (built client, free port of 127.0.0.1, `uvicorn.Server` with
  `server_config`, as spec 038's harness), with
  `create_app(rooms=room_registry, dist_dir=WEB_DIST_DIR, catalogue=..., accounts=AccountSettings(public_url=<its base URL>, smtp=SETTINGS.smtp), account_store=AccountStore(path), mailer=recorder)`.
  Devices are browser contexts (separate storage and cookies). (Note from the lead,
  2026-10-21: "`uvicorn.Server` with `server_config`, as spec 038's harness" was
  added: `live_server` builds its server that way since spec 036.)
- Browser with mocked routes (AC-9): spec 040's mocked socket, plus
  `page.route("**/api/account", ...)` answering `{"signed_in": false, "email": null}`
  (or signed in) and `page.route("**/api/account/link", ...)`; the window sizes of
  spec 006 AC-5 in desktop and touch contexts as in spec 013 AC-6 (spec 009's touch
  harness).
- Logs (AC-10): `caplog` at level `DEBUG` for every logger
  (`caplog.set_level(logging.DEBUG)`). A record holds a string when the text of
  `logging.Formatter().format(record)`, which adds its traceback, holds it, as in
  spec 038's "In-process logs". (Note from the lead, 2026-10-21: the records were
  "formatted with `record.getMessage()`", which leaves out a traceback, where a
  chained `smtplib` error would show the address (check against spec 038).)
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check of
  this spec is Chromium-only (`<dialog>`, cookies and `history.replaceState` work in
  all three).

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-9.2.1) (HTTP; Python) A guest in a room asks for a sign-in link by e-mail, and using it creates the account without changing their player. `Ana` (token `TA`, colour 0, host) and `Bob` join a FX-01 room and Ana writes `T` at (1, 0). `POST /api/account/link` with `{"email": "  Ana.Probe@Example.org ", "room": {"code": <code>, "resume_token": TA}}` answers 202 with `{}`, and the recorder holds one message with `To` `ana.probe@example.org`, `From` `nock@example.org`, `Subject` `fr.json["email.sign_in.subject"]`, and a body equal to `fr.json["email.sign_in.body"]` with `{link}` replaced by `http://testserver/account#<token>`, the token being 43 characters of `A-Za-z0-9_-`. `POST /api/account/sign-in` with that token answers 200 with `{"email": "ana.probe@example.org", "room_code": <code>, "rooms": [{"code": <code>, "player_id": <Ana>, "resume_token": TA, "nickname": "ANA"}]}` and a `set-cookie` header for `nock_session` with `HttpOnly`, `Max-Age=7776000`, `Path=/` and `SameSite=Lax`, and without `Secure`; then `GET /api/account` answers `{"signed_in": true, "email": "ana.probe@example.org"}`. The room's `players`, `seq`, cells and log are the same as before the link was asked: Ana keeps her id, nickname, colour, host role and `joined_seq`, (1, 0) keeps `T` authored by her, and nothing was sent on the sockets. Using the token again answers 404; a second link used 1,801 seconds of the fake clock after it was asked answers 404, and one used 1,799 seconds after answers 200. With `public_url` `https://nock.example`, the cookie also has `Secure`. (Note from the lead, 2026-10-21: the nickname of `rooms` read `"Ana"`; the server sends it in capitals, spec 039's "Nicknames in capitals", and this answer is compared as JSON.) Python, for the purge of "HTTP routes", each case on a new `AccountStore(tmp_path / "nock.sqlite3")`: `token = add_link("ana.probe@example.org", None, 0.0)` (the database files, `nock.sqlite3` and `nock.sqlite3-wal` as "Database bytes" of "Test harness" reads them, then hold the address), then `purge(1_801.0)`, then `use_link(token, 0.0)` gives None (at time 0 the link is not too old, so only the purge can have removed it), and the files hold no byte of the purged address (its UTF-8 bytes occur in neither file; no account holds it, since asking for a link creates none); the same for a session, except for the bytes, since the account keeps its address: `session = sign_in("ana.probe@example.org", 0.0).session`, then `purge(7_776_001.0)`, then `account_of_session(session, 0.0)` gives None. A link and a session just under their life are kept: after `purge(1_799.0)`, a link asked at 0.0 still answers `use_link(token, 0.0)` with its address; after `purge(7_775_999.0)`, a session started at 0.0 still answers `account_of_session(session, 0.0)` with its account. App: a link asked before the app starts is gone after the sweep that the app runs when it starts (spec 032): `token = add_link("ana.probe@example.org", None, t)` on the `AccountStore` given to `create_app`, with `t` the fake clock's time, the clock advanced by 1,801 seconds, then `with TestClient(app):`; the spec does not say that the start waits for its sweep, so the store given is a subclass whose `purge` calls the original and then sets a `threading.Event`, and the test waits for that event (it cannot poll with `use_link`, which deletes the link it finds); `purge` was called with the fake clock's time, and `use_link(token, t)` gives None. (Note from the lead, 2026-10-21, first review of spec 033: the Python part, and "Python" in the brackets, were added. No check ran `purge`, which is the only thing that removes the address of someone who asked for a link and never used it ("What the accounts keep"); the edge case "Session expiry" already points here. A `use_link` at the time of the purge would not tell the purge from the expiry check, which answers None too. The two kept checks are the other side of the rule: a purge that deleted every link and session would pass the others.) (Note from the lead, 2026-10-21, first review of spec 033: the check of the files' bytes was added with the checkpoint at the end of `purge` (`nock.accounts`): without it, a purged address could stay in `nock.sqlite3-wal` (spec 038). It is made on the first case only, the link; the app case checks rows, not bytes.)
- **AC-2** (AC-9.2.1) (browser with live server) From inside a room, a guest creates an account and keeps the same seat, colour and authorship, also on a second device. Device 1 (context 1) enters a FX-01 room as `Ana` and types `T` at (1, 0); she clicks `account-open`, `account-dialog` opens with the focus on `account-email-input`, she types `ana.probe@example.org` and submits: `account-sent` reads `Lien envoyé à ana.probe@example.org. Il est valable 30 minutes.` and the recorder holds one message. A new page of context 1 opens the message's link: `account-page` reaches `data-state="signed_in"`, `account-email` reads `Connecté avec ana.probe@example.org`, the page's URL is `<base>/account` with no fragment, and `account-room-link` has `href="/r/<code>"`; Ana's room page is still `joined` with the same `data-you` and roster `data-colour` as before, and the server's cell (1, 0) is still authored by her `data-you`. Device 2 (context 2, empty storage) opens `/account`, which shows `signed_out`, asks for a link with the same address and opens the new link: `signed_in`, and `localStorage["nock.identity.<code>"]` of context 2 holds Ana's player id and token. Device 2 then opens `/r/<code>`: its room page reaches `data-status="joined"` with the same `data-you` as device 1, without `nickname-form`, its roster lists `Ana` with the same `data-colour`, and device 1's room page reaches `data-status="replaced"` (spec 012).
- **AC-3** (AC-9.2.2) (browser with live server) No action needed to finish a grid requires an account. With accounts on, a page in a fresh context (no cookie, no storage) opens the room link of a FX-01 room, enters as `Ana`, types the 18 letters word by word with `X` in place of `I` at (2, 2), 60 ms or more between keys (spec 037's harness), selects the word `MIME` and presses `check-word` (spec 023), types `I` at (2, 2), and reaches `data-solved="true"` with `grid-status` `solved` (spec 026). No response of the page had status 401 or 403, none had a `set-cookie` header, `context.cookies()` is empty, `account-dialog` never had the `open` attribute, and every frame the page sent parses with `parse_client_message` (spec 039 has no account field).
- **AC-4** (AC-9.2.3) (HTTP; Python) Deleting my account removes my personal data at once. `Bob` then `Zélie-Probe` (token `TZ`) join room R, so Bob is host; Zélie writes `T` at (1, 0), asks a link from R with `zelie.probe@example.org` and signs in; she also joined room S, linked it with `PUT /api/account/rooms`, and timed out there (a past player of S, spec 032); she asks one more link and leaves it unused. `DELETE /api/account` answers 204 and clears `nock_session` (`Max-Age=0`). Then `GET /api/account` with the old cookie answers `{"signed_in": false, "email": null}`, `GET /api/account/rooms` answers 401, and the unused link answers 404. In R, Zélie's record keeps its player id and colour with the nickname `--`, (1, 0) keeps `T` authored by her id, the log holds her `player_joined` with nickname `--` at the same seq, and a new client joining R gets a snapshot whose view of her has the nickname `--`; in S her past record has the nickname `--`. The database files then hold neither `zelie.probe@example.org` nor `ZÉLIE-PROBE` (UTF-8; the nickname she joined with, as the server stores it, spec 012), and still hold `BOB`. (Note from the lead, 2026-10-16: the bytes searched were `Zélie-Probe` and `Bob`, which the store never holds once nicknames are in capitals (human's rule of 2026-10-16: nicknames in capitals).) Python, for a former player seated back: on a FX-01 room whose `players` hold `BOB` and a player named `--`, and whose `past_players` hold a past player named `--` whose token is `TP`, `join_room` with `Join(nickname="Autre", resume_token=TP)` gives exactly one entry, a `PlayerJoined` of that past player's id whose view has the nickname `--`, not `-- 2`, and in the new state two players of `players` are named `--`. (Note from the lead, 2026-10-21: the Python part was added, with "Python" in the brackets, for "Seat back of a former player" (from spec 032's pass).) Erasure paths that the play above does not run, three more plays: (a) a stored snapshot of S that holds her: `Dan` is in S with her, so that S ticks and she times out (specs 017 and 032); after her time-out he leaves S, the room's task stops and saves a snapshot (spec 018), and the setup waits until S's stored snapshot holds Zélie in `past_players` with the nickname `ZÉLIE-PROBE` (for example through a `RoomStore` subclass that records what `save_snapshot` receives) before it sends `DELETE /api/account`; then no database file holds `zelie.probe@example.org` or `ZÉLIE-PROBE`, and after a restart (the first process stops, which saves a snapshot of each live room, spec 018; a second registry and app open the same file) the files still hold neither, and R and S load with her records named `--` (in `players` of R, in `past_players` of S). (b) A deletion after a restart: the play above runs up to the deletion in a first app, which then stops; `DELETE /api/account` goes to a second app on the same database file (its own registry, `RoomStore` and `AccountStore`, and a client with no cookie), with the old session in a `Cookie` header; it answers 204 and clears the cookie, no room is live in that app, and then R and S load with her records named `--`, the log of R holds her `player_joined` with `--`, and the files hold neither her address nor `ZÉLIE-PROBE`. (c) An account with no room: `ana.probe@example.org` asks a link with `"room": null` and uses it, and the files hold the address; `DELETE /api/account` answers 204, and the files then hold no `ana.probe@example.org`. (d) Python, a link after the erasure, on a new `AccountStore`: `a = sign_in("zelie.probe@example.org", 0.0).account_id`, a `RoomIdentity` of nickname `ZÉLIE-PROBE` is linked (`link_identity(a, identity, 1.0)` returns True), then `delete_account(a)`; then `link_identity(a, identity, 2.0)` returns False, `identities(a)` is `[]`, the raw `account_identities` table holds no row for `a` (read with `sqlite3` on the file), and the database files hold no `ZÉLIE-PROBE`. Through the routes, a `PUT /api/account/rooms` whose session was checked before the deletion cannot be timed from outside, so the test replaces the app's `account_store` with a subclass whose `link_identity` first calls `delete_account` for the account, then the original: the `PUT` answers 401 and the files hold no `ZÉLIE-PROBE`. (Note from the lead, 2026-10-21, second review of spec 033: (d) was added for the rule of `link_identity` in `nock.accounts`; it is one more check of this criterion, not a new one.) (Note from the lead, 2026-10-21, first review of spec 033: the three plays were added. The tests of the play above skip three paths of the erasure: the rewrite of a stored snapshot (S kept only its first snapshot, which holds no player, since Dan stayed in S, so a restart had no snapshot to bring a nickname back from); the erasure of a room that is only in the store (every room was live); and the checkpoint of `delete_account` on its own (the checkpoint of a room's erasure follows it, so a missing one would have passed). (a), (b) and (c) run them in turn.)
- **AC-5** (AC-9.2.3) (browser with live server) Other players then see "former player". In the play of AC-4 on the live server, Zélie deletes her account from `/account`: `account-delete` shows `account-delete-warning`, `account-delete-confirm` sends the deletion, and the page reaches `data-state="deleted"` with `fr.json["account.deleted"]`; `account-delete-cancel` instead keeps the account (a `GET /api/account` still says signed in). Bob's page in R (he is host), reloaded, shows Zélie's `roster-nickname` as `Ancien joueur` and her `remove-player` with the `aria-label` `Retirer Ancien joueur du salon`, and, after Zélie (still in the room as a guest) checks a word, the feed line `Ancien joueur a vérifié un mot`; on `/`, Bob's "My rooms" item of R reads `Joueurs : Bob, Ancien joueur`; and once R is solved, spec 028's recap names her `Ancien joueur`. No page shows `--`.
- **AC-6** (new) (Python, `uvicorn.Server.run` replaced; app started with `TestClient`) Accounts are configured by environment variables, and an invalid value stops the start. `account_settings_from_env` gives None for `{}` and when `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both empty; with `NOCK_PUBLIC_URL="https://nock.example/"`, `NOCK_SMTP_HOST="smtp.example"` and `NOCK_SMTP_FROM="nock@nock.example"` it gives `AccountSettings(public_url="https://nock.example", smtp=SmtpSettings(host="smtp.example", port=587, security="starttls", user=None, password=None, sender="nock@nock.example"))`; `NOCK_SMTP_SECURITY` `tls` and `none` give the ports 465 and 25, and `NOCK_SMTP_PORT="2525"` gives 2525. Each of these raises `SettingsError` whose message names the variable: `NOCK_PUBLIC_URL` of `nock.example`, `ftp://nock.example`, `https://nock.example/app`, `https://nock.example?x=1`, `https://u@nock.example` or `https://`; only one of `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` set (the message names the missing one); `NOCK_SMTP_SECURITY="STARTTLS"`; `NOCK_SMTP_PORT` of `abc`, `0`, `65536` or ` 587`; a missing or invalid `NOCK_SMTP_FROM`; `NOCK_SMTP_USER` without `NOCK_SMTP_PASSWORD`, and the reverse; `NOCK_SMTP_PASSWORD="pw-SECRET-9"` with `NOCK_SMTP_SECURITY=none`. No message holds `pw-SECRET-9`, nor does `repr` of the settings when the password is valid. `main()` with an invalid variable raises `SystemExit` whose `code` is a `str` naming it and never calls `run`. Special characters (decisions 13 and 14), each case changing the valid settings above only by the variables it names: `account_settings_from_env` gives None when `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both empty and `NOCK_SMTP_PORT` is `"abc"` (accounts off, so it is not read); `NOCK_SMTP_HOST` of `"smtp.example."`, `"::1"` and `"a" * 63 + ".example"` gives that `host`; `NOCK_SMTP_PORT="0" * 5000 + "2525"` gives the port 2525; `NOCK_SMTP_USER="nock team"` with `NOCK_SMTP_PASSWORD="pw SECRET 9"` gives that `user` and a `password` whose `get_secret_value()` is `"pw SECRET 9"`. Each of these raises `SettingsError` whose message names the variable: `NOCK_PUBLIC_URL` of `"https://nock.example\n"`, `"https://nock..example"`, `"https://nock.example:0"`, `"https://::1"` and `"http://[::1]:8000"`; `NOCK_SMTP_HOST` of `"smtp.example\n"`, `"smtp\u200b.example"`, `"smtp..example"`, `"a" * 64 + ".example"`, `"[::1]"` and `"smtp.example:25"`; `NOCK_SMTP_PORT="587\n"`; `NOCK_SMTP_SECURITY="tls\n"`; `NOCK_SMTP_USER` of `"nock\n"`, `"nock\u2028"` and `"fran\u00e7ois"`, with `NOCK_SMTP_PASSWORD="pw SECRET 9"`; `NOCK_SMTP_FROM` of `"\tnock@nock.example"`, which `normalize_email` would strip, `"nock\u200b@nock.example"`, and `"fran\u00e7ois@nock.example"`, which `normalize_email` refuses too since decision 15; `NOCK_SMTP_PASSWORD` of `"pw-SECRET-9\n"`, `"pw-SECRET\u202e-9"` and `"mot-de-pass\u00e9"`, with `NOCK_SMTP_USER="nock"`; the message for `"mot-de-pass\u00e9"` holds neither that value nor `mot-de-pass`. In the whole criterion, a message that refuses the value of a variable of the table of "Configuration" other than `NOCK_SMTP_PASSWORD` contains `repr(value)`; a message that names a missing variable rather than refusing a value (only one of `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` set, `NOCK_SMTP_USER` without `NOCK_SMTP_PASSWORD`, a missing `NOCK_SMTP_FROM`) holds none of the values that its case sets; every message has one item in its `splitlines()` and holds no character of Unicode general category Cc, Cf, Zl or Zp; and `SECRET` (capital letters), which both passwords of this criterion, `pw-SECRET-9` and `pw SECRET 9`, contain, appears in no message and in no `repr` of valid settings. `main()` with `NOCK_SMTP_HOST="smtp.example\n"` and the other variables of the valid settings raises `SystemExit` whose `code` contains `repr("smtp.example\n")` and has one item in its `splitlines()`. App: with `NOCK_DATABASE` unset, and with it set to `""`, the app of `create_app(dist_dir=tmp_path, accounts=SETTINGS, mailer=recorder)`, started and stopped by `with TestClient(app):` while `nock.server.AccountStore` is the recording subclass of "Test harness", builds at least one account store, every one with the path `":memory:"` and none with `""`. (Note from the lead, 2026-10-16: "app started with `TestClient`" added to the brackets, and the text from "Special characters" on added, with decisions 13 and 14. The criterion used to end with "never calls `run`": it had no value with a special character, and said of the messages only that they name the variable and never hold `pw-SECRET-9` (review of spec 036's refinement).) (Note from the lead, 2026-10-16: the last check of "In the whole criterion" was "no message holds `pw-SECRET`", but the cases of `NOCK_SMTP_USER` use the password `"pw SECRET 9"`, which does not hold it, so a message that showed that password passed every check; the check is now on `SECRET`, which both passwords hold, and covers `repr` of valid settings too. The check on a refused value is limited to the variables of the table, and a message that names a missing variable holds none of its case's values (see "Messages") (second review of spec 036's refinement).) (Note from the lead, 2026-10-21: `NOCK_PUBLIC_URL="http://[::1]:8000"`, which gave that `public_url`, is now refused, decision 16; `"françois@nock.example"` was the sender "which `normalize_email` accepts", until decision 15.)
- **AC-7** (new) (Python with a test SMTP server; Python with smtplib replaced; HTTP) The sign-in link is sent with the standard library, over a checked TLS connection. With the test SMTP server and `security="none"`, `SmtpMailer(...).send(sign_in_message(SETTINGS, "ana.probe@example.org", <43-character token>))` delivers one message: envelope from `nock@example.org` to `ana.probe@example.org`; parsed with `email.message_from_bytes(data, policy=email.policy.default)`, its subject is `fr.json["email.sign_in.subject"]`, its content type `text/plain` with charset `utf-8`, and its body holds `http://testserver/account#<token>`. With smtplib replaced: `starttls` makes `SMTP("smtp.example", 587, timeout=10)`, then `starttls(context=c)` with `c.verify_mode == ssl.CERT_REQUIRED` and `c.check_hostname is True`, then `login("nock", <password>)` when a user is set, `send_message` and `quit`; `tls` makes `SMTP_SSL("smtp.example", 465, context=c, timeout=10)` with the same checks. A server answering `550` to `RCPT` makes `send` raise `MailError`, and neither `str` of that error nor its traceback text (`"".join(traceback.format_exception(error))`) holds `ana.probe@example.org`; through the app, the link request then answers 503 with `{"detail": "Mail not sent"}`. (Note from the lead, 2026-10-21: the check of the error's text and traceback was added, for the docstring of `MailError`.)
- **AC-8** (new) (HTTP) Link requests reveal nothing and cannot flood a mailbox. The answer to a link request is the same 202 `{}` for an address that has an account and one that has none. `POST /api/account/link` with `email` `""`, `ana`, `ana@`, `@example.org`, `ana@example`, `ana @example.org`, `"françois@example.org"` (decision 15), `x1,victim@example.org`, `a<b@example.org`, `a"b@example.org` (decision 15, the local part's characters) or the address of 255 characters of "Test harness" answers 422 with exactly `{"detail": "Invalid e-mail address"}` and sends nothing. With a `room` whose token is no member's, it answers 404 with `{"detail": "Not Found"}` and sends nothing. None of these refusals counts toward the limits below. Three requests for one address within an hour of the fake clock are sent; the fourth answers 429 and sends nothing; after `advance(3600)` one is sent again. From one client address, ten requests for ten addresses are sent and the eleventh answers 429. An address with an allowed mark in its local part, `ana+1@example.org`, answers 202 and is sent to `ana+1@example.org`. The limits stop counting a request once it is older than an hour: one request for `ana@example.org` at fake time t, then `advance(3601)` and 3 more for the same address, are all answered 202 and sent; and ten requests from one client address at t, then `advance(3601)` and ten more for ten other addresses, are all answered 202. (Note from the lead, 2026-10-21, second review of spec 033: the `+` address and the two expiry cases were added; the review found them untested. The first one is a mark that decision 15 allows, so a rule that refused every mark would have passed the others; the others are the "forgets them" rule of "A link request" for the address and for the client address, where the check above only covers the address at exactly 3,600 seconds.) With accounts off, `GET /account`, `GET /api/account`, `POST /api/account/link` and `DELETE /api/account` answer 404. (Note from the lead, 2026-10-21: `"françois@example.org"` was added with decision 15; "or 255 characters" now names the value of "Test harness"; "answers 422, sends nothing, and its body does not hold the address sent" became the exact body, which holds no address, since no body can leave out the empty address; the 404's body and the sentence on counting ("A link request" of "HTTP routes") were added.) (Note from the lead, 2026-10-21, first review of spec 033: `x1,victim@example.org`, `a<b@example.org` and `a"b@example.org` were added, with the new rule for the local part (decision 15). Each is refused as decision 15 says: 422 and `account.error.email` (the page shows any 422 of a link request with that text, "Client"), nothing sent and no count toward the limits. So `x1,victim@example.org` and `x2,victim@example.org` no longer count as two addresses that both reach `victim@example.org`.)
- **AC-9** (new) (browser with mocked socket and routes; keyboard only for the walk) The account controls meet spec 035 and keep the room page's layout. With accounts on (mocked `GET /api/account`) and a FX-01 snapshot, at each window size of spec 006 AC-5, in desktop and touch contexts: `account-open` is the last `button` element inside `room-toolbar`; at 320 by 568, 568 by 320, 360 by 740 and 740 by 360 its vertical range overlaps those of the toolbar's other buttons (spec 024's one-row rule), and after `account-open` is scrolled into view (as a keyboard focus does) it is visible whole inside the toolbar; and spec 013 AC-6's checks pass (after a tap on a cell, `grid-viewport` at least 100 px high, no page scroll, the grid fits at zoom 1, the clue bar inside the window above the keyboard). Keyboard only: `tab_to` reaches `account-open`, which shows spec 035 AC-2's outline; `Enter` opens `account-dialog` with the focus on `account-email-input`; during 10 presses of `Tab`, then 10 of `Shift+Tab`, no element outside `account-dialog` gets the focus (the rest of the page is inert while it is open; the browser may move the focus to its own interface, as spec 035 "Nothing focusable after the grid" describes); `Escape` closes it and the focus is back on `account-open`. Spec 035's contrast and language scans find no offending element at 1280 by 720 and 360 by 740 on the room page with the dialog open, then showing `account-sent`, then showing `account-error`, and on `/account` in the states `signed_out`, `signed_in`, `link_invalid` and `deleted` (mocked answers); `/account` has no horizontal scroll at the sizes of spec 006 AC-5. (Note from the lead, 2026-10-21: "the last control" became "the last `button` element", since spec 024's `room-toolbar-more` mark is the toolbar's last child.)
- **AC-10** (new) (HTTP with captured logs) Secrets and addresses never reach a log, and tokens are stored hashed. With `SETTINGS` given the user `nock` and the password `pw-SECRET-9`, during a link request, a sign-in, `GET /api/account`, a `PUT /api/account/rooms`, a sign-out, a link request that fails with the failing mailer, and a deletion, no log record holds (as "Logs" of "Test harness" reads a record) the link token, the session cookie's value, `TA`, the address `ana.probe@example.org`, or the SMTP password `pw-SECRET-9`. After the sign-in, the database files hold the address but neither the link token nor the session value (their SHA-256 hex digests are stored instead). (Note from the lead, 2026-10-21: "(formatted)" became the reference to "Logs", whose formatter now adds the traceback, as spec 038's does.)
- **AC-11** (new) (HTTP; browser with live server) A signed-in device gets the rooms of the account. HTTP: after Ana's sign-in of AC-1, `GET /api/account/rooms` answers `[{"code": R, "player_id": <Ana>, "resume_token": TA, "nickname": "ANA"}]`; after she joins room S as a new player (token `TA2`) and sends `PUT /api/account/rooms` with S and `TA2` (204), it lists S then R; a `PUT` with a token that is no member's of S answers 404, and one without the cookie 401; once R expires (spec 032), the list holds S only. Browser: device 2 of AC-2, once signed in, opens `/`: its "My rooms" (spec 032) lists Ana's room, and `account-link` points to `/account`; a signed-in room page sends one `PUT /api/account/rooms` with its code and token after its first snapshot. (Note from the lead, 2026-10-21: the nickname read `"Ana"`; the server sends it in capitals, spec 039's "Nicknames in capitals".)

## Edge cases and errors

- Address case (AC-1): stored lower-cased and trimmed; `Ana.Probe@Example.org` and
  `ana.probe@example.org` are one account.
- Link on another device (AC-2): the link signs in the device that opens it, wherever
  it was asked; a mail scanner that fetches the link gets `index.html` only, since the
  token is in the fragment and is used by the page's `POST`.
- Signed in elsewhere (AC-2): opening the room on device 2 resumes Ana's player while
  her resume window lasts (spec 017); device 1 shows `replaced`. After a time-out,
  the identity seats Ana back with the same player id, her nickname (with spec 012's
  suffix if a player took it meanwhile) and her colour while no player of the room
  has it (spec 032 AC-7), unless the room is full or locked. (Note from the lead, 2026-10-15: "After a time-out the identity no
  longer resumes (spec 032, open question 1)" became the sentence above, after spec
  032's decision 11.)
- An existing account (AC-1): a link for an address that has an account signs in to
  it and links the room's identity to it.
- Room gone or player gone before the link is used (AC-1): the account is created or
  signed in, and no identity is linked (`room_code` None).
- A second sign-in on a device (AC-1): the new cookie replaces the old one in the
  browser; the old session is not ended, and goes at the first sweep after its 90
  days (decision 16). (Note from the lead, 2026-10-21: this read "the session the
  request carried ends".)
- Session expiry (AC-1): after 90 days the cookie no longer signs in; `GET /api/account`
  says signed out. Expired links and sessions are deleted by the sweep (spec 032).
- Deleting while in a room (AC-4, AC-5): the player stays in the room as a guest; their
  nickname becomes `--` there, and their own page shows `Ancien joueur` for themself
  after its next snapshot. Pages already open show the old nickname until their next
  snapshot (no event announces the change).
- Chat (AC-4): messages that the deleted player wrote stay in the room (they are part
  of the others' conversation) and are attributed to `Ancien joueur`; they go with the
  room at expiry (spec 038).
- Other people's devices (AC-4): a name kept in another player's `localStorage` (spec
  029's history) cannot be erased by the server.
- Two erased players (AC-5): both read `Ancien joueur`; "My rooms" lists that name once
  (spec 032's `team_nicknames`).
- CSRF (AC-1, AC-4): `SameSite=Lax` keeps the cookie off requests that other sites make
  with `POST`, `PUT` and `DELETE`; the deletion also needs the page's confirmation.
- Mail failure (AC-7): the player sees `account.error.send` and can try again; the
  failed attempt counts toward the limits of AC-8.
- Limits after a restart (AC-8): they are kept in memory and start again at zero.
  Meanwhile a key whose counted requests are all older than an hour is forgotten
  ("A link request"). (Note from the lead, 2026-10-21: the sentence on forgetting
  was added.)
- Room code reused (AC-11): an identity whose room was deleted is not served, even
  once a new room draws its code, since its token is no member's of the new room;
  the account keeps it until it is deleted (decision 16). (Note from the lead,
  2026-10-21: added.)
- Former player seated back (AC-4): a past player erased to `--` who comes back with
  their device's token is seated back as `--`, with no suffix, also when another
  player of the room is `--`; their own page then shows `Ancien joueur` for them.
  (Note from the lead, 2026-10-21: added from spec 032's pass.)
- Header row (AC-9): the button must never add a row to the header; spec 013 AC-6's
  floor of 100 px left 3 px at 568 by 320 before spec 024's toolbar. It goes into
  that toolbar, whose sideways scroll and edge fade (`room-toolbar-more`) show that
  more controls follow.
- Accounts turned off later (AC-8): the account rows stay in the database, unused,
  until the account is deleted or accounts are turned on again; cookies are ignored.
- Former nickname on the server (AC-4): `--` passes spec 039's length check and fails
  spec 012's character rule, so no player can join with it.
- An app started without `main()` (AC-6), such as `uvicorn nock.server:app`,
  checks the variables of "Configuration" when it starts, as `main()` does, but
  not the characters of `NOCK_DATABASE`, which only `main()` checks (spec 036
  AC-11); the account store opens the file of the rooms' store, or `":memory:"`
  when the variable is unset or empty. (Note from the lead, 2026-10-16: added
  with decision 13 (review of spec 036's refinement).)

## Out of scope

- Payments and subscriptions (epic E9).
- Room resume: spec 032.
- Catching up after an absence: spec 034 (each device keeps its own seen seq).
- Game history: spec 029, which lists an account's finished grids.
- Passwords, social sign-in, changing the address, several addresses per account.
- Sending other e-mails (newsletters, reminders), and an outgoing mail queue.
- Removing the deleted player's messages from the chat, and erasing data from backups.
- Merging two accounts, or a room identity linked to two accounts at once (the later
  link wins on each device).
- An IPv6 address in `NOCK_PUBLIC_URL`, and deleting an identity of a deleted room
  before its account is deleted (decision 16). (Note from the lead, 2026-10-21:
  added.)
- Getting a timed-out player back in a room: spec 032 AC-7, which seats them back
  with their token, also the token an account gives a device. (Note from the lead,
  2026-10-15: "(spec 032, open question 1)" became "spec 032 AC-7", after spec 032's
  decision 11.)

## Work packages

None.

## Decisions

Proposed by the spec-writer on 2026-10-14 for the Phase 6 refine, with the human's
answers of the same day (send the sign-in link with the standard library `smtplib`
and SMTP settings from environment variables, no new dependency; numeric thresholds:
keep the backlog defaults, so 30 days for the deletion). They are part of the spec
above and are approved with it.

1. One flow for sign-up and sign-in. Asking for a link creates nothing; using it
   creates the account when needed. So the answer never tells whether an address has
   an account.
2. Link token in the URL fragment, used by the page with a `POST`: a server log never
   holds it, and a mail scanner that fetches links cannot use it up. The app has no
   redirect (spec 040 AC-28 forbids 3xx).
3. Links point at `NOCK_PUBLIC_URL`, never at the request's host, so a forged `Host`
   header cannot send a victim a link to another site.
4. Session cookie: `HttpOnly`, `SameSite=Lax`, `Secure` on HTTPS; tokens and sessions
   stored as SHA-256 digests.
5. TLS: `ssl.create_default_context()`, because `smtplib` checks no certificate
   without a context. A password over a plain connection (`none`) is refused.
6. Spec 005's scan: `smtplib` and `ssl` allowed in `nock/mailer.py` only (lead's
   amendment of spec 005, see "Spec 005 amendment"). (Note from the lead,
   2026-10-21: done, spec 005 decision 7.)
7. Texts of the e-mail from `fr.json`, read by the server (`nock.i18n`), like every
   other text.
8. Erasure (AC-4): at once, rather than within 30 days; the account's rows are
   deleted, and the nickname of each of its players is replaced in the room's state,
   snapshots and log, so that recaps show "former player". Options for the marker:
   a new protocol field (a change to spec 039) or a reserved nickname. Pick: the
   reserved nickname `--`, which no player can choose.
9. Rooms across devices (AC-11): the account keeps each room identity the player
   linked; a signed-in device stores the missing ones, and never replaces one it has.
10. The account button is the last control of spec 024's `room-toolbar`, since the
    568 by 320 header has no spare row and that toolbar is the room's one place for
    tools (AC-9); the dialog sits outside the toolbar so that its scrolling cannot
    clip it.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question.

11. Thresholds, none of which is in the backlog (former open question 1). Options:
    keep the proposed values, or set others (the texts `account.sent` and
    `email.sign_in.body` say "30 minutes" and would change with them). Pick: keep
    them: a sign-in link lives 30 minutes and works once, a session lives 90 days,
    and at most 3 links per address and 10 per client address are sent per hour.
    Already part of the spec above; the comments of the four constants of
    `nock.accounts` now point here.
12. Spec 005's scan (former open question 2). Options: (a) one exception, so that
    `src/nock/mailer.py` may import `smtplib` and `ssl`; (b) send mail from a
    separate process outside `src/`, which splits the server in two. Pick: (a).
    Already part of the spec above ("Spec 005 amendment", decision 6). The lead
    refines spec 005, a `done` spec, with a dated note before this spec's tests are
    written, and the test-writer updates spec 005's scan tests before the
    implementer runs. (Note from the lead, 2026-10-21: spec 005 is refined, its
    decision 7; its AC-4 changed, so its tests follow.)

Decided by the lead on 2026-10-16, after the review of spec 036's refinement,
under the human's rule of the same day, "Technical variables should not contain
special characters". Already part of the spec above.

13. The rules of spec 036 for the variables of this spec (AC-6). Spec 036's
    decision 15 counts an empty `NOCK_DATABASE` as unset, like the other technical
    variables, and cites this spec for that rule, but this spec still opened
    `AccountStore` on an empty `NOCK_DATABASE`; `NOCK_SMTP_HOST` refused only
    spaces, `NOCK_SMTP_USER` and `NOCK_SMTP_PASSWORD` took any non-empty text, and
    the messages showed the value with no rule for escaping it. Options: (a) keep
    this spec's rules; (b) give each variable the rule of its kind in spec 036.
    Pick: (b). A host (`NOCK_SMTP_HOST`, and the host of `NOCK_PUBLIC_URL`) takes
    the characters of `NOCK_HOST` (spec 036 decision 11) and its labels (spec 036
    decision 16); inside the URL an IPv6 address is written between `[` and `]`,
    as every URL writes it, since there `:` introduces the port (note from the
    lead, 2026-10-21: since this spec's decision 16, the URL takes no IPv6
    address). A port
    (`NOCK_SMTP_PORT`, and the port of `NOCK_PUBLIC_URL`) takes the rule of
    `NOCK_PORT`. Free text (`NOCK_SMTP_USER`, `NOCK_SMTP_FROM`) refuses the set of
    `NOCK_DATABASE` (spec 036 decision 14), and so does the secret,
    `NOCK_SMTP_PASSWORD`, whose message names the variable and never shows the
    value, as spec 038 does for the operator token; this spec's decision 14
    then narrows these three to printable ASCII. `NOCK_SMTP_SECURITY` takes
    three exact words, so it holds no special character already. An unset or
    empty variable takes the default of "Configuration", and the account store is
    `":memory:"` when `NOCK_DATABASE` is unset or empty (spec 036 decision 15). A
    message shows a refused value as `repr(value)`, on one line (spec 036
    decision 12). The checks stay where this spec already reads the variables:
    `main()` before it builds a server, and the app's start when it is given no
    `accounts`; while accounts are off, the other `NOCK_SMTP_*` variables are
    neither read nor checked. (a) was rejected: it leaves these variables outside
    the human's rule, and an empty `NOCK_DATABASE` would put the accounts in a
    private temporary file while the rooms stay in memory.

Decided by the lead on 2026-10-16, answering open question 1 of the same day
(raised with decision 13), after a check of `smtplib`. Already part of the spec
above.

14. SMTP login and sender in ASCII (former open question 1 of 2026-10-16; AC-6).
    Python's `smtplib` encodes the user and the password of `login` as ASCII: the
    lead checked that, with Python 3.14.6,
    `smtplib.SMTP.login("fran\u00e7ois", "mot-de-pass\u00e9")` raises
    `UnicodeEncodeError` (`'ascii' codec can't encode character '\xe7'`), and
    that an ASCII login passes. Its `send_message` also needs the server's
    SMTPUTF8 extension when the sender or a recipient is not in ASCII (line 970
    of CPython 3.14's `smtplib.py`), and `normalize_email` accepts a local part
    outside ASCII (note from the lead, 2026-10-21: since decision 15, it refuses
    one). Under decision 13 alone, such a `NOCK_SMTP_USER`,
    `NOCK_SMTP_PASSWORD` or `NOCK_SMTP_FROM` passed the start, and then every
    sign-in link could fail with `MailError` (503, `account.error.send`).
    Options: (a) keep the rules of decision 13, and let the operator learn of the
    problem from the logged failure of the first link; (b) these variables also
    refuse every character outside ASCII, with their usual messages (the
    password's naming the variable only), so that the start stops on them. Pick:
    (b), since `SettingsError` is for a value the server cannot use (spec 038).
    The open question named the user and the password; the sender gets the same
    rule for the same reason. With the set of decision 13, the three take only
    the printable ASCII characters, U+0020 SPACE to U+007E TILDE; U+200C and
    U+200D, outside ASCII, are refused too.

Decided by the lead on 2026-10-21, answering open question 2 of 2026-10-16 with
the recommended option, under the human's rule of 2026-10-16 ("Make things simple
from a backend perspective, don't generate edge cases by making things
complicated"). Already part of the spec above. (Note from the lead, 2026-10-21:
this group was added; its item was open question 2.)

15. Players' addresses in ASCII (former open question 2 of 2026-10-16; AC-1, AC-7,
    AC-8). `normalize_email` accepted a local part with characters outside ASCII,
    such as `"fran\u00e7ois@example.org"` (its domain was already ASCII only).
    Sending a link to such an address needs the SMTP server's SMTPUTF8 extension
    (`send_message`, line 970 of CPython 3.14's `smtplib.py`); without it,
    `send_message` raises `SMTPNotSupportedError`, the mailer raises `MailError`,
    and the player gets 503 and `account.error.send`, which asks them to try again
    later, at every try. This is this spec's design for what players type, not a
    technical variable. Options: (a) keep `normalize_email` as it was: such an
    address works when the server offers SMTPUTF8, and fails at each request
    otherwise; (b) `normalize_email` also refuses a local part outside ASCII: 422
    and `account.error.email`; (c) keep accepting it, and answer a request that the
    server cannot send for lack of SMTPUTF8 with its own status and text (a new
    `fr.json` key) saying that this address cannot receive the link. Pick: (b),
    because the answer is the same on every server and is tested without one, and
    such addresses are rare; (c) serves those few players better, but adds a
    mailer error, an answer and a text. What it changed: the docstring of
    `normalize_email` (each character of the local part is printable ASCII other
    than the space), AC-8 (`"fran\u00e7ois@example.org"` refused, 422), the
    wording of AC-6 on `NOCK_SMTP_FROM`, and notes in decision 14.

    (Note from the lead, 2026-10-21, first review of spec 033: the local part of an
    address now takes only RFC 5322's `atext` characters (ASCII letters, digits and
    `` !#$%&'*+-/=?^_`{|}~ ``) and `.`; "printable ASCII other than the space" above
    is the rule it replaces. Why: the review found that `,`, `<`, `>` and `"` in the
    local part get around AC-8's limit of 3 links per address. With the test SMTP
    server, `x1,victim@example.org` and `x2,victim@example.org` counted as two
    addresses yet both reached `victim@example.org`, and `a"b<victim@example.org`
    reached it with no comma at all. Decided by the lead, under the human's rule of
    2026-10-16 that heads this group. The spec has no rule on leading, trailing or
    doubled dots in the local part, and none is added. `+` sub-addressing
    (`ana+1@example.org` and `ana+2@example.org`) still reaches one mailbox under
    many addresses: no limit per address can stop that, and it is accepted. What it
    changed: the docstring of `normalize_email`, and AC-8, which gains
    `x1,victim@example.org`, `a<b@example.org` and `a"b@example.org` among its
    refused addresses.)

Decided by the lead on 2026-10-21, under the human's rule of 2026-10-16: "Make
things simple from a backend perspective, don't generate edge cases by making
things complicated. We are here to work on a core Arrow Crossword game. The core is
the game engine not all the rest." Already part of the spec above. (Note from the
lead, 2026-10-21: this group was added.)

16. Cuts. Accounts are peripheral to the game, so each rule below, which added a
    backend edge case with no need that a player would notice, is cut:
    - An IPv6 address in `NOCK_PUBLIC_URL` (`http://[::1]:8000`): the brackets
      needed a parse of their own, and a deployment's public URL holds a name. Its
      host is now a name or an IPv4 address. `NOCK_SMTP_HOST` keeps spec 036's
      rule, IPv6 included, since it reuses `NOCK_HOST`'s check as it is.
    - Ending, at sign-in, the session that the request carried: the new cookie
      replaces the old one in the browser, and the old session goes at the first
      sweep after its 90 days.
    - `AccountStore.forget_rooms` and its call after each sweep: `expire_rooms()`
      returns only the rooms that the sweep deletes, not those that a lookup
      deletes (spec 032), so it missed some; and an identity of a deleted room
      whose code a new room drew was served. The identities served are now those
      whose token is a member's of their room, which covers both, and an identity
      of a deleted room stays until its account is deleted, as spec 029's history
      of a deleted room does.
    - The used state of a sign-in link: `use_link` deletes the link.
    - The identity kept in a link: a link keeps the request's `RoomKey`, and the
      sign-in links the member as `PUT /api/account/rooms` does, one path instead
      of two.
    - The length limits of `SignInLinkRequest.email`: `normalize_email` already
      limits the length, and FastAPI's validation body repeated the address.
    - The account store while accounts are off: the app opens none.
    - A room page's `PUT /api/account/rooms` after a later snapshot whose `you`
      differs: a page's player id changes only when its token matched nobody
      (spec 012, "Unknown resume token"), and the next page load links the new id.

    Kept, although they are backend rules: the two limits of decision 11, which are
    the human's thresholds against a flooded mailbox; several identities of one
    account in a room, so that the erasure reaches every player of the account
    (spec 029 reads them too); and the erasure in the log, for the backlog's
    "former player" in the recaps (AC-9.2.3).

## Open questions

(Note from the lead, 2026-10-21: no question is open. Open question 1 of 2026-10-16,
on SMTP logins outside ASCII, was answered with option (b) on 2026-10-16 and is
decision 14. Open question 2 of 2026-10-16, on players' addresses outside ASCII, was
answered with option (b) on 2026-10-21 and is decision 15. Before those questions,
this section said "None.")
