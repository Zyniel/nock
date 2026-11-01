---
id: B-024
title: /ops overrides of the room lives
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:overrides
  - domain:operations
  - domain:lifetime
dependencies: []
ordinal: 34000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved the brief as written, with the lead's
  calls, and picked A for the INFO log, then the spec change as written with
  the lead's calls, 2026-10-29; the dry run's count and AC-16's wording fixed
  on the human's word; built and reviewed in two rounds, 2026-10-29)
- Waits for: nothing left (B-023 is merged and on this branch).
- Domains: admin/overrides (new), admin/operations (its token and throttle
  rules cover the new routes; the periods read the effective lives),
  lobby/lifetime (its rules read the effective value), product (the stable
  routes); `specs/_map.md` (a table row, the glossary), `_settings.md`,
  `_design/pages.md` « Plain pages: account, shared recap, operator »; the
  screens sheet, the `/ops` part
- Architecture decision: yes (a new domain file, new stable routes, stored
  data, the first write in the ops API). The Plan agent on Fable weighed the
  options for the first brief of this request and the human picked them; no
  new Plan run.
- Criteria: overrides AC-1 to AC-20 (new); operations, lifetime, product:
  no criterion changed (rules only)
- Branch: feat/b-024-ops-overrides · PR: #64
- Problem: the room lives and the sweep interval are environment variables
  (`lobby/lifetime.md` rules 4, 7), so changing one means a restart, and the
  operator cannot see how many rooms a shorter life would delete.
- In scope, the human's request as written (2026-10-28):
  - Glossary terms: default value (built in); environment value (the
    variable's, when set); override (a value saved from `/ops`, stored in the
    database, in memory when `NOCK_DATABASE` is unset); effective value (the
    override, else the environment value, else the default; every rule reads
    it); dry run (how many rooms a proposed value would delete now, nothing
    saved).
  - The operator page gets a section listing the four room lives and the
    sweep interval, each with its effective value and its source (default,
    variable, override).
  - The operator can save an override within the same bounds, or reset it to
    the environment value.
  - `GET /api/ops/settings` reads them, `PUT /api/ops/settings` saves one,
    and a dry run gives the count without saving, all behind the operator
    token and its throttle.
  - Saving a shorter room life asks for confirmation with the dry run's count.
  - An override applies at once (lookups and the next sweep use it) and is
    logged at INFO with its name, old and new value, never the token.
  - The dashboard periods follow the effective shortest room life.
- Out of scope (the human's): overriding other settings. Also: several app
  processes sharing overrides (`platform/server.md` leaves them out); a
  history of overrides (between two operator tabs, the last save wins);
  splitting `operations.md`.
- Size: four domain files, kept as one change: `lifetime.md` and
  `product.md` get one line each, and `operations.md` changes in place with
  no new criterion (it is at about 18.8 KB and 20 criteria).
- Already decided by the human (every pick A of the first brief of this
  request, 2026-10-28):
  1. **Where:** a new domain file **`admin/overrides.md`** holds the
     effective value, the routes, the storage, the log and the page section;
     its tests are `tests/test_overrides_*.py`. `operations.md` keeps the
     token, the throttle and rules 6, 8 to 10, which also cover the new
     routes.
  2. **API:** `GET /api/ops/settings` answers the five settings, each with
     its name, effective value, source, default, environment value,
     override, bounds and unit, and `durable` (whether a database file holds
     the overrides). `PUT /api/ops/settings {"name", "value"}` saves one,
     `value: null` resets it, and answers the same list.
     `POST /api/ops/settings/dry-run` with the same body answers
     `{"rooms": n}`; it takes only the four lives (the sweep interval deletes
     nothing), and a reset's dry run uses the value the reset falls back to.
     An unknown name or a value out of bounds answers 422.
  3. **Storage:** one table `overrides (name, value)` in the room store,
     untouched by room deletion, in memory when `NOCK_DATABASE` is unset. At
     start a stored override with an unknown name or a value out of bounds is
     dropped with one WARNING; the start never fails over it. An override
     outranks the variable even if the variable changed since; the page shows
     the variable's value beside it. Without a database file the card shows
     the muted line « Sans base de données, ces réglages sont perdus au
     redémarrage. »
  4. **Applying at once:** the registry swaps its config under its lock; the
     next lookup uses the new value; the sweep uses it on its next run, and a
     new interval starts after the current wait. Saving does not sweep.
  5. **Dashboard periods:** see "New since the first brief".
  6. **Screen:** one card « Durées de vie des salons » under the dashboard,
     five rows (« Salon d'un compte, résolu », « Salon d'un compte, en
     cours », « Salon anonyme, résolu », « Salon anonyme, en cours »,
     « Intervalle de nettoyage »), each with its value (« 720 h »,
     « 60 min »), a source chip (« par défaut », « variable », « modifiée »),
     a number field, « Enregistrer » (primary) and « Rétablir » (quiet). The
     confirmation is the account page's disclosure pattern inside the card,
     under a divider: « Cela effacera N salons maintenant. », « Confirmer »
     (primary), « Annuler »; no red button. A value out of bounds shows
     « Valeur hors limites (24 à 8760 h). » On a phone each row stacks.
- Screens: `/ops` gains that card (`_design/pages.md`, screens sheet part 7,
  in both layouts, with the confirmation open in one of them).
- New since the first brief (the lead's calls; say if any should change):
  - **Dashboard periods (pick 5 replaced):** B-023 already made the
    dashboard answer name its offered periods (`offered_days`,
    `admin/operations.md` rule 12). Pick 5's `period_limit_days` is dropped;
    `offered_days` and the default period are computed from the effective
    lives, so a saved override changes them at the next dashboard request.
  - **Settled by B-023:** the dry run calls B-023's one expiry function
    (`is_room_expired`) over the stored room times, which hold the kind and
    the solve time; the expired-room line already names no duration. These
    two open questions of the first brief are closed.
  - **What the dry run counts:** every room the proposed value would delete
    now, including any already due under the current value (the lead's
    default in the first brief), so the count matches what the next sweep
    would do.
  - **Throttle and cache:** the new routes follow `operations.md` rules 8 to
    10: only a 401 counts toward the throttle, a 422 never does, and every
    answer has `Cache-Control: no-store`.
  - **Environment value of an app given a registry** (the tests'
    `create_app(rooms=...)`): its config stands in for the environment
    values, as `lobby/lifetime.md` rule 7 already reads no variable then.
  - **Lowering the sweep interval** asks no confirmation: it deletes nothing
    by itself.
- Open questions:
  1. **The INFO record is not printed by `python -m nock`.** `product.md`
     rule 27 runs the server at `warning`, so an override logged at INFO, as
     the request says, reaches only a host that sets up logging (and the
     tests). Options:
     - **A (lead's default): INFO as asked, runner unchanged.** The spec says
       so; no baseline changes.
     - B: log the override at WARNING, so the default runner prints it. It
       departs from the request's word, but the operator sees every change.
     - C: run the server at `info`. A baseline change: the runner would then
       print every INFO record of `nock.*` and uvicorn's start lines too.
- Answers (the human, 2026-10-29): "Approve and pick A": the INFO record as
  asked, the runner unchanged, and the spec says so.
<!-- SECTION:DESCRIPTION:END -->
