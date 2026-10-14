---
id: "033"
title: Optional account
status: approved
---

# 033 - Optional account

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

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
  `SESSION_LIFE_SECONDS` (90 days). It is the only cookie of the app, and only a
  signed-in player has it (spec 038 AC-2).
- **Identity of an account in a room**: the room code, player id, resume token and
  nickname of a member (spec 032) that the account linked. A room can have several
  (one per player id); "the account's identity" of a room is the latest one linked.
- **Former player**: the player of an identity of a deleted account. The server
  replaces their nickname with `FORMER_PLAYER_NICKNAME` (`--`), which no real
  nickname can be (spec 012 needs a letter or a digit), and the client shows
  `t("player.former")` (`Ancien joueur`) for it.
- **Accounts on**: `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both set, or the app
  was given `AccountSettings`. Accounts off: every account route and page answers 404
  and the client shows no account control.

### Configuration

| Variable | Default | Valid values | Any other value |
| --- | --- | --- | --- |
| `NOCK_PUBLIC_URL` | unset or empty: accounts off | `http://` or `https://`, a host, and optionally `:` and a port; nothing else (no user, no path other than one trailing `/`, which is dropped, no query, no fragment). The links of the e-mails start with it; it is never taken from a request's `Host` header | `SettingsError` naming `NOCK_PUBLIC_URL` and the value |
| `NOCK_SMTP_HOST` | unset or empty: accounts off | a host name or address, without spaces | `SettingsError` naming the variable and the value |
| `NOCK_SMTP_PORT` | `587` with `starttls`, `465` with `tls`, `25` with `none` | ASCII digits only, 1 to 65535 (as spec 036's `NOCK_PORT`) | `SettingsError` naming the variable and the value |
| `NOCK_SMTP_SECURITY` | `starttls` | exactly `starttls`, `tls` or `none` | `SettingsError` naming the variable and the value |
| `NOCK_SMTP_USER` | unset: no login | any non-empty text | — |
| `NOCK_SMTP_PASSWORD` | unset: no login | any non-empty text; a secret | `SettingsError` naming the variable, never the value, when it is set without `NOCK_SMTP_USER`, or with `NOCK_SMTP_SECURITY=none` |
| `NOCK_SMTP_FROM` | none | an address that `normalize_email` accepts; required when accounts are on | `SettingsError` naming the variable and the value |

- An empty value counts as unset, as in spec 036. `NOCK_SMTP_USER` set without
  `NOCK_SMTP_PASSWORD` is a `SettingsError` naming the missing one.
- Exactly one of `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` set is a `SettingsError`
  naming the missing one. With accounts off, the other `NOCK_SMTP_*` variables are
  not read.
- `main()` (spec 036, as spec 038 extends it) also calls
  `account_settings_from_env(os.environ)` before it builds a server; a
  `SettingsError` becomes `SystemExit(str(error))`, so `python -m nock` prints it and
  exits with status 1. An app built otherwise reads the same variables when it
  starts and fails its startup with the same error.
- Secrets: the SMTP password, the link tokens, the session tokens and the resume
  tokens are never written to a log, an error message or a `repr`; nor are e-mail
  addresses.

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

Spec 005's server scan (AC-4) forbids `smtplib` and `ssl` in every `.py` file under
`src/`, and the human asked on 2026-10-14 to send the sign-in link with `smtplib`.
Before this spec's tests run, the lead refines spec 005 so that its scan allows
`smtplib` and `ssl` in `src/nock/mailer.py` only (sending mail is not fetching
grids), and keeps flagging them in every other file. No other module of this spec
opens a connection.

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
    """A message could not be sent. Its text holds no password, token or address."""


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

### `nock.accounts` (new)

```python
# src/nock/accounts.py
SESSION_COOKIE: str = "nock_session"
LINK_LIFE_SECONDS: float = 1_800.0  # 30 minutes (proposed, open question 1)
SESSION_LIFE_SECONDS: float = 7_776_000.0  # 90 days (proposed, open question 1)
LINKS_PER_EMAIL_PER_HOUR: int = 3  # proposed, open question 1
LINKS_PER_ADDRESS_PER_HOUR: int = 10  # proposed, open question 1
EMAIL_MAX_LENGTH: int = 254


def normalize_email(text: str) -> str:
    """Return the address as stored: `strip()`ped, then lower-cased.

    Rules, on the result: at most EMAIL_MAX_LENGTH characters; exactly one `@`; a
    local part of 1 to 64 characters with no whitespace or control character; a
    domain of two or more labels separated by `.`, each 1 to 63 ASCII letters,
    digits and hyphens, not starting or ending with a hyphen.

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

    email: str = Field(min_length=1, max_length=320)  # then checked by normalize_email
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
    room: RoomIdentity | None


class SessionStart(AccountModel):
    account_id: str
    session: str  # the raw cookie value; only its SHA-256 is stored


class AccountStore:
    """Accounts on disk, in the database file of the rooms (NOCK_DATABASE).

    A plain class (a service). Safe to call from several threads. It uses its own
    connection, journal_mode WAL, synchronous FULL and secure_delete ON, like
    RoomStore (specs 018, 038). Link and session tokens are stored as their SHA-256
    only; addresses and identities are stored as given.
    """

    def __init__(self, path: str | Path) -> None: ...

    def add_link(self, email: str, room: RoomIdentity | None, now: float) -> str:
        """Record a sign-in link for `email` (normalised by the caller) and the
        identity to link with it; return its raw token."""

    def use_link(self, token: str, now: float) -> LinkUse | None:
        """Mark the link used and return it; None when the token is unknown, used,
        or older than LINK_LIFE_SECONDS."""

    def sign_in(self, email: str, now: float) -> SessionStart:
        """Create the account of `email` when there is none, then a session."""

    def account_of_session(self, session: str, now: float) -> Account | None:
        """The account of a session that exists and is not older than
        SESSION_LIFE_SECONDS; None otherwise."""

    def end_session(self, session: str) -> None: ...

    def link_identity(self, account_id: str, identity: RoomIdentity, now: float) -> None:
        """Link an identity to the account; linking the same player again updates
        its token and nickname and makes it the newest."""

    def identities(self, account_id: str) -> list[RoomIdentity]:
        """The account's identity of each of its rooms (the latest linked per
        room), newest link first."""

    def delete_account(self, account_id: str) -> list[RoomIdentity]:
        """Delete the account, its sessions, its identities and every sign-in link
        of its address; return every identity it held (not only the latest)."""

    def forget_rooms(self, codes: Sequence[str]) -> None:
        """Delete the identities of those rooms (they expired, spec 032)."""

    def purge(self, now: float) -> None:
        """Delete the links older than LINK_LIFE_SECONDS and the sessions older than
        SESSION_LIFE_SECONDS."""

    def close(self) -> None:
        """Close the database. Idempotent."""
```

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
        checkpoint the WAL (spec 038). Seqs, order and everything else stay.

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
        nickname. Returns once it is done; False when the room is unknown.
        """
```

This is the second exception to spec 018's "the log is never rewritten" (the first
is spec 032's deletion at expiry): privacy erasure rewrites the nickname in place.

### HTTP routes

All account answers carry `Cache-Control: no-store`. "Session" below is the account
of the request's `nock_session` cookie (`account_of_session`). A refusal for lack of
a session is 401 with `{"detail": "Not authorized"}`.

| Method and path | Answer |
| --- | --- |
| any route below, or `GET /account`, accounts off | 404, `{"detail": "Not Found"}` |
| `GET /account` | `index.html` (503 when the client is not built), as `/r/{code}` |
| `GET /api/account` | 200, `AccountStatus`: signed in with the session's address, or `{"signed_in": false, "email": null}` |
| `POST /api/account/link`, body `SignInLinkRequest` | 202 with `{}`, after `sign_in_message` was sent to `normalize_email(email)`; the answer is the same whether the address has an account |
| the same, `normalize_email` refuses the address | 422, `{"detail": "Invalid e-mail address"}`, which does not repeat the address |
| the same, `room` given and its token is no member's of that room (spec 032 `member_id`) | 404 |
| the same, `LINKS_PER_EMAIL_PER_HOUR` links already asked for that address, or `LINKS_PER_ADDRESS_PER_HOUR` from that client address, in the last 3,600 seconds of `rooms.clock` | 429, `{"detail": "Too Many Requests"}`, nothing sent; this refusal is not counted |
| the same, the mailer raises `MailError` | 503, `{"detail": "Mail not sent"}`; the failure is logged without secret or address |
| `POST /api/account/sign-in`, body `SignInRequest` | 200, `SignInResult`, with `Set-Cookie: nock_session=<session>; HttpOnly; Max-Age=7776000; Path=/; SameSite=Lax`, plus `; Secure` when the public URL starts with `https://`; a session the request carried is ended first |
| the same, the link is unknown, used or expired | 404 |
| `POST /api/account/sign-out` | 204, the session ended (if any) and `Set-Cookie: nock_session=""; Max-Age=0; Path=/` |
| `GET /api/account/rooms` | 200, JSON array of `RoomIdentity`: `identities(account)` of the rooms that still exist; 401 without a session |
| `PUT /api/account/rooms`, body `RoomKey` | 204 after `link_identity` of that member (player id and nickname from the room); 404 when the token is no member's; 401 without a session |
| `DELETE /api/account` | 204 after the erasure below, with the cookie cleared as for sign-out; 401 without a session |

Sign-in, in order: `use_link(token)`; `sign_in(email)`; when the link carries a room
identity whose room still exists and whose token is still a member's,
`link_identity`, and `room_code` is that room's code (else `room_code` is None);
`rooms` is then `identities(account)` of the rooms that still exist.

Erasure (`DELETE /api/account`), before answering:

1. `delete_account(account_id)` removes the address, the sessions, the identities and
   the address's unused links, and returns every identity the account held; nothing
   else of the account is kept.
2. For each of those identities whose room exists,
   `rooms.erase_player(code, player_id)`.

So no copy of the address or of those nicknames stays in the database files (spec
038's `secure_delete` and checkpoints), at once, well within the 30 days of the
backlog.

The app (spec 032's sweep) also calls `account_store.forget_rooms(<deleted codes>)`
after each `expire_rooms()`, and `account_store.purge(now)`, every sweep.

`create_app` (changes):

```python
def create_app(
    rooms: RoomRegistry | None = None,
    dist_dir: Path | None = None,
    catalogue: Catalogue | None = None,
    *,
    operator_token: str | None = None,  # spec 038
    accounts: AccountSettings | None = None,  # None: account_settings_from_env(os.environ) at startup
    account_store: AccountStore | None = None,  # None: AccountStore(NOCK_DATABASE, ":memory:" when unset), opened at startup, closed at stop
    mailer: Mailer | None = None,  # None: SmtpMailer(accounts.smtp)
) -> FastAPI: ...
```

A store or mailer given is never closed by the app. Times come from `rooms.clock`.

### Client

Accounts on or off: the room page, the catalogue page and the account page ask
`GET /api/account` once when they load; a 404 means off, and then no account
control is shown.

Room page (once `data-status="joined"`, accounts on):

- `data-testid="account-open"`: a `<button type="button">` with the text
  `t("account.open")`, the last control of spec 024's `room-toolbar` (after the
  controls that specs 019 to 028 put there). Spec 024's toolbar rules apply to it:
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
  `t("account.sent", {email})`; 422 shows `data-testid="account-error"`
  (`role="alert"`) with `t("account.error.email")`; 429 with
  `t("account.error.too_many")`; anything else with `t("account.error.send")`.
- Signed in, it shows `t("account.signed_in_heading")`,
  `t("account.signed_in_as", {email})` and a link
  `data-testid="account-page-link"` to `/account` (`t("account.manage")`).
- A signed-in page sends `PUT /api/account/rooms` with its code and
  `snapshot.resume_token` after the first snapshot of a page load, and after each
  later snapshot whose `you` differs; its answer changes nothing on the page.

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

Former players, everywhere a nickname is shown (the roster's `roster-nickname`, the
`host.remove_label` of spec 014, the feed's `{name}` of specs 013 and 034, "My rooms"
of spec 032, the recap dialog of spec 028, the ops replay of spec 038, and the other
views of specs 019 to 029 that name a player): a nickname equal to `--` is shown as
`t("player.former")`.

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
- Browser with live server: the test module starts its own server as spec 040's
  `live_server` does (built client, free port of 127.0.0.1), with
  `create_app(rooms=room_registry, dist_dir=WEB_DIST_DIR, catalogue=..., accounts=AccountSettings(public_url=<its base URL>, smtp=SETTINGS.smtp), account_store=AccountStore(path), mailer=recorder)`.
  Devices are browser contexts (separate storage and cookies).
- Browser with mocked routes (AC-9): spec 040's mocked socket, plus
  `page.route("**/api/account", ...)` answering `{"signed_in": false, "email": null}`
  (or signed in) and `page.route("**/api/account/link", ...)`; the window sizes of
  spec 006 AC-5 in desktop and touch contexts as in spec 013 AC-6 (spec 009's touch
  harness).
- Logs (AC-10): `caplog` at level `DEBUG` for every logger, records formatted with
  `record.getMessage()`.
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check of
  this spec is Chromium-only (`<dialog>`, cookies and `history.replaceState` work in
  all three).

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-9.2.1) (HTTP) A guest in a room asks for a sign-in link by e-mail, and using it creates the account without changing their player. `Ana` (token `TA`, colour 0, host) and `Bob` join a FX-01 room and Ana writes `T` at (1, 0). `POST /api/account/link` with `{"email": "  Ana.Probe@Example.org ", "room": {"code": <code>, "resume_token": TA}}` answers 202 with `{}`, and the recorder holds one message with `To` `ana.probe@example.org`, `From` `nock@example.org`, `Subject` `fr.json["email.sign_in.subject"]`, and a body equal to `fr.json["email.sign_in.body"]` with `{link}` replaced by `http://testserver/account#<token>`, the token being 43 characters of `A-Za-z0-9_-`. `POST /api/account/sign-in` with that token answers 200 with `{"email": "ana.probe@example.org", "room_code": <code>, "rooms": [{"code": <code>, "player_id": <Ana>, "resume_token": TA, "nickname": "Ana"}]}` and a `set-cookie` header for `nock_session` with `HttpOnly`, `Max-Age=7776000`, `Path=/` and `SameSite=Lax`, and without `Secure`; then `GET /api/account` answers `{"signed_in": true, "email": "ana.probe@example.org"}`. The room's `players`, `seq`, cells and log are the same as before the link was asked: Ana keeps her id, nickname, colour, host role and `joined_seq`, (1, 0) keeps `T` authored by her, and nothing was sent on the sockets. Using the token again answers 404; a second link used 1,801 seconds of the fake clock after it was asked answers 404, and one used 1,799 seconds after answers 200. With `public_url` `https://nock.example`, the cookie also has `Secure`.
- **AC-2** (AC-9.2.1) (browser with live server) From inside a room, a guest creates an account and keeps the same seat, colour and authorship, also on a second device. Device 1 (context 1) enters a FX-01 room as `Ana` and types `T` at (1, 0); she clicks `account-open`, `account-dialog` opens with the focus on `account-email-input`, she types `ana.probe@example.org` and submits: `account-sent` reads `Lien envoyé à ana.probe@example.org. Il est valable 30 minutes.` and the recorder holds one message. A new page of context 1 opens the message's link: `account-page` reaches `data-state="signed_in"`, `account-email` reads `Connecté avec ana.probe@example.org`, the page's URL is `<base>/account` with no fragment, and `account-room-link` has `href="/r/<code>"`; Ana's room page is still `joined` with the same `data-you` and roster `data-colour` as before, and the server's cell (1, 0) is still authored by her `data-you`. Device 2 (context 2, empty storage) opens `/account`, which shows `signed_out`, asks for a link with the same address and opens the new link: `signed_in`, and `localStorage["nock.identity.<code>"]` of context 2 holds Ana's player id and token. Device 2 then opens `/r/<code>`: its room page reaches `data-status="joined"` with the same `data-you` as device 1, without `nickname-form`, its roster lists `Ana` with the same `data-colour`, and device 1's room page reaches `data-status="replaced"` (spec 012).
- **AC-3** (AC-9.2.2) (browser with live server) No action needed to finish a grid requires an account. With accounts on, a page in a fresh context (no cookie, no storage) opens the room link of a FX-01 room, enters as `Ana`, types the 18 letters word by word with `X` in place of `I` at (2, 2), 60 ms or more between keys (spec 037's harness), selects the word `MIME` and presses `check-word` (spec 023), types `I` at (2, 2), and reaches `data-solved="true"` with `grid-status` `solved` (spec 026). No response of the page had status 401 or 403, none had a `set-cookie` header, `context.cookies()` is empty, `account-dialog` never had the `open` attribute, and every frame the page sent parses with `parse_client_message` (spec 039 has no account field).
- **AC-4** (AC-9.2.3) (HTTP) Deleting my account removes my personal data at once. `Bob` then `Zélie-Probe` (token `TZ`) join room R, so Bob is host; Zélie writes `T` at (1, 0), asks a link from R with `zelie.probe@example.org` and signs in; she also joined room S, linked it with `PUT /api/account/rooms`, and timed out there (a past player of S, spec 032); she asks one more link and leaves it unused. `DELETE /api/account` answers 204 and clears `nock_session` (`Max-Age=0`). Then `GET /api/account` with the old cookie answers `{"signed_in": false, "email": null}`, `GET /api/account/rooms` answers 401, and the unused link answers 404. In R, Zélie's record keeps its player id and colour with the nickname `--`, (1, 0) keeps `T` authored by her id, the log holds her `player_joined` with nickname `--` at the same seq, and a new client joining R gets a snapshot whose view of her has the nickname `--`; in S her past record has the nickname `--`. The database files then hold neither `zelie.probe@example.org` nor `Zélie-Probe` (UTF-8), and still hold `Bob`.
- **AC-5** (AC-9.2.3) (browser with live server) Other players then see "former player". In the play of AC-4 on the live server, Zélie deletes her account from `/account`: `account-delete` shows `account-delete-warning`, `account-delete-confirm` sends the deletion, and the page reaches `data-state="deleted"` with `fr.json["account.deleted"]`; `account-delete-cancel` instead keeps the account (a `GET /api/account` still says signed in). Bob's page in R (he is host), reloaded, shows Zélie's `roster-nickname` as `Ancien joueur` and her `remove-player` with the `aria-label` `Retirer Ancien joueur du salon`, and, after Zélie (still in the room as a guest) checks a word, the feed line `Ancien joueur a vérifié un mot`; on `/`, Bob's "My rooms" item of R reads `Joueurs : Bob, Ancien joueur`; and once R is solved, spec 028's recap names her `Ancien joueur`. No page shows `--`.
- **AC-6** (new) (Python, `uvicorn.Server.run` replaced) Accounts are configured by environment variables, and an invalid value stops the start. `account_settings_from_env` gives None for `{}` and when `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both empty; with `NOCK_PUBLIC_URL="https://nock.example/"`, `NOCK_SMTP_HOST="smtp.example"` and `NOCK_SMTP_FROM="nock@nock.example"` it gives `AccountSettings(public_url="https://nock.example", smtp=SmtpSettings(host="smtp.example", port=587, security="starttls", user=None, password=None, sender="nock@nock.example"))`; `NOCK_SMTP_SECURITY` `tls` and `none` give the ports 465 and 25, and `NOCK_SMTP_PORT="2525"` gives 2525. Each of these raises `SettingsError` whose message names the variable: `NOCK_PUBLIC_URL` of `nock.example`, `ftp://nock.example`, `https://nock.example/app`, `https://nock.example?x=1`, `https://u@nock.example` or `https://`; only one of `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` set (the message names the missing one); `NOCK_SMTP_SECURITY="STARTTLS"`; `NOCK_SMTP_PORT` of `abc`, `0`, `65536` or ` 587`; a missing or invalid `NOCK_SMTP_FROM`; `NOCK_SMTP_USER` without `NOCK_SMTP_PASSWORD`, and the reverse; `NOCK_SMTP_PASSWORD="pw-SECRET-9"` with `NOCK_SMTP_SECURITY=none`. No message holds `pw-SECRET-9`, nor does `repr` of the settings when the password is valid. `main()` with an invalid variable raises `SystemExit` whose `code` is a `str` naming it and never calls `run`.
- **AC-7** (new) (Python with a test SMTP server; Python with smtplib replaced; HTTP) The sign-in link is sent with the standard library, over a checked TLS connection. With the test SMTP server and `security="none"`, `SmtpMailer(...).send(sign_in_message(SETTINGS, "ana.probe@example.org", <43-character token>))` delivers one message: envelope from `nock@example.org` to `ana.probe@example.org`; parsed with `email.message_from_bytes(data, policy=email.policy.default)`, its subject is `fr.json["email.sign_in.subject"]`, its content type `text/plain` with charset `utf-8`, and its body holds `http://testserver/account#<token>`. With smtplib replaced: `starttls` makes `SMTP("smtp.example", 587, timeout=10)`, then `starttls(context=c)` with `c.verify_mode == ssl.CERT_REQUIRED` and `c.check_hostname is True`, then `login("nock", <password>)` when a user is set, `send_message` and `quit`; `tls` makes `SMTP_SSL("smtp.example", 465, context=c, timeout=10)` with the same checks. A server answering `550` to `RCPT` makes `send` raise `MailError`; through the app, the link request then answers 503 with `{"detail": "Mail not sent"}`.
- **AC-8** (new) (HTTP) Link requests reveal nothing and cannot flood a mailbox. The answer to a link request is the same 202 `{}` for an address that has an account and one that has none. `POST /api/account/link` with `email` `""`, `ana`, `ana@`, `@example.org`, `ana@example`, `ana @example.org` or 255 characters answers 422, sends nothing, and its body does not hold the address sent. With a `room` whose token is no member's, it answers 404 and sends nothing. Three requests for one address within an hour of the fake clock are sent; the fourth answers 429 and sends nothing; after `advance(3600)` one is sent again. From one client address, ten requests for ten addresses are sent and the eleventh answers 429. With accounts off, `GET /account`, `GET /api/account`, `POST /api/account/link` and `DELETE /api/account` answer 404.
- **AC-9** (new) (browser with mocked socket and routes; keyboard only for the walk) The account controls meet spec 035 and keep the room page's layout. With accounts on (mocked `GET /api/account`) and a FX-01 snapshot, at each window size of spec 006 AC-5, in desktop and touch contexts: `account-open` is the last control inside `room-toolbar`; at 320 by 568, 568 by 320, 360 by 740 and 740 by 360 its vertical range overlaps those of the toolbar's other buttons (spec 024's one-row rule), and after `account-open` is scrolled into view (as a keyboard focus does) it is visible whole inside the toolbar; and spec 013 AC-6's checks pass (after a tap on a cell, `grid-viewport` at least 100 px high, no page scroll, the grid fits at zoom 1, the clue bar inside the window above the keyboard). Keyboard only: `tab_to` reaches `account-open`, which shows spec 035 AC-2's outline; `Enter` opens `account-dialog` with the focus on `account-email-input`; during 10 presses of `Tab`, then 10 of `Shift+Tab`, no element outside `account-dialog` gets the focus (the rest of the page is inert while it is open; the browser may move the focus to its own interface, as spec 035 "Nothing focusable after the grid" describes); `Escape` closes it and the focus is back on `account-open`. Spec 035's contrast and language scans find no offending element at 1280 by 720 and 360 by 740 on the room page with the dialog open, then showing `account-sent`, then showing `account-error`, and on `/account` in the states `signed_out`, `signed_in`, `link_invalid` and `deleted` (mocked answers); `/account` has no horizontal scroll at the sizes of spec 006 AC-5.
- **AC-10** (new) (HTTP with captured logs) Secrets and addresses never reach a log, and tokens are stored hashed. With `SETTINGS` given the user `nock` and the password `pw-SECRET-9`, during a link request, a sign-in, `GET /api/account`, a `PUT /api/account/rooms`, a sign-out, a link request that fails with the failing mailer, and a deletion, no log record (formatted) holds the link token, the session cookie's value, `TA`, the address `ana.probe@example.org`, or the SMTP password `pw-SECRET-9`. After the sign-in, the database files hold the address but neither the link token nor the session value (their SHA-256 hex digests are stored instead).
- **AC-11** (new) (HTTP; browser with live server) A signed-in device gets the rooms of the account. HTTP: after Ana's sign-in of AC-1, `GET /api/account/rooms` answers `[{"code": R, "player_id": <Ana>, "resume_token": TA, "nickname": "Ana"}]`; after she joins room S as a new player (token `TA2`) and sends `PUT /api/account/rooms` with S and `TA2` (204), it lists S then R; a `PUT` with a token that is no member's of S answers 404, and one without the cookie 401; once R expires (spec 032), the list holds S only. Browser: device 2 of AC-2, once signed in, opens `/`: its "My rooms" (spec 032) lists Ana's room, and `account-link` points to `/account`; a signed-in room page sends one `PUT /api/account/rooms` with its code and token after its first snapshot.

## Edge cases and errors

- Address case (AC-1): stored lower-cased and trimmed; `Ana.Probe@Example.org` and
  `ana.probe@example.org` are one account.
- Link on another device (AC-2): the link signs in the device that opens it, wherever
  it was asked; a mail scanner that fetches the link gets `index.html` only, since the
  token is in the fragment and is used by the page's `POST`.
- Signed in elsewhere (AC-2): opening the room on device 2 resumes Ana's player while
  her resume window lasts (spec 017); device 1 shows `replaced`. After a time-out the
  identity no longer resumes (spec 032, open question 1).
- An existing account (AC-1): a link for an address that has an account signs in to
  it and links the room's identity to it.
- Room gone or player gone before the link is used (AC-1): the account is created or
  signed in, and no identity is linked (`room_code` None).
- A second sign-in on a device (AC-1): the session the request carried ends.
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
- Header row (AC-9): the button must never add a row to the header; spec 013 AC-6's
  floor of 100 px left 3 px at 568 by 320 before spec 024's toolbar. It goes into
  that toolbar, whose sideways scroll and edge fade (`room-toolbar-more`) show that
  more controls follow.
- Accounts turned off later (AC-8): the account rows stay in the database, unused,
  until the account is deleted or accounts are turned on again; cookies are ignored.
- Former nickname on the server (AC-4): `--` passes spec 039's length check and fails
  spec 012's character rule, so no player can join with it.

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
- Getting a timed-out player back in a room (spec 032, open question 1).

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
   amendment of spec 005, see "Spec 005 amendment").
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

## Open questions

1. Proposed thresholds, none of which is in the backlog: a sign-in link lives 30
   minutes and works once; a session lives 90 days; at most 3 links per address and
   10 per client address per hour. Options: keep them (my pick), or set others; the
   texts `account.sent` and `email.sign_in.body` say "30 minutes" and change with it.
2. Spec 005's scan. This spec needs the lead to refine spec 005 (a `done` spec) so
   that `src/nock/mailer.py` may import `smtplib` and `ssl`. Options: (a) that one
   exception (my pick); (b) send mail from a separate process outside `src/`, which
   splits the server in two.
