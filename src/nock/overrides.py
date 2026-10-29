"""The `/ops` overrides of the room lives and the sweep interval.

The operator saves a value for one of five settings (`admin/overrides.md`): the
four room lives and the sweep interval. A saved value outranks the environment
variable and the default. The effective values are held by the registry's
`RoomConfig`, so every rule that reads a life or the interval follows a save.
"""

from __future__ import annotations

import logging
import threading
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, StrictInt, model_validator

from nock.hub import RoomRegistry
from nock.room import (
    DEFAULT_ROOM_LIFE_HOURS,
    MAX_ROOM_LIFE_HOURS,
    MIN_ROOM_LIFE_HOURS,
    RoomConfig,
)
from nock.settings import (
    DEFAULT_SWEEP_MINUTES,
    MAX_SWEEP_MINUTES,
    MIN_SWEEP_MINUTES,
    SECONDS_PER_MINUTE,
)

logger = logging.getLogger(__name__)

SWEEP_MINUTES_NAME: str = "expiry_sweep_minutes"


class Setting(NamedTuple):
    """One setting: its name, its unit and its bounds (`admin/overrides.md` rule 1)."""

    name: str
    unit: str  # "hours" or "minutes"
    minimum: int
    maximum: int
    default: int


def _room_life(name: str) -> Setting:
    """Return the room life setting called `name`."""
    return Setting(
        name, "hours", MIN_ROOM_LIFE_HOURS, MAX_ROOM_LIFE_HOURS, DEFAULT_ROOM_LIFE_HOURS
    )


# The five settings, in the order the routes list them.
SETTINGS: tuple[Setting, ...] = (
    _room_life("creator_solved_room_hours"),
    _room_life("creator_room_hours"),
    _room_life("anonymous_solved_room_hours"),
    _room_life("anonymous_room_hours"),
    Setting(
        SWEEP_MINUTES_NAME,
        "minutes",
        MIN_SWEEP_MINUTES,
        MAX_SWEEP_MINUTES,
        DEFAULT_SWEEP_MINUTES,
    ),
)
SETTING_BY_NAME: dict[str, Setting] = {setting.name: setting for setting in SETTINGS}


class SettingChange(BaseModel):
    """The body of `PUT /api/ops/settings` and of the dry run.

    `value` is a whole number within the setting's bounds, or None to remove
    the override. A body that breaks this is refused with a 422.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    value: StrictInt | None  # no default: a body with no `value` is refused

    @model_validator(mode="after")
    def check_name_and_bounds(self) -> SettingChange:
        """Refuse an unknown setting and a value out of its bounds."""
        setting = SETTING_BY_NAME.get(self.name)
        if setting is None:
            raise ValueError(f"Unknown setting: {self.name!r}")
        if self.value is None:
            return self
        if self.value < setting.minimum or self.value > setting.maximum:
            raise ValueError(
                f"{self.name} must be from {setting.minimum} to {setting.maximum}"
            )
        return self

    def is_room_life(self) -> bool:
        """Tell whether the setting is a room life (the interval is not)."""
        return self.name != SWEEP_MINUTES_NAME


def _whole_if_possible(number: float) -> float:
    """Return `number` as an int when it is whole (60.0 is 60), else as it is."""
    if number == int(number):
        return int(number)
    return number


def _values_of(config: RoomConfig) -> dict[str, float]:
    """Return the five values a config holds, by setting name.

    The interval is in minutes, a fraction of a minute when the config holds one.
    """
    return {
        "creator_solved_room_hours": config.creator_solved_room_hours,
        "creator_room_hours": config.creator_room_hours,
        "anonymous_solved_room_hours": config.anonymous_solved_room_hours,
        "anonymous_room_hours": config.anonymous_room_hours,
        SWEEP_MINUTES_NAME: _whole_if_possible(
            config.expiry_sweep_seconds / SECONDS_PER_MINUTE
        ),
    }


def _config_with(environment: RoomConfig, overrides: dict[str, int]) -> RoomConfig:
    """Return `environment` with each override in place of its value."""
    changes: dict[str, float] = {}
    for name, value in overrides.items():
        if name == SWEEP_MINUTES_NAME:
            changes["expiry_sweep_seconds"] = value * SECONDS_PER_MINUTE
        else:
            changes[name] = value
    return environment.model_copy(update=changes)


def _valid_override(name: str, value: object) -> int | None:
    """Return a stored value as an int when it is a valid override of `name`.

    Returns:
        The value, or None when `name` is unknown or the value is not a whole
        number within the setting's bounds.
    """
    setting = SETTING_BY_NAME.get(name)
    if setting is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        return None
    if value < setting.minimum or value > setting.maximum:
        return None
    return value


class RoomLifeOverrides:
    """The overrides of one registry: stored in its store, applied to its config.

    The environment values are the registry's config when this is made, that is
    when the app starts. Every method may be called from any thread.
    """

    def __init__(self, registry: RoomRegistry) -> None:
        """Keep the registry and its config as the environment values."""
        self._registry = registry
        self._store = registry.store
        self._environment = registry.config
        self._overrides: dict[str, int] = {}
        self._lock = threading.Lock()

    def load(self) -> None:
        """Read the table, drop the rows that are not valid, and apply the rest.

        A row with an unknown name, or a value that is not a whole number within
        the bounds, is deleted and logged at WARNING; the start goes on.
        """
        with self._lock:
            for name, value in self._store.read_overrides():
                valid_value = _valid_override(name, value)
                if valid_value is None:
                    self._store.delete_override(name)
                    logger.warning(
                        "Dropped the stored override %s with the value %r", name, value
                    )
                else:
                    self._overrides[name] = valid_value
            self._registry.replace_config(self._effective_config())

    def unload(self) -> None:
        """Give the registry back the environment values, as the app stops."""
        with self._lock:
            self._registry.replace_config(self._environment)

    def answer(self) -> dict[str, object]:
        """Return the answer of `GET /api/ops/settings` (rule 3)."""
        with self._lock:
            rows: list[dict[str, object]] = []
            for setting in SETTINGS:
                rows.append(self._row(setting))
        return {"durable": self._store.is_durable, "settings": rows}

    def save(self, name: str, value: int | None) -> None:
        """Save the override of a setting, or remove it with None, and apply it.

        The registry's config is swapped, so the next lookup and the next sweep
        use the new value; nothing is deleted here. One INFO record logs the
        old and the new effective value.

        Args:
            name: A setting of `SETTINGS`.
            value: A whole number within its bounds, or None.
        """
        with self._lock:
            old_value = _values_of(self._registry.config)[name]
            if value is None:
                self._store.delete_override(name)
                self._overrides.pop(name, None)
            else:
                self._store.save_override(name, value)
                self._overrides[name] = value
            new_config = self._effective_config()
            self._registry.replace_config(new_config)
            new_value = _values_of(new_config)[name]
        logger.info("Setting %s changed from %s to %s", name, old_value, new_value)

    def dry_run(self, name: str, value: int | None) -> int:
        """Count the rooms that a room life would delete now, saving nothing.

        Args:
            name: A room life of `SETTINGS`.
            value: The proposed life in hours; None: the value a reset falls
                back to, the environment value.

        Returns:
            How many rooms `lobby/lifetime.md` rule 5 finds expired with that
            life, the other lives as they are.
        """
        if value is None:
            value = int(_values_of(self._environment)[name])
        proposed_config = self._registry.config.model_copy(update={name: value})
        return self._registry.count_expired_rooms(proposed_config)

    def _effective_config(self) -> RoomConfig:
        """Return the environment config with the overrides in place. Caller locks."""
        return _config_with(self._environment, self._overrides)

    def _row(self, setting: Setting) -> dict[str, object]:
        """Return the nine fields of a setting's row. Caller locks."""
        name = setting.name
        environment_value = _values_of(self._environment)[name]
        environment: float | None = None
        if environment_value != setting.default:
            environment = environment_value
        override = self._overrides.get(name)
        if override is not None:
            value: float = override
            source = "override"
        elif environment is not None:
            value = environment
            source = "environment"
        else:
            value = setting.default
            source = "default"
        return {
            "name": name,
            "unit": setting.unit,
            "min": setting.minimum,
            "max": setting.maximum,
            "default": setting.default,
            "environment": environment,
            "override": override,
            "value": value,
            "source": source,
        }
