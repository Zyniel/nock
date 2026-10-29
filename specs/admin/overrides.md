---
area: admin
file: overrides
status: done
---

# admin/overrides - The `/ops` overrides of the room lives

## Purpose

The operator changes the four room lives and the sweep interval from `/ops`
without a restart, sees where each value comes from, and learns how many rooms a
shorter life would delete before saving it.

## Depends on

- `lobby/lifetime.md`: the five settings, their bounds and defaults (rules 4, 7),
  the expiry decision (rule 5) and the sweep (rule 6).
- `admin/operations.md`: the operator token, the throttle and the ops API's
  common rules (6, 8 to 10), the page's states (rule 16).
- `platform/server.md`: the store, on a file or in memory.

## Rules

### Values

1. The settings are the four room lives and the sweep interval, each named as
   its `RoomConfig` field, the interval `expiry_sweep_minutes` (whole minutes).
   Each has a default value (720 hours; 60 minutes), an environment value (its
   variable's, when set, `lobby/lifetime.md` rule 7; for an app given a
   registry, its config's), an override (a value saved from `/ops`, or none)
   and an effective value: the override, else the environment value, else the
   default; its source is `override`, `environment` or `default`. The bounds
   are the variable's (24 to 8760 hours; 1 to 1440 minutes).
2. Every rule that reads a life or the interval reads the effective value: the
   registry's config (`RoomRegistry.config`) holds the five effective values,
   so expiry, the sweep and the dashboard periods (`admin/operations.md` rule
   12) follow an override. An override outranks the variable even when the
   variable changed since the save.

### The routes

3. `GET /api/ops/settings`: 200 `{"durable": b, "settings": [...]}`, the five
   settings in rule 1's order, each `name`, `unit` (`hours` or `minutes`),
   `min`, `max`, `default`, `environment` (null when the variable is unset),
   `override` (null when none), `value` (the effective value) and `source`.
   `durable` is true when the store is a database file.
4. `PUT /api/ops/settings`, body `{"name": s, "value": v}`: `v` a whole number
   within the bounds saves it as the override of `s`; `v` null removes the
   override; either answers 200 with rule 3's answer. An unknown name, a
   missing field, a value that is not a whole number (`"24"`, 24.5, true) or
   one out of bounds: 422, nothing changed.
5. `POST /api/ops/settings/dry-run`, the same body, a room life only: 200
   `{"rooms": n}`, `n` the number of rooms the proposed value would delete now:
   the rooms the sweep reads, live or not, that `lobby/lifetime.md` rule 5 finds
   expired at the clock time with that life (for null, the value the reset
   falls back to) and the other lives as they are. A room due under the current
   value that the proposed value keeps is not counted. Nothing is saved or
   deleted and no socket closes.
   `expiry_sweep_minutes`, or a body rule 4 refuses: 422.
6. The three routes follow `admin/operations.md` rules 6 (pages off: 404), 8
   and 9 (the throttle: a 401 counts, a 422 never) and 10 (`no-store` on every
   answer; another method on `/api/ops/settings` 405).

### Storage

7. The overrides are rows of the table `overrides (name TEXT PRIMARY KEY,
   value INTEGER NOT NULL)` of the room store, created with the other tables
   (`CREATE TABLE IF NOT EXISTS`; `user_version` stays 2, `lobby/lifetime.md`
   rule 8). A room's deletion never touches it. On a file they survive a
   restart; in memory (`NOCK_DATABASE` unset) they go with the process.
8. When the app starts, before its first sweep, it reads the table: each valid
   row is an override; a row whose name is unknown, or whose value is not a
   whole number within the bounds, is deleted and logged once at WARNING
   (`nock.overrides`, naming the row's name and value); the start never fails
   over one. The environment values are those the app started with.

### Applying

9. A save or a reset swaps the registry's config under its lock: the next
   lookup and the next sweep use the new value, and saving deletes nothing by
   itself. A new interval starts after the sweep's current wait. The other
   four effective values stay.
10. Each 200 of `PUT` logs one INFO record of `nock.overrides` holding the
    setting's name, the old and the new effective value, never the token.
    `python -m nock` logs at `warning` (`product.md` rule 27): the record
    reaches only a host that sets up logging.

### The page

11. In `ready`, between the dashboard and the replay, the card
    `ops.settings_heading` asks `GET /api/ops/settings` and holds one line
    while waiting (`ops.loading`) or when it fails (`ops.error`); a 401 or 429
    locks the page (`admin/operations.md` rule 16). Then one row per setting,
    rule 3's order: its name `ops.setting.<name>`, its effective value
    (`ops.hours_value`, `ops.minutes_value`), its source (`ops.source.default`,
    `ops.source.environment`, `ops.source.override`), a number input named by
    the row's name, empty, the buttons `ops.setting_save` and
    `ops.setting_reset`, the latter disabled unless the source is `override`.
12. `ops.setting_save` with the input empty, not a whole number or out of
    bounds shows `ops.setting_out_of_bounds` (the bounds and unit) as an error
    line under the input and sends nothing. Otherwise, for the interval or a
    life not below the row's effective value, it sends the `PUT`;
    `ops.setting_reset` does the same with the value the reset falls back to.
    A life below the row's effective value sends the dry run first and asks
    (rule 13). After a 200 the rows show the answer, the input is emptied and
    the page asks the dashboard again with no period, handled as a period press
    (`admin/operations.md` rule 18). A 422 or another failure shows `ops.error`
    as an error line under the input; a 401 or 429 locks.
13. The question is the account page's disclosure inside the card, under a
    divider: `ops.setting_confirm_one` (0 or 1 room) or
    `ops.setting_confirm_many` with the dry run's count, `ops.setting_confirm`
    and `ops.setting_cancel`; while open the button that asked shows pressed,
    and `ops.setting_cancel` or a second press closes it with nothing sent. At
    most one question is open. `ops.setting_confirm` sends the `PUT` of rule 12.
14. With `durable` false, the muted line `ops.settings_in_memory` stands under
    the card's title.

### Look

- The card, its rows, the source tag, the question and the phone layout:
  `_design/pages.md`, « Plain pages: account, shared recap, operator ».

## Acceptance criteria

- **AC-1** With no variable and no override, `creator_room_hours` answers
  `value` 720, `source` `default`, `environment` and `override` null; with
  `NOCK_CREATOR_ROOM_HOURS` 48, `value` 48, `source` `environment`,
  `environment` 48; after a `PUT` of 96, `value` 96, `source` `override`,
  `environment` 48, `override` 96; a `PUT` of 48 still gives `source`
  `override`.
- **AC-2** With the token, `GET /api/ops/settings` lists the five settings in
  rule 1's order with their nine fields, the lives `unit` `hours`, `min` 24,
  `max` 8760, `default` 720, the interval `unit` `minutes`, 1, 1440, 60;
  `durable` is true on a database file and false in memory.
- **AC-3** `PUT {"name": "anonymous_room_hours", "value": 48}` answers 200 with
  the list, that row 48 and `override`, the four others as before; the next
  `GET` reads the same.
- **AC-4** With `NOCK_ANONYMOUS_ROOM_HOURS` 48 and an override of 96,
  `{"value": null}` answers 200 with `value` 48, `source` `environment`,
  `override` null; without the variable, 720 and `default`; a reset of a
  setting with no override answers 200 and changes nothing.
- **AC-5** `creator_room_hours` 23, 8761, 24.5 and `"24"`,
  `expiry_sweep_minutes` 0 and 1441, the name `room_hours`, and a body with no
  `value` each answer 422, and the next `GET` is unchanged.
- **AC-6** Anonymous rooms A (last edited 50 h ago, a socket open), B (30 h) and
  C (solved 30 h ago) under `anonymous_room_hours` 48: the dry run of 24 answers
  `{"rooms": 2}`, of 96 `{"rooms": 0}`; A's socket stays open, no room is gone,
  and the `GET` after shows no override.
- **AC-7** With `NOCK_ANONYMOUS_ROOM_HOURS` 24 overridden to 720 and B of AC-6
  present, the dry run of `{"value": null}` answers `{"rooms": 1}`; the dry run
  of `expiry_sweep_minutes` 30 answers 422.
- **AC-8** Each of the three routes without a token gets rule 8's 401 and
  counts: after 10, the right token on the dry run gets 429; a 422 on `PUT`
  counts nothing. Their 200, 401, 422 and 429 and `DELETE /api/ops/settings`
  (405) carry `no-store`; with the variable unset, the three answer as
  `/api/xyz/dashboard`.
- **AC-9** On a database file, a `PUT` of `creator_room_hours` 48 then a second
  app on the same file: its `GET` reads 48, `override`, `durable` true, and
  its registry's config 48. In memory, a new app reads 720 and `default`.
- **AC-10** With the rows (`room_hours`, 48), (`creator_room_hours`, 23),
  (`anonymous_room_hours`, `"abc"`) and (`anonymous_solved_room_hours`, 48) in
  `overrides` before the start, the app starts, logs three WARNING records of
  `nock.overrides` naming those rows, keeps only the last row, and its config
  reads `anonymous_solved_room_hours` 48 and `creator_room_hours` 720.
- **AC-11** With the lives at 720, anonymous room A last edited 30 h ago is
  served by a lookup; after `PUT anonymous_room_hours 24`, the registry's
  config reads 24 and a lookup half a second later deletes A, its socket
  closed with 4404; the other four values of the config are unchanged.
- **AC-12** With the sweep interval long, `PUT anonymous_room_hours 24` leaves A
  of AC-11 in the store with its socket open until a lookup or a sweep; with
  the registry's interval a short float, the sweep after the `PUT` deletes A.
  `PUT expiry_sweep_minutes 2` makes the config's `expiry_sweep_seconds` 120.
- **AC-13** With `NOCK_CREATOR_ROOM_HOURS` 24, the `PUT` of 48 logs one INFO
  record of `nock.overrides` holding `creator_room_hours`, 24 and 48 and not
  the token; the reset logs one holding 48 and 24; a 422 logs none.
- **AC-14** With the default lives, after `PUT anonymous_solved_room_hours 100`
  the dashboard answers `offered_days` `[1]` and `days` 1, and `?days=7` 422;
  after the reset, `[1, 7, 30]` and `days` 7.
- **AC-15** `ready`, the card « Durées de vie des salons » lists « Salon d'un
  compte, résolu », « Salon d'un compte, en cours », « Salon anonyme, résolu »,
  « Salon anonyme, en cours » with « 720 h » and « par défaut », then
  « Intervalle de nettoyage » « 60 min » « par défaut », « Rétablir » disabled;
  with `NOCK_CREATOR_ROOM_HOURS` 48, its row reads « 48 h » « variable ».
- **AC-16** Typing 96 in that row and « Enregistrer » sends the `PUT`, with no
  question: the row reads « 96 h » « modifiée », the input is empty and
  « Rétablir » enabled. With 100 in « Salon anonyme, résolu » (at 720) and
  « Enregistrer », rule 12 asks « Cela effacera 0 salon maintenant. » first;
  after « Confirmer » the period chips are « Dernières 24 heures » alone,
  pressed. « Rétablir » there asks no question and brings the three chips
  back and the row to « 720 h » « par défaut ».
- **AC-17** With AC-6's rooms, 24 in « Salon anonyme, en cours » (at 48) and
  « Enregistrer » saves nothing and shows, under a divider, « Cela effacera 2
  salons maintenant. », « Confirmer » and « Annuler », the button pressed;
  « Annuler » closes it, the row unchanged; « Confirmer » saves: « 24 h »
  « modifiée ». One room reads « Cela effacera 1 salon maintenant. ».
- **AC-18** 23 or 8761 in a life's row and « Enregistrer » shows « Valeur hors
  limites (24 à 8760 h). » under the input, an alert, and sends nothing; 0 in
  the interval's shows « Valeur hors limites (1 à 1440 min). »; 30 there saves
  at once, « 30 min » « modifiée », no question.
- **AC-19** In memory, the card holds « Sans base de données, ces réglages sont
  perdus au redémarrage. » under its title; on a file, no such line. While the
  settings load, the card holds « Chargement… » only; a 500 gives
  « Impossible de charger les données. » as an alert.
- **AC-20** Tab reaches each row's input and buttons and Enter in an input
  saves; the question open, Tab reaches « Confirmer » then « Annuler »; each
  shows the focus ring; the contrast and language scans find nothing with the
  question open, on a computer and on a phone, where each row stacks and no
  window scrolls sideways.

## Edge cases

- An override equal to the variable's value is still an override (AC-1).
- A save equal to the row's effective value asks no question (AC-16).
- A registry given with an interval that is a fraction of a minute answers
  that fraction as the interval's `environment` value (AC-2).
- A reset with no override logs a record with equal old and new values
  (AC-13).

## Out of scope

- Overriding another setting; several processes sharing overrides
  (`platform/server.md`); a history of overrides (between two tabs the last
  save wins); undoing a deletion the override caused.
- The token, the throttle and the page's states: `admin/operations.md`. What
  expiry and the sweep do: `lobby/lifetime.md`.

## Code

- `src/nock/overrides.py`; `src/nock/server.py`: the three routes, the start;
  `src/nock/store.py`: the table; `src/nock/hub.py`: the config swap.
- `web/src/lib/OpsSettings.svelte`, `OpsPage.svelte`, `ops.ts`.
- Tests: `tests/test_overrides_*`.
