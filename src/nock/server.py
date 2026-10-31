"""FastAPI app: serves the built web client, the room WebSocket and the recaps.

It also answers a member's catch-up request: what changed in a room while their
page was away (spec 034).

While the app runs, it deletes the expired rooms of the registry it serves once
when it starts, then every `expiry_sweep_seconds` (`lobby/lifetime.md` rule 6).

With an operator token, it also serves the operator pages (spec 038): the page
`/ops` and the ops API under `/api/ops/`, the dashboard and the replay of a room,
which only a request carrying the token reaches, and the routes that save the
overrides of the room lives (`admin/overrides.md`).

With account settings, it also serves the optional accounts (spec 033): the page
`/account` and the routes under `/api/account`, which sign a player in with a
link sent by e-mail and keep the rooms of their account. Before a room is
deleted, each account of the room keeps the record of its finished grid
(spec 029).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import re
import secrets
import threading
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Mapping,
)
from pathlib import Path
from typing import Annotated, Literal

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
)
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.datastructures import MutableHeaders
from starlette.requests import ClientDisconnect
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nock.accounts import (
    LINKS_PER_ADDRESS_PER_HOUR,
    LINKS_PER_EMAIL_PER_HOUR,
    SESSION_COOKIE,
    SESSION_LIFE_SECONDS,
    Account,
    AccountStatus,
    AccountStore,
    RoomIdentity,
    SignInLinkRequest,
    SignInRequest,
    SignInResult,
    normalize_email,
)
from nock.catalogue import (
    GRIDS_DIR,
    Catalogue,
    CatalogueEntry,
    load_catalogue,
    summarize,
)
from nock.catch_up import CatchUpRequest
from nock.hub import (
    MAX_FRAME_BYTES,
    ROOM_NOT_FOUND_CLOSE_CODE,
    SESSION_REPLACED_CLOSE_CODE,
    SILENCE_CLOSE_CODE,
    RoomConnection,
    RoomRegistry,
)
from nock.mailer import Mailer, MailError, SmtpMailer, sign_in_message
from nock.operations import (
    DAY_SECONDS,
    RoomLog,
    RoomReplay,
    dashboard_figures,
    default_period,
    offered_periods,
    room_edits,
)
from nock.overrides import RoomLifeOverrides, SettingChange, settings_set_in
from nock.protocol import grid_view, parse_client_message
from nock.room import RoomKey, RoomState, RoomSummary
from nock.room import member_id as room_member_id
from nock.settings import (
    DEFAULT_ROOMS_PER_ADDRESS_PER_HOUR,
    DEFAULT_SOCKETS_PER_ADDRESS,
    OPERATOR_TOKEN_VARIABLE,
    AccountSettings,
    account_settings_from_env,
    operator_token_from_env,
    room_config_from_env,
    rooms_per_address_per_hour_from_env,
    sockets_per_address_from_env,
)
from nock.store import RoomStore

__all__ = [
    "ROOM_NOT_FOUND_CLOSE_CODE",
    "SESSION_REPLACED_CLOSE_CODE",
    "SILENCE_CLOSE_CODE",
    "WS_MAX_SIZE_BYTES",
    "RoomRegistry",
    "create_app",
    "server_config",
]

logger = logging.getLogger(__name__)

WEB_DIST_DIR: Path = Path(__file__).resolve().parents[2] / "web" / "dist"
ROOM_CODE_PATTERN: str = r"^[A-Z0-9]{6}$"
GRID_NUMBER_PATTERN: str = r"^[1-9][0-9]{0,8}$"
FORCE_PATTERN: str = r"^[1-4]$"
MAX_SUMMARY_KEYS: int = 100  # spec 032: keys in one POST /api/rooms/summaries
THROTTLED_CLOSE_CODE: int = 4429  # WebSocket close code, too many wrong codes
TOO_MANY_SOCKETS_CLOSE_CODE: int = 4503  # too many sockets open from the address
WRONG_CODE_LIMIT: int = 10
WRONG_CODE_WINDOW_SECONDS: float = 60.0
DATABASE_VARIABLE: str = "NOCK_DATABASE"  # path of the SQLite file (spec 018)
MEMORY_DATABASE: str = ":memory:"
WS_MAX_SIZE_BYTES: int = 8192  # spec 036: uvicorn refuses larger frames (close 1009)
OPS_API_ROOT: str = "/api/ops"  # spec 038: hidden too while the pages are off
OPS_API_PREFIX: str = "/api/ops/"  # spec 038: the paths of the ops API
BEARER_SCHEME: str = "bearer"  # spec 038: the scheme of the token, in any case
MAX_BODY_BYTES: int = 65_536  # `platform/serving.md` rule 11: a request body's size
CONTENT_TOO_LARGE_DETAIL: str = "Content Too Large"
# `platform/serving.md` rule 12: sent with every HTTP answer of the app.
SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
# `platform/serving.md` rule 13: the Cache-Control of the client's files.
NOT_KEPT_WITHOUT_ASKING: dict[str, str] = {"Cache-Control": "no-cache"}
KEPT_FOR_A_YEAR: dict[str, str] = {
    "Cache-Control": "public, max-age=31536000, immutable"
}
NO_STORE: str = "no-store"  # spec 038: the Cache-Control of every ops API answer
ACCOUNT_PAGE_PATH: str = "/account"  # spec 033: hidden too while accounts are off
ACCOUNT_API_ROOT: str = "/api/account"  # spec 033: its routes are under it
ACCOUNT_API_PREFIX: str = "/api/account/"
LINK_LIMIT_WINDOW_SECONDS: float = 3_600.0  # spec 033: the limits count an hour

# The ?days= of the dashboard as written in the URL: exactly 1, 7 or 30 (spec 038).
DashboardDays = Literal["1", "7", "30"]

_MISSING_BUILD_TEXT = "The web client is not built: run npm --prefix web run build"


class CreateRoomRequest(BaseModel):
    """The body of POST /api/rooms."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    grid_number: int = Field(ge=1, strict=True)  # a catalogue number (spec 004)


class CreateRoomResponse(BaseModel):
    """The answer of POST /api/rooms: never any grid data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str  # matches ROOM_CODE_PATTERN
    share_url: str  # absolute: <scheme>://<host>/r/<code>


class RoomSummariesRequest(BaseModel):
    """The body of POST /api/rooms/summaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rooms: tuple[RoomKey, ...] = Field(max_length=MAX_SUMMARY_KEYS)


class _WrongCodeThrottle:
    """The failures of each client address, kept in memory by one app.

    An app has two: one for the wrong room codes (spec 011; spec 028's recap
    route shares it), one for the refused ops API requests (spec 038), each with
    its own count. An address is kept until WRONG_CODE_WINDOW_SECONDS after its
    last failure, and at most until the next failure recorded after that. Every
    method may be called from any thread: each one takes the lock.
    """

    def __init__(self) -> None:
        """Create a throttle that holds no failure."""
        self._lock = threading.Lock()
        self._failure_times: dict[str, list[float]] = {}

    def is_blocked(self, address: str, now: float) -> bool:
        """Tell whether `address` has too many failures in the window at `now`.

        Records and forgets nothing.

        Args:
            address: The client's address.
            now: Clock time of the request.

        Returns:
            True when `address` has at least WRONG_CODE_LIMIT failures whose
            time `t` satisfies `t > now - WRONG_CODE_WINDOW_SECONDS`.
        """
        with self._lock:
            recent = self._recent_failures(address, now)
            return len(recent) >= WRONG_CODE_LIMIT

    def record_unless_blocked(self, address: str, now: float) -> bool:
        """Record one failure of `address` at time `now`, unless it is blocked.

        The check and the record are one step under the lock, so failures that
        arrive at once are counted one after another (spec 011): of a burst,
        exactly the first WRONG_CODE_LIMIT are recorded, however long the
        lookups before them took. Before it records, the throttle forgets every
        address whose failures are all outside the window at `now`, so that an
        address that never comes back is not kept until the process stops.

        Args:
            address: The client's address.
            now: Clock time of the failure: a wrong code, or a wrong token.

        Returns:
            True when the failure is recorded: the client gets the answer of an
            unknown room, or of a missing token. False when the address is
            blocked: the client gets the throttle's answer, and nothing is
            recorded or forgotten.
        """
        with self._lock:
            recent = self._recent_failures(address, now)
            if len(recent) >= WRONG_CODE_LIMIT:
                return False
            self._forget_old_failures(now)
            recent.append(now)
            self._failure_times[address] = recent
            return True

    def held_addresses(self) -> frozenset[str]:
        """Return the addresses whose failures the throttle keeps.

        Records and forgets nothing.
        """
        with self._lock:
            return frozenset(self._failure_times)

    def _recent_failures(self, address: str, now: float) -> list[float]:
        """Return the failure times of `address` inside the window at `now`.

        The caller holds the lock.
        """
        recent: list[float] = []
        for failure_time in self._failure_times.get(address, []):
            if failure_time > now - WRONG_CODE_WINDOW_SECONDS:
                recent.append(failure_time)
        return recent

    def _forget_old_failures(self, now: float) -> None:
        """Keep, for every address, only its failures inside the window at `now`.

        An address left with no failure is forgotten. The caller holds the lock.
        """
        kept: dict[str, list[float]] = {}
        for address in self._failure_times:
            recent = self._recent_failures(address, now)
            if len(recent) > 0:
                kept[address] = recent
        self._failure_times = kept


class _RoomsHolder:
    """The registry an app serves: the one it was given, or one it creates.

    A registry created here opens its database on first use, which is when the
    app starts, and is closed with the app. A registry given is never closed.
    """

    def __init__(self, given: RoomRegistry | None) -> None:
        """Keep `given`, or None to create the registry on first use."""
        self._lock = threading.Lock()
        self._registry = given
        self._is_created_here = False
        # The settings whose variable was set, for a registry created here.
        self._settings_set: frozenset[str] | None = None

    def get(self) -> RoomRegistry:
        """Return the registry, creating it from the environment the first time.

        A registry created here has the room lives of the environment variables
        and the store of NOCK_DATABASE.

        Raises:
            SettingsError: a room life or the sweep interval breaks its rule. The
                database is not opened then.
        """
        with self._lock:
            if self._registry is None:
                config = room_config_from_env(os.environ)
                self._settings_set = settings_set_in(os.environ)
                self._registry = RoomRegistry(
                    config=config, store=RoomStore(_database_path())
                )
                self._is_created_here = True
            return self._registry

    def settings_set(self) -> frozenset[str] | None:
        """Return the settings whose variable was set when the registry was made.

        Returns:
            The setting names of `nock.overrides.settings_set_in`, for a registry
            created here; None for a registry given.

        Raises:
            RuntimeError: the holder has no registry yet, or it was closed. Call
                `get` first.
        """
        with self._lock:
            if self._registry is None:
                raise RuntimeError(
                    "The holder has no registry: call get() before settings_set()."
                )
            return self._settings_set

    def close_if_created(self) -> None:
        """Close the registry (and its store) when this holder created it.

        After it, the holder has no registry, so `settings_set` raises until `get`
        creates one again.
        """
        with self._lock:
            if self._registry is not None and self._is_created_here:
                self._registry.close()
                self._registry = None
                self._is_created_here = False
                self._settings_set = None


class _RunningOverrides:
    """The overrides of the registry an app serves, made when the app starts."""

    def __init__(self) -> None:
        """Create a holder with no overrides: the app has not started."""
        self._overrides: RoomLifeOverrides | None = None

    def start(
        self, registry: RoomRegistry, settings_set: frozenset[str] | None
    ) -> None:
        """Read the stored overrides of `registry` and apply them to its config.

        Args:
            registry: The registry the app serves.
            settings_set: See `RoomLifeOverrides`.
        """
        overrides = RoomLifeOverrides(registry, settings_set)
        overrides.load()
        self._overrides = overrides

    def stop(self) -> None:
        """Give the registry the environment values back, as the app stops."""
        if self._overrides is not None:
            self._overrides.unload()
        self._overrides = None

    def get(self) -> RoomLifeOverrides:
        """Return the overrides of the running app.

        Raises:
            RuntimeError: the app has not started.
        """
        if self._overrides is None:
            raise RuntimeError("The overrides are read when the app starts")
        return self._overrides


class _OperatorToken:
    """The operator token an app checks: the one it was given, or its variable.

    A token given follows the rule of NOCK_OPERATOR_TOKEN and is checked when
    the app is built. Without one, the variable is read each time the app
    starts (spec 038). While `token` is None, the operator pages are off.
    """

    def __init__(self, given: str | None) -> None:
        """Check the token given, or wait for the app's start to read the variable.

        Args:
            given: The `operator_token` of `create_app`. "" turns the operator
                pages off, as an empty variable does. None: read
                NOCK_OPERATOR_TOKEN when the app starts.

        Raises:
            SettingsError: `given` breaks the rule of NOCK_OPERATOR_TOKEN. The
                message never holds it.
        """
        self._reads_variable = given is None
        self.token: str | None = None
        if given is not None:
            # The token given goes through the variable's rule, as if it were
            # the variable's value: "" gives None, so the pages are off.
            self.token = operator_token_from_env({OPERATOR_TOKEN_VARIABLE: given})

    def read_at_start(self) -> None:
        """Take the token of NOCK_OPERATOR_TOKEN, unless a token was given.

        Raises:
            SettingsError: the variable breaks the rule of spec 038.
        """
        if self._reads_variable:
            self.token = operator_token_from_env(os.environ)


class _LinkLimits:
    """The two limits of the sign-in link requests, kept in memory (spec 033).

    Per normalised address and per client address, the times of the counted
    requests of the last hour. A key is kept until LINK_LIMIT_WINDOW_SECONDS
    after its last counted request, and at most until the next request counted
    after that. Every method may be called from any thread: each one takes the
    lock.
    """

    def __init__(self) -> None:
        """Create limits that hold no request."""
        self._lock = threading.Lock()
        self._times_per_email: dict[str, list[float]] = {}
        self._times_per_address: dict[str, list[float]] = {}

    def count_unless_reached(self, email: str, address: str, now: float) -> bool:
        """Count one request for `email` from `address`, unless a limit is reached.

        The check and the count are one step under the lock, so requests that
        arrive at once are counted one after another. Before it counts, each
        limit forgets the keys whose counted requests are all out of the hour.

        Args:
            email: The normalised address the link is for.
            address: The client's address.
            now: Clock time of the request.

        Returns:
            True when the request is counted, and its mail may be sent. False
            when LINKS_PER_EMAIL_PER_HOUR requests for `email`, or
            LINKS_PER_ADDRESS_PER_HOUR from `address`, have a time `t` with
            `t > now - 3600`: nothing is counted or forgotten then.
        """
        with self._lock:
            email_times = _times_in_window(self._times_per_email.get(email, []), now)
            address_times = _times_in_window(
                self._times_per_address.get(address, []), now
            )
            if len(email_times) >= LINKS_PER_EMAIL_PER_HOUR:
                return False
            if len(address_times) >= LINKS_PER_ADDRESS_PER_HOUR:
                return False
            self._times_per_email = _forget_old_times(self._times_per_email, now)
            self._times_per_address = _forget_old_times(self._times_per_address, now)
            email_times.append(now)
            address_times.append(now)
            self._times_per_email[email] = email_times
            self._times_per_address[address] = address_times
            return True


class _RoomCreationLimit:
    """The rooms each client address created in the last hour (`lobby/rooms.md`).

    Per address, the times of its counted creations. An address is kept until
    LINK_LIMIT_WINDOW_SECONDS after its last counted creation, and at most until
    the next creation counted after that. Every method may be called from any
    thread: each one takes the lock.
    """

    def __init__(self) -> None:
        """Create a limit that holds no creation, at the default number of rooms."""
        self._lock = threading.Lock()
        self._rooms_per_hour = DEFAULT_ROOMS_PER_ADDRESS_PER_HOUR
        self._times_per_address: dict[str, list[float]] = {}

    def read_at_start(self) -> None:
        """Take the number of rooms of NOCK_ROOMS_PER_ADDRESS_PER_HOUR.

        Raises:
            SettingsError: the variable breaks the rule of `lobby/rooms.md`
                rule 14.
        """
        rooms_per_hour = rooms_per_address_per_hour_from_env(os.environ)
        with self._lock:
            self._rooms_per_hour = rooms_per_hour

    def count_unless_reached(self, address: str, now: float) -> bool:
        """Count one creation by `address`, unless it reached the limit.

        The check and the count are one step under the lock, so creations that
        arrive at once are counted one after another. Before it counts, the
        limit forgets the addresses with no creation left in the hour.

        Args:
            address: The client's address.
            now: Clock time of the request.

        Returns:
            True when the creation is counted. False when the address has
            created as many rooms with a time `t > now - 3600` as the limit:
            nothing is counted or forgotten then.
        """
        with self._lock:
            recent = _times_in_window(self._times_per_address.get(address, []), now)
            if len(recent) >= self._rooms_per_hour:
                return False
            self._times_per_address = _forget_old_times(self._times_per_address, now)
            recent.append(now)
            self._times_per_address[address] = recent
            return True

    def forget_creation(self, address: str, now: float) -> None:
        """Take back the creation counted for `address` at `now`.

        For a creation that failed after it was counted: only a created room
        counts.
        """
        with self._lock:
            times = self._times_per_address.get(address, [])
            if now in times:
                times.remove(now)
            if len(times) == 0:
                self._times_per_address.pop(address, None)


class _OpenSocketCap:
    """The room sockets each client address holds open, kept in memory by one app.

    The cap is NOCK_SOCKETS_PER_ADDRESS (`platform/realtime.md` rule 26). An
    address is kept while it holds a socket. Every method may be called from any
    thread: each one takes the lock.
    """

    def __init__(self) -> None:
        """Create a cap that holds no socket, at the default number of sockets."""
        self._lock = threading.Lock()
        self._cap = DEFAULT_SOCKETS_PER_ADDRESS
        self._open_per_address: dict[str, int] = {}

    def read_at_start(self) -> None:
        """Take the number of sockets of NOCK_SOCKETS_PER_ADDRESS.

        Raises:
            SettingsError: the variable breaks the rule of `platform/realtime.md`
                rule 26.
        """
        cap = sockets_per_address_from_env(os.environ)
        with self._lock:
            self._cap = cap

    def count_unless_reached(self, address: str) -> bool:
        """Count one open socket for `address`, unless it reached the cap.

        The check and the count are one step under the lock, so sockets that
        arrive at once are counted one after another.

        Args:
            address: The client's address.

        Returns:
            True when the socket is counted. False when the address already
            holds as many open sockets as the cap: nothing is counted then.
        """
        with self._lock:
            open_count = self._open_per_address.get(address, 0)
            if open_count >= self._cap:
                return False
            self._open_per_address[address] = open_count + 1
            return True

    def release(self, address: str) -> None:
        """Take back the socket counted for `address`, whatever closed it."""
        with self._lock:
            open_count = self._open_per_address.get(address, 0)
            if open_count <= 1:
                self._open_per_address.pop(address, None)
            else:
                self._open_per_address[address] = open_count - 1


def _times_in_window(times: list[float], now: float) -> list[float]:
    """Return the times of `times` inside the hour that ends at `now`."""
    recent: list[float] = []
    for counted_at in times:
        if counted_at > now - LINK_LIMIT_WINDOW_SECONDS:
            recent.append(counted_at)
    return recent


def _forget_old_times(
    times_per_key: dict[str, list[float]], now: float
) -> dict[str, list[float]]:
    """Return the keys with their times inside the hour; a key with none goes."""
    kept: dict[str, list[float]] = {}
    for key, times in times_per_key.items():
        recent = _times_in_window(times, now)
        if len(recent) > 0:
            kept[key] = recent
    return kept


class _AccountService:
    """What an app's accounts run on: their settings, their store, their mailer.

    Settings given are used as they are. Without them, the variables of spec
    033 are read each time the app starts. While `settings` is None, accounts
    are off. A store or a mailer given is used and never closed; a store created
    here is opened when the app starts and closed when it stops.
    """

    def __init__(
        self,
        settings: AccountSettings | None,
        store: AccountStore | None,
        mailer: Mailer | None,
    ) -> None:
        """Keep what `create_app` was given; the rest is made at the start."""
        self._given_settings = settings
        self._given_store = store
        self._given_mailer = mailer
        self.settings: AccountSettings | None = None
        self.store: AccountStore | None = None
        self.mailer: Mailer | None = None
        self.limits = _LinkLimits()
        self._is_store_created_here = False

    def start(self) -> None:
        """Turn the accounts on or off, as the app starts.

        Raises:
            SettingsError: no settings were given, and a variable of spec 033
                breaks its rule.
        """
        settings = self._given_settings
        if settings is None:
            settings = account_settings_from_env(os.environ)
        self.settings = settings
        if settings is None:
            return
        self.mailer = self._given_mailer
        if self.mailer is None:
            self.mailer = SmtpMailer(settings.smtp)
        self.store = self._given_store
        if self.store is None:
            self.store = AccountStore(_database_path())
            self._is_store_created_here = True

    def stop(self) -> None:
        """Close the store when it was created at the start."""
        if self.store is not None and self._is_store_created_here:
            self.store.close()
        self.store = None
        self._is_store_created_here = False


def _database_path() -> str:
    """Return the path of NOCK_DATABASE, or ":memory:" when unset or empty."""
    database = os.environ.get(DATABASE_VARIABLE, "")
    if database == "":
        return MEMORY_DATABASE  # an empty variable counts as unset
    return database


def _not_found() -> HTTPException:
    """Return the 404 error with FastAPI's usual body."""
    return HTTPException(status_code=404, detail="Not Found")


def _period_not_offered(days: str, offered_days: list[int]) -> RequestValidationError:
    """Return the 422 for a dashboard period that the room lives do not offer.

    It has the body FastAPI gives a wrong `days`: a list of validation errors.
    """
    offered_text = ", ".join(str(offered) for offered in offered_days)
    error = {
        "type": "literal_error",
        "loc": ("query", "days"),
        "msg": f"Input should be one of the offered periods: {offered_text}",
        "input": days,
    }
    return RequestValidationError([error])


def _too_many_requests() -> HTTPException:
    """Return the 429 error of a throttled address (wrong room codes or tokens)."""
    return HTTPException(status_code=429, detail="Too Many Requests")


def _not_authorized() -> HTTPException:
    """Return the 401 error of an ops API request without the operator token."""
    return HTTPException(
        status_code=401,
        detail="Not authorized",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _no_session() -> HTTPException:
    """Return the 401 error of an account route asked without a session."""
    return HTTPException(status_code=401, detail="Not authorized")


def _is_account_path(path: str) -> bool:
    """Tell whether `path` is `/account`, `/api/account` or under it (spec 033)."""
    if path in (ACCOUNT_PAGE_PATH, ACCOUNT_API_ROOT):
        return True
    return path.startswith(ACCOUNT_API_PREFIX)


def _member_identity(rooms: RoomRegistry, key: RoomKey) -> RoomIdentity | None:
    """Return the member of a room whose resume token is the key's, or None.

    The player id and the nickname come from the room (spec 033). None when the
    room is unknown or expired, or when the token is no member's.
    """
    state = rooms.peek_room(key.code)
    if state is None:
        return None
    player_id = room_member_id(state, key.resume_token)
    if player_id is None:
        return None
    nickname = _nickname_of(state, player_id)
    if nickname is None:
        return None
    return RoomIdentity(
        code=key.code,
        player_id=player_id,
        resume_token=key.resume_token,
        nickname=nickname,
    )


def _nickname_of(state: RoomState, player_id: str) -> str | None:
    """Return the nickname of a member of the room, in `players` or past ones."""
    for player in state.players:
        if player.player_id == player_id:
            return player.nickname
    for past_player in state.past_players:
        if past_player.player_id == player_id:
            return past_player.nickname
    return None


def _served_identities(
    rooms: RoomRegistry, store: AccountStore, account_id: str
) -> list[RoomIdentity]:
    """Return the account's identities whose token is still a member's of the room.

    So an identity of a deleted room is left out, also once a new room has its
    code (spec 033, "Room code reused").
    """
    served: list[RoomIdentity] = []
    for identity in store.identities(account_id):
        if rooms.member_id(identity.code, identity.resume_token) is not None:
            served.append(identity)
    return served


def _save_missing_history(
    rooms: RoomRegistry, store: AccountStore, account_id: str
) -> None:
    """Save the record of each solved room of the account that has none yet.

    Each room code of the account's identities is looked up; `save_history`
    takes only the identities whose token is a member's of that room (spec 029).
    """
    for identity in store.identities(account_id):
        state = rooms.peek_room(identity.code)
        if state is not None and state.solved:
            store.save_history(account_id, state)


def _history_saver(store: AccountStore) -> Callable[[RoomState], None]:
    """Return the delete hook that saves the history records of a room (spec 029).

    The hook saves the record of a solved room for each account of
    `accounts_of_room(code)`; `save_history` skips an account whose identities
    are of an older room that had the same code.
    """

    def save_before_deletion(state: RoomState) -> None:
        """Save the records; runs under the registry lock in the deleting thread."""
        if not state.solved:
            return
        for account_id in store.accounts_of_room(state.code):
            store.save_history(account_id, state)

    return save_before_deletion


def _clear_session_cookie(response: Response) -> None:
    """Make the browser forget its session cookie (`Max-Age=0`)."""
    response.delete_cookie(SESSION_COOKIE, path="/")


def _is_ops_path(path: str) -> bool:
    """Tell whether `path` is `/api/ops` or a path under `/api/ops/` (spec 038)."""
    return path == OPS_API_ROOT or path.startswith(OPS_API_PREFIX)


def _carries_token(request: Request, token: str) -> bool:
    """Tell whether the request carries the header `Authorization: Bearer <token>`.

    The token is read from that header only, never from the URL, the query or a
    cookie. It is compared with `secrets.compare_digest`, whose time does not
    tell how much of the token was right.
    """
    header = request.headers.get("authorization", "")
    scheme, separator, given_token = header.partition(" ")
    # The scheme is read in any case, then exactly one space.
    if separator != " " or scheme.lower() != BEARER_SCHEME:
        return False
    # As bytes: compare_digest refuses a str that is not ASCII.
    return secrets.compare_digest(given_token.encode("utf-8"), token.encode("utf-8"))


def _room_logs_since(store: RoomStore, since: float) -> list[RoomLog]:
    """Return the log of each room created at `since` or later (spec 038).

    The rooms are read from the store only, so none of them is made live.
    """
    room_logs: list[RoomLog] = []
    for code, created_at in store.codes_created_since(since):
        entries = tuple(store.read_log(code))
        room_logs.append(RoomLog(code=code, created_at=created_at, entries=entries))
    return room_logs


def _client_address(connection: Request | WebSocket) -> str:
    """Return the address of the client of a request or a socket."""
    if connection.client is None:
        return "unknown"
    return connection.client.host


def _index_response(dist_dir: Path) -> Response:
    """Answer with index.html, or 503 when the client is not built.

    The check is made on every request, so a build made after the server
    started is served without a restart.
    """
    index_path = dist_dir / "index.html"
    if not index_path.is_file():
        return PlainTextResponse(_MISSING_BUILD_TEXT, status_code=503)
    return FileResponse(index_path, headers=NOT_KEPT_WITHOUT_ASKING)


def _published_entry(
    catalogue: Catalogue, number_regex: re.Pattern[str], number: str
) -> CatalogueEntry:
    """Return the published entry written `number` in a URL.

    Raises:
        HTTPException: 404 when `number` is malformed, unknown or unpublished.
    """
    if number_regex.fullmatch(number) is None:
        raise _not_found()
    entry = catalogue.find_published(int(number))
    if entry is None:
        raise _not_found()
    return entry


def _is_safe_file_name(name: str) -> bool:
    """Tell whether `name` is one plain file name that cannot leave a directory."""
    if name == "":
        return False
    # Dot files are never served; this also rejects "." and "..".
    if name.startswith("."):
        return False
    if "/" in name:
        return False
    if "\\" in name:
        return False
    # ":" would allow Windows drive letters and alternate data streams.
    return ":" not in name


def _file_in_directory(
    directory: Path, name: str, cache_headers: dict[str, str]
) -> FileResponse:
    """Answer with the regular file `name` directly inside `directory`.

    Args:
        directory: The folder that holds the file.
        name: The file's name.
        cache_headers: The Cache-Control header of the 200 answer.

    Raises:
        HTTPException: 404 when there is no such file, or `name` leaves `directory`.
    """
    if not _is_safe_file_name(name):
        raise _not_found()
    file_path = (directory / name).resolve()
    if not file_path.is_relative_to(directory.resolve()):
        raise _not_found()
    if not file_path.is_file():
        raise _not_found()
    return FileResponse(file_path, headers=cache_headers)


def _frame_size(raw_message: str | bytes) -> int:
    """Return the size of a frame in bytes (UTF-8 for a text frame)."""
    if isinstance(raw_message, str):
        return len(raw_message.encode("utf-8"))
    return len(raw_message)


async def _read_frames(websocket: WebSocket, connection: RoomConnection) -> None:
    """Pass each frame of the client to the room until the client disconnects.

    The room task decides what a message means: a join, a message of a joined
    player, or an error for a connection that has not joined.
    """
    while True:
        frame = await websocket.receive()
        if frame["type"] == "websocket.disconnect":
            return
        raw_message = frame.get("text")
        if raw_message is None:
            raw_message = frame.get("bytes", b"")
        if _frame_size(raw_message) > MAX_FRAME_BYTES:
            connection.submit_invalid()
            continue
        try:
            message = parse_client_message(raw_message)
        except ValidationError:
            connection.submit_invalid()
            continue
        connection.submit(message)


async def _connect_in_worker(
    connect: Callable[[], RoomConnection | None],
) -> RoomConnection | None:
    """Run `connect` in a worker thread; never leave its connection behind.

    When the handler is cancelled while the thread runs, the thread goes on, and
    the connection it returns is left as soon as it comes, so that the room's
    count of open sockets stays right (`platform/server.md` rule 22).

    Args:
        connect: Opens the connection; it runs in the worker thread.

    Returns:
        What `connect` returned.
    """
    connecting = asyncio.ensure_future(asyncio.to_thread(connect))
    try:
        return await asyncio.shield(connecting)
    except asyncio.CancelledError:
        connecting.add_done_callback(_leave_connection_of)
        raise


def _leave_connection_of(connecting: asyncio.Future[RoomConnection | None]) -> None:
    """Leave the connection that a finished `connect` call gave, if it gave one."""
    if connecting.cancelled() or connecting.exception() is not None:
        return
    connection = connecting.result()
    if connection is not None:
        connection.leave()


async def _serve_socket(websocket: WebSocket, connection: RoomConnection) -> None:
    """Serve the socket of a connection until it closes.

    The writer sends what the room task queues for this connection, in order:
    the snapshot of the join, the events, the errors and the closes. The join
    runs as the account that the socket's session signs in, if any.
    """
    writer = asyncio.create_task(
        connection.run_writer(
            websocket.send_text, lambda close_code: websocket.close(close_code)
        )
    )
    try:
        await _read_frames(websocket, connection)
    finally:
        connection.leave()
        writer.cancel()
        # The writer may have failed on a closed socket, and the server may
        # cancel this handler while it shuts down: neither is an error here.
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await writer


async def _sweep_expired_rooms(
    rooms: RoomRegistry, accounts: _AccountService, stop: asyncio.Event
) -> None:
    """Delete the expired rooms now, then every `expiry_sweep_seconds`, until `stop`.

    While accounts are on, each sweep then deletes the old sign-in links and
    sessions (spec 033). Each sweep runs in a worker thread, since it waits for
    the disk. A sweep that raises is logged, and the next one runs as planned
    (spec 032).
    """
    while not stop.is_set():
        try:
            await asyncio.to_thread(rooms.expire_rooms)
        except Exception:
            logger.exception("The sweep of the expired rooms failed")
        account_store = accounts.store
        if account_store is not None:
            try:
                await asyncio.to_thread(account_store.purge, rooms.clock())
            except Exception:
                logger.exception("The sweep of the old links and sessions failed")
        # The interval, or less when the app stops meanwhile.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), rooms.config.expiry_sweep_seconds)


@contextlib.asynccontextmanager
async def _expiry_sweeps(
    rooms: RoomRegistry, accounts: _AccountService
) -> AsyncGenerator[None]:
    """Run the expiry sweeps of `rooms` in the background while the block runs.

    On the way out, a sweep under way is waited for, so that it never meets a
    closed registry or account store.
    """
    stop = asyncio.Event()
    sweeping = asyncio.create_task(_sweep_expired_rooms(rooms, accounts, stop))
    try:
        yield
    finally:
        stop.set()
        await sweeping


def _declared_length(scope: Scope) -> int | None:
    """Return the request's `Content-Length`, or None when it has none."""
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class _HttpEdge:
    """The HTTP edge of the app, around everything else (`platform/serving.md`).

    It refuses a request body above MAX_BODY_BYTES with 413 before any handler
    runs (rule 11), and adds the SECURITY_HEADERS to every HTTP answer (rule 12).
    A WebSocket scope passes through untouched.
    """

    def __init__(self, app: ASGIApp) -> None:
        """Keep the app that the edge wraps."""
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve one connection: only an HTTP request is checked and marked."""
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers[name] = value
            await send(message)

        declared_length = _declared_length(scope)
        if declared_length is not None:
            if declared_length > MAX_BODY_BYTES:
                await self._refuse(scope, receive, send_with_security_headers)
                return
            await self._app(scope, receive, send_with_security_headers)
            return

        # No Content-Length (a chunked body): read the body before the app sees
        # any of it.
        try:
            body = await _read_body_within_limit(receive)
        except ClientDisconnect:
            return  # the client left before the end of its request
        if body is None:
            await self._refuse(scope, receive, send_with_security_headers)
            return
        await self._app(scope, _replay_body(body, receive), send_with_security_headers)

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Answer 413, whatever the body that follows. It is never cached."""
        response = JSONResponse(
            {"detail": CONTENT_TOO_LARGE_DETAIL},
            status_code=413,
            headers={"Cache-Control": "no-store"},
        )
        await response(scope, receive, send)


async def _read_body_within_limit(receive: Receive) -> bytes | None:
    """Read a whole request body, stopping as soon as it is over MAX_BODY_BYTES.

    At most one chunk above the limit is read.

    Args:
        receive: The ASGI `receive` of the request.

    Returns:
        The whole body, or None when it is over MAX_BODY_BYTES.

    Raises:
        ClientDisconnect: The client left before the end of its request.
    """
    body = bytearray()
    while True:
        message = await receive()
        if message["type"] != "http.request":
            raise ClientDisconnect("The client left before the end of its request")
        body.extend(message.get("body", b""))
        if len(body) > MAX_BODY_BYTES:
            return None
        if not message.get("more_body", False):
            return bytes(body)


def _replay_body(body: bytes, receive: Receive) -> Receive:
    """Return a `receive` that gives `body` first, then what `receive` gives."""
    is_replayed = False

    async def replay() -> Message:
        nonlocal is_replayed
        if not is_replayed:
            is_replayed = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


class _EdgeFastAPI(FastAPI):
    """A FastAPI app whose whole middleware stack sits inside the HTTP edge.

    The edge is outside Starlette's error middleware, so the answer to an
    unhandled error carries the security headers too.
    """

    def build_middleware_stack(self) -> ASGIApp:
        """Build the stack, wrapped in the HTTP edge."""
        return _HttpEdge(super().build_middleware_stack())


def create_app(
    rooms: RoomRegistry | None = None,
    dist_dir: Path | None = None,
    catalogue: Catalogue | None = None,
    *,
    operator_token: str | None = None,
    accounts: AccountSettings | None = None,
    account_store: AccountStore | None = None,
    mailer: Mailer | None = None,
) -> FastAPI:
    """Build the app.

    Args:
        rooms: The rooms the WebSocket serves. None: a new registry on the
            database of the environment variable NOCK_DATABASE (in memory when
            it is unset or empty), opened when the app starts and closed when
            it stops.
            A registry given is never closed by the app.
        dist_dir: The built client. None: WEB_DIST_DIR.
        catalogue: The grids served. None: an empty catalogue.
        operator_token: The token of the operator pages (spec 038), checked
            by the rule of NOCK_OPERATOR_TOKEN when `create_app` is called:
            "" turns the pages off, as an unset variable does, and the
            variable is not read. None: the token of NOCK_OPERATOR_TOKEN, read
            when the app starts; the pages are off when the variable is unset
            or empty.
        accounts: The account settings (spec 033). None: the settings of
            `account_settings_from_env(os.environ)`, read when the app starts;
            accounts are off when NOCK_PUBLIC_URL and NOCK_SMTP_HOST are unset.
        account_store: Where the accounts are kept. None, accounts on: a new
            AccountStore on NOCK_DATABASE (":memory:" when unset or empty),
            opened when the app starts and closed when it stops; accounts off:
            none. A store given is never closed by the app.
        mailer: What sends the sign-in links. None: SmtpMailer(accounts.smtp).

    Never raises because `dist_dir` is missing or empty (see AC-6). The app's
    startup raises SettingsError when it reads a NOCK_OPERATOR_TOKEN that breaks
    the rule of spec 038, a NOCK_ROOMS_PER_ADDRESS_PER_HOUR that breaks the rule
    of `lobby/rooms.md` rule 14, a NOCK_SOCKETS_PER_ADDRESS that breaks the rule
    of `platform/realtime.md` rule 26, or account variables that break the rules of
    spec 033.

    Raises:
        SettingsError: `operator_token` breaks the rule of NOCK_OPERATOR_TOKEN.
            The message never holds it.
    """
    holder = _RoomsHolder(rooms)
    operator = _OperatorToken(operator_token)
    running_overrides = _RunningOverrides()
    room_creations = _RoomCreationLimit()
    open_sockets = _OpenSocketCap()
    account_service = _AccountService(accounts, account_store, mailer)
    client_dir = dist_dir if dist_dir is not None else WEB_DIST_DIR
    grid_catalogue = catalogue if catalogue is not None else Catalogue()
    room_code_regex = re.compile(ROOM_CODE_PATTERN)
    grid_number_regex = re.compile(GRID_NUMBER_PATTERN)
    wrong_codes = _WrongCodeThrottle()
    # Spec 038: the refused ops API requests, counted apart from the wrong codes.
    refused_ops_requests = _WrongCodeThrottle()

    @contextlib.asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        operator.read_at_start()
        room_creations.read_at_start()
        open_sockets.read_at_start()
        account_service.start()
        try:
            room_registry = holder.get()
            # Spec 029: before a room is deleted, its accounts keep their records.
            account_store = account_service.store
            if account_store is not None:
                room_registry.set_delete_hook(_history_saver(account_store))
            # While accounts are off, the rooms play as anonymous rooms.
            room_registry.set_creators_active(account_store is not None)
            # `admin/overrides.md` rule 8: before the first sweep.
            running_overrides.start(room_registry, holder.settings_set())
            try:
                async with _expiry_sweeps(room_registry, account_service):
                    yield
            finally:
                running_overrides.stop()
                room_registry.set_delete_hook(None)
        finally:
            account_service.stop()
            holder.close_if_created()

    # No slash redirect: a path ending with "/" matches no route and is a 404.
    web_app = _EdgeFastAPI(
        lifespan=lifespan,
        redirect_slashes=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    # Spec 038, rule 1: while the operator pages are off, a request of any
    # method to an ops path answers as the same method on an unknown path under
    # /api/ does. The routes cannot answer it: another method than GET on the
    # path of an ops route would get FastAPI's 405. Rule 4: while the pages are
    # on, no browser or proxy keeps an ops API answer, refusals included.
    @web_app.middleware("http")
    async def guard_ops_paths(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if operator.token is None:
            if _is_ops_path(path):
                # FastAPI's own answer to a path that no route matches.
                return await http_exception_handler(request, _not_found())
            return await call_next(request)
        response = await call_next(request)
        if path.startswith(OPS_API_PREFIX):
            response.headers["Cache-Control"] = NO_STORE
        return response

    # Spec 033: while accounts are off, the account page and every path under
    # /api/account answer as an unknown path does, whatever the method. While
    # they are on, no browser or proxy keeps an answer under /api/account.
    @web_app.middleware("http")
    async def guard_account_paths(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if not _is_account_path(path):
            return await call_next(request)
        if account_service.settings is None:
            return await http_exception_handler(request, _not_found())
        response = await call_next(request)
        if path != ACCOUNT_PAGE_PATH:
            response.headers["Cache-Control"] = NO_STORE
        return response

    def account_store_in_use() -> AccountStore:
        """Return the account store, or refuse the request while accounts are off.

        Raises:
            HTTPException: 404 while accounts are off; `guard_account_paths`
                already answers so.
        """
        store = account_service.store
        if store is None:
            raise _not_found()
        return store

    def account_of_cookies(cookies: Mapping[str, str]) -> Account | None:
        """Return the account of a session cookie, None while accounts are off."""
        store = account_service.store
        session = cookies.get(SESSION_COOKIE)
        if store is None or session is None:
            return None
        return store.account_of_session(session, holder.get().clock())

    def signed_in_account(request: Request) -> Account | None:
        """Return the account of the request's session cookie, or None."""
        account_store_in_use()
        return account_of_cookies(request.cookies)

    def require_account(request: Request) -> Account:
        """Return the account of the session, or refuse the request (spec 033).

        Raises:
            HTTPException: 401 without a session that signs an account in.
        """
        account = signed_in_account(request)
        if account is None:
            raise _no_session()
        return account

    def check_operator(request: Request) -> None:
        """Let an ops API request through, or refuse it (spec 038, rules 1 to 3).

        Runs before the route reads its parameters, so a wrong token is refused
        before any validation.

        Raises:
            HTTPException: 404 while the operator pages are off, as for any
                unknown path; 429 while the client's address is throttled,
                whatever its token; 401 without the operator token, which
                counts as one refusal of the address.
        """
        token = operator.token
        if token is None:
            # Rule 1. `guard_ops_paths` already answers so while the pages are off.
            raise _not_found()
        address = _client_address(request)
        now = holder.get().clock()
        if refused_ops_requests.is_blocked(address, now):
            raise _too_many_requests()
        if _carries_token(request, token):
            return
        # Checked again as it is recorded: requests run in several threads.
        if not refused_ops_requests.record_unless_blocked(address, now):
            raise _too_many_requests()
        raise _not_authorized()

    @web_app.get("/", include_in_schema=False)
    def serve_catalogue() -> Response:
        return _index_response(client_dir)

    # The operator's page asks for the token itself, so it is served to anyone
    # while the operator pages are on (spec 038).
    @web_app.get("/ops", include_in_schema=False)
    def serve_ops_page() -> Response:
        if operator.token is None:
            raise _not_found()
        return _index_response(client_dir)

    @web_app.get(ACCOUNT_PAGE_PATH, include_in_schema=False)
    def serve_account_page() -> Response:
        return _index_response(client_dir)

    @web_app.get("/r/{code}", include_in_schema=False)
    def serve_room(code: str) -> Response:
        if room_code_regex.fullmatch(code) is None:
            raise _not_found()
        return _index_response(client_dir)

    @web_app.get("/g/{number}", include_in_schema=False)
    def serve_grid(number: str) -> Response:
        _published_entry(grid_catalogue, grid_number_regex, number)
        return _index_response(client_dir)

    @web_app.get("/recap/{token}", include_in_schema=False)
    def serve_shared_recap(token: str) -> Response:
        if holder.get().shared_recap(token) is None:
            raise _not_found()
        return _index_response(client_dir)

    @web_app.get("/api/grids")
    def list_grids(
        force: Annotated[str | None, Query(pattern=FORCE_PATTERN)] = None,
    ) -> list[dict[str, object]]:
        force_number = int(force) if force is not None else None
        summaries = grid_catalogue.published_summaries(force_number)
        bodies: list[dict[str, object]] = []
        for summary in summaries:
            bodies.append(summary.model_dump(mode="json"))
        return bodies

    @web_app.get("/api/grids/{number}")
    def get_grid(number: str) -> dict[str, object]:
        entry = _published_entry(grid_catalogue, grid_number_regex, number)
        return summarize(entry).model_dump(mode="json")

    @web_app.get("/api/rooms", include_in_schema=False)
    def refuse_room_list() -> None:
        raise _not_found()

    @web_app.post("/api/rooms", status_code=201)
    def create_room(body: CreateRoomRequest, request: Request) -> CreateRoomResponse:
        entry = grid_catalogue.find_published(body.grid_number)
        if entry is None:
            raise _not_found()
        creator = account_of_cookies(request.cookies)
        creator_account_id = None if creator is None else creator.account_id
        room_registry = holder.get()
        address = _client_address(request)
        now = room_registry.clock()
        if not room_creations.count_unless_reached(address, now):
            raise _too_many_requests()
        try:
            code = room_registry.register_room(
                entry.grid,
                grid_number=body.grid_number,
                creator_account_id=creator_account_id,
            )
        except Exception:
            room_creations.forget_creation(address, now)
            raise
        base_url = str(request.base_url).rstrip("/")
        return CreateRoomResponse(code=code, share_url=f"{base_url}/r/{code}")

    # Spec 028. A wrong code counts against the throttle of the room socket, so
    # this route cannot be used to test room codes at full speed.
    @web_app.get("/api/rooms/{code}/recap")
    def get_room_recap(code: str, request: Request) -> dict[str, object]:
        room_registry = holder.get()
        address = _client_address(request)
        now = room_registry.clock()
        if wrong_codes.is_blocked(address, now):
            raise _too_many_requests()
        if room_registry.peek_room(code) is None:
            # Checked again as it is recorded: requests run in several threads.
            if not wrong_codes.record_unless_blocked(address, now):
                raise _too_many_requests()
            raise _not_found()
        recap = room_registry.room_recap(code)
        if recap is None:
            raise _not_found()
        return recap.model_dump(mode="json")

    @web_app.get("/api/recaps/{token}")
    def get_shared_recap(token: str) -> dict[str, object]:
        shared = holder.get().shared_recap(token)
        if shared is None:
            raise _not_found()
        return shared.model_dump(mode="json")

    # Spec 032: the rooms a device keeps a member's token of. A room left out is
    # never said why, so this route tests no room code and is not throttled.
    @web_app.post("/api/rooms/summaries")
    def list_room_summaries(body: RoomSummariesRequest) -> list[dict[str, object]]:
        summaries: list[RoomSummary] = holder.get().room_summaries(body.rooms)
        bodies: list[dict[str, object]] = []
        for summary in summaries:
            bodies.append(summary.model_dump(mode="json"))
        return bodies

    # Spec 034: what changed in a room while a member's page was away. A 404
    # never says why, so this route is no oracle for room codes and is not
    # throttled.
    @web_app.post("/api/rooms/{code}/catch-up")
    def get_catch_up(code: str, body: CatchUpRequest) -> dict[str, object]:
        if room_code_regex.fullmatch(code) is None:
            raise _not_found()
        catch_up = holder.get().catch_up(code, body)
        if catch_up is None:
            raise _not_found()
        return catch_up.model_dump(mode="json")

    # Spec 038: the figures of the rooms created in the last `days` days, read
    # from the store without making any room live.
    # A period that the room lives do not offer is refused as a wrong one.
    @web_app.get("/api/ops/dashboard", dependencies=[Depends(check_operator)])
    def get_dashboard(
        days: Annotated[DashboardDays | None, Query()] = None,
    ) -> dict[str, object]:
        room_registry = holder.get()
        now = room_registry.clock()
        offered_days = offered_periods(room_registry.config)
        if days is None:
            period_days = default_period(offered_days)
        else:
            period_days = int(days)
            if period_days not in offered_days:
                raise _period_not_offered(days, offered_days)
        since = now - period_days * DAY_SECONDS
        room_logs = _room_logs_since(room_registry.store, since)
        figures = dashboard_figures(room_logs, period_days, now)
        answer = figures.model_dump(mode="json")
        answer["offered_days"] = offered_days
        return answer

    # Spec 038: the empty grid and the ordered edits of one room, from its log.
    # A 404 here is no refusal: only wrong tokens count against the address.
    @web_app.get("/api/ops/rooms/{code}/edits", dependencies=[Depends(check_operator)])
    def get_room_edits(code: str) -> dict[str, object]:
        if room_code_regex.fullmatch(code) is None:
            raise _not_found()
        room_registry = holder.get()
        state = room_registry.peek_room(code)
        if state is None:
            raise _not_found()
        entries = room_registry.store.read_log(code)
        replay = RoomReplay(
            code=code, grid=grid_view(state.grid), edits=room_edits(entries)
        )
        return replay.model_dump(mode="json")

    # `admin/overrides.md` rule 3: the five settings with their sources.
    @web_app.get("/api/ops/settings", dependencies=[Depends(check_operator)])
    def get_settings() -> dict[str, object]:
        return running_overrides.get().answer()

    # Rule 4: save an override of one setting, or remove it with a null value.
    @web_app.put("/api/ops/settings", dependencies=[Depends(check_operator)])
    def save_setting(change: SettingChange) -> dict[str, object]:
        overrides = running_overrides.get()
        overrides.save(change.name, change.value)
        return overrides.answer()

    # Rule 5: how many rooms a proposed room life would delete now. Nothing is
    # saved or deleted.
    @web_app.post("/api/ops/settings/dry-run", dependencies=[Depends(check_operator)])
    def dry_run_setting(change: SettingChange) -> dict[str, object]:
        if not change.is_room_life():
            raise HTTPException(
                status_code=422, detail="The dry run is for a room life only"
            )
        rooms = running_overrides.get().dry_run(change.name, change.value)
        return {"rooms": rooms}

    @web_app.get(ACCOUNT_API_ROOT)
    def get_account_status(request: Request) -> dict[str, object]:
        account = signed_in_account(request)
        if account is None:
            status = AccountStatus(signed_in=False, email=None)
        else:
            status = AccountStatus(signed_in=True, email=account.email)
        return status.model_dump(mode="json")

    # Spec 033: checked in this order: the body, the address, the room, the
    # limits; then the mail is sent. Only a request that reaches the mailer
    # counts toward the limits.
    @web_app.post(f"{ACCOUNT_API_ROOT}/link", status_code=202)
    def ask_sign_in_link(
        body: SignInLinkRequest, request: Request
    ) -> dict[str, object]:
        store = account_store_in_use()
        settings = account_service.settings
        sender = account_service.mailer
        if settings is None or sender is None:
            raise _not_found()
        try:
            email = normalize_email(body.email)
        except ValueError:
            raise HTTPException(
                status_code=422, detail="Invalid e-mail address"
            ) from None
        room_registry = holder.get()
        room = body.room
        if (
            room is not None
            and room_registry.member_id(room.code, room.resume_token) is None
        ):
            raise _not_found()
        now = room_registry.clock()
        address = _client_address(request)
        if not account_service.limits.count_unless_reached(email, address, now):
            raise _too_many_requests()
        token = store.add_link(email, body.room, now)
        try:
            sender.send(sign_in_message(settings, email, token))
        except MailError as error:
            # A MailError names the kind of failure only: no address, no secret.
            logger.warning("A sign-in link was not sent: %s", error)
            raise HTTPException(status_code=503, detail="Mail not sent") from None
        return {}

    @web_app.post(f"{ACCOUNT_API_ROOT}/sign-in")
    def sign_in_with_link(body: SignInRequest, response: Response) -> dict[str, object]:
        store = account_store_in_use()
        settings = account_service.settings
        if settings is None:
            raise _not_found()
        room_registry = holder.get()
        now = room_registry.clock()
        link = store.use_link(body.token, now)
        if link is None:
            raise _not_found()
        session = store.sign_in(link.email, now)
        room_code = None
        if link.room is not None:
            identity = _member_identity(room_registry, link.room)
            if identity is not None:
                store.link_identity(session.account_id, identity, now)
                room_code = identity.code
        rooms = _served_identities(room_registry, store, session.account_id)
        response.set_cookie(
            SESSION_COOKIE,
            session.session,
            max_age=int(SESSION_LIFE_SECONDS),
            path="/",
            secure=settings.public_url.startswith("https://"),
            httponly=True,
            samesite="lax",
        )
        result = SignInResult(email=link.email, room_code=room_code, rooms=tuple(rooms))
        return result.model_dump(mode="json")

    @web_app.post(f"{ACCOUNT_API_ROOT}/sign-out", status_code=204)
    def sign_out(request: Request) -> Response:
        store = account_store_in_use()
        session = request.cookies.get(SESSION_COOKIE)
        if session is not None:
            store.end_session(session)
        response = Response(status_code=204)
        _clear_session_cookie(response)
        return response

    @web_app.get(f"{ACCOUNT_API_ROOT}/rooms")
    def list_account_rooms(request: Request) -> list[dict[str, object]]:
        account = require_account(request)
        store = account_store_in_use()
        identities = _served_identities(holder.get(), store, account.account_id)
        bodies: list[dict[str, object]] = []
        for identity in identities:
            bodies.append(identity.model_dump(mode="json"))
        return bodies

    # Spec 029: the account's finished grids, after saving the missing records.
    @web_app.get(f"{ACCOUNT_API_ROOT}/history")
    def list_account_history(request: Request) -> list[dict[str, object]]:
        account = require_account(request)
        store = account_store_in_use()
        _save_missing_history(holder.get(), store, account.account_id)
        bodies: list[dict[str, object]] = []
        for record in store.history(account.account_id):
            bodies.append(record.model_dump(mode="json"))
        return bodies

    # Rule 24: derived at each request from the history, the rooms and the
    # creator rooms; nothing is saved.
    @web_app.get(f"{ACCOUNT_API_ROOT}/progress")
    def get_account_progress(request: Request) -> dict[str, str]:
        account = require_account(request)
        store = account_store_in_use()
        room_registry = holder.get()
        created_codes = room_registry.store.codes_created_by(account.account_id)
        return store.progress(
            account.account_id, room_registry.peek_room, created_codes
        )

    # The dependency refuses a request without a session before its body is
    # read (spec 033) and hands the account of the session to the route. The
    # dependency is a default value, not an `Annotated` one: `require_account` is
    # local to this function, so FastAPI could not find it from the annotation text
    # that `from __future__ import annotations` leaves.
    account_of_request = Depends(require_account)

    @web_app.put(f"{ACCOUNT_API_ROOT}/rooms", status_code=204)
    def link_account_room(
        body: RoomKey, account: Account = account_of_request
    ) -> Response:
        store = account_store_in_use()
        room_registry = holder.get()
        identity = _member_identity(room_registry, body)
        if identity is None:
            raise _not_found()
        linked = store.link_identity(
            account.account_id, identity, room_registry.clock()
        )
        if not linked:
            # The account was deleted after the session was read.
            raise _no_session()
        return Response(status_code=204)

    # Spec 033: the account goes at once, then each of its players is erased
    # from the rooms that still exist.
    @web_app.delete(ACCOUNT_API_ROOT, status_code=204)
    def delete_account(request: Request) -> Response:
        account = require_account(request)
        store = account_store_in_use()
        room_registry = holder.get()
        deleted_identities = store.delete_account(account.account_id)
        for identity in deleted_identities:
            room_registry.erase_player(identity.code, identity.player_id)
        room_registry.delete_creator_rooms(account.account_id)
        # Erasing a player deletes an expired room, whose delete hook may have
        # saved a record with the nickname: erase it from the records once more.
        store.erase_players_from_history(deleted_identities)
        response = Response(status_code=204)
        _clear_session_cookie(response)
        return response

    @web_app.get("/assets/{file_name}", include_in_schema=False)
    def serve_asset(file_name: str) -> FileResponse:
        return _file_in_directory(client_dir / "assets", file_name, KEPT_FOR_A_YEAR)

    @web_app.get("/{file_name}", include_in_schema=False)
    def serve_root_file(file_name: str) -> FileResponse:
        if file_name == "api":
            raise _not_found()
        return _file_in_directory(client_dir, file_name, NOT_KEPT_WITHOUT_ASKING)

    async def serve_counted_socket(
        websocket: WebSocket, room_registry: RoomRegistry, code: str, address: str
    ) -> None:
        """Serve a socket that is counted among the open sockets of its address."""
        now = room_registry.clock()
        if wrong_codes.is_blocked(address, now):
            await websocket.close(code=THROTTLED_CLOSE_CODE)
            return
        owner_loop = asyncio.get_running_loop()
        cookies = websocket.cookies

        def connect() -> RoomConnection | None:
            account = account_of_cookies(cookies)
            account_id = None if account is None else account.account_id
            return room_registry.connect(code, account_id, owner_loop=owner_loop)

        # One call in a worker thread (`platform/server.md` rule 22): it may
        # read the room from the store or delete it once expired (spec 032),
        # and the event loop must not wait.
        connection = await _connect_in_worker(connect)
        if connection is None:
            # Checked again as it is recorded: other sockets of the address may
            # have been counted while this one waited for its lookup.
            if wrong_codes.record_unless_blocked(address, now):
                await websocket.close(code=ROOM_NOT_FOUND_CLOSE_CODE)
            else:
                await websocket.close(code=THROTTLED_CLOSE_CODE)
            return
        await _serve_socket(websocket, connection)

    @web_app.websocket("/api/rooms/{code}/ws")
    async def room_socket(websocket: WebSocket, code: str) -> None:
        room_registry = holder.get()
        await websocket.accept()
        address = _client_address(websocket)
        # Counted before the throttle, and released whatever closes the socket.
        if not open_sockets.count_unless_reached(address):
            await websocket.close(code=TOO_MANY_SOCKETS_CLOSE_CODE)
            return
        try:
            await serve_counted_socket(websocket, room_registry, code, address)
        finally:
            open_sockets.release(address)

    return web_app


def server_config(
    app: FastAPI, host: str = "127.0.0.1", port: int = 8000, log_level: str = "warning"
) -> uvicorn.Config:
    """Return the uvicorn configuration of the server.

    `ws_max_size` is WS_MAX_SIZE_BYTES: uvicorn refuses a larger frame before
    it is buffered whole, and closes the socket with 1009. `access_log` is
    False and the level defaults to "warning": uvicorn writes the client's
    address in its access log and in its info line for each socket (spec 038).
    Every other option is uvicorn's default.

    Args:
        app: The app to serve.
        host: The address the server listens on.
        port: The port the server listens on.
        log_level: The level of uvicorn's logs.

    Returns:
        The configuration to give to `uvicorn.Server`.
    """
    return uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
        ws_max_size=WS_MAX_SIZE_BYTES,
    )


app: FastAPI = create_app(catalogue=load_catalogue(GRIDS_DIR))
