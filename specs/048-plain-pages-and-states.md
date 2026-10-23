---
id: "048"
title: Plain pages and states
status: approved
---

# 048 - Plain pages and states

Epic E10 Quality bar · Release: MVP · No backlog story: this is the "plain pages and
states" part of build step 5 of `specs/_design.md` (section 14; `docs/build-plan.md`
Phase 7, order 8, the last). It applies `_design.md` section 8 "Plain pages:
account, shared recap, operator" and "States: opening, loading, empty, error" (for
the pages of this spec), section 8 "Entry and not-found pages" and section 10 for
the two frames these pages sit in, section 11 (card, field, text input, error line,
confirmation line, text link, filter chip, slider, destructive action), and the
parts of sections 2, 4 and 6 (the cells of the operator's replay) that these pages
use. It builds on spec 041 (tokens, fonts, `nock-button`), spec 042 (the cell look),
spec 046 (the entry-page frame and the catalogue's frame) and spec 047 (the recap's
states), and redefines none of them; where it changes one of their rules, "Refined
specs" says so. The FX-01 reference grid is in `specs/_reference.md`; the stack in
`specs/_architecture.md`.

## Goal

Three pages of Nock are still drawn with browser defaults: the account page
`/account` (spec 033), the page a shared recap link opens, `/recap/<token>` (spec
028), and the operator's page `/ops` (spec 038). The human decided their look on
2026-10-22 (screens sheet P11, P12, P14, P15, D1): each is one or a few white cards on
the page grey, in a frame the player already knows, with no red button. The human
also decided one rule for every waiting, empty or failed state (P2, P4, P10): a
state is one line of text where its content will be, muted while waiting or empty,
red when something failed, green when done; no spinner, no skeleton. This spec draws
the three pages, gives each of their states that one line, and checks that no
spinner exists anywhere in the client. The rule of the human holds: the simplest
design that removes edge cases.

## Public interface

No new Python name, no new protocol message, no new HTTP route, no new `fr.json`
key. Client only (`web/`: chiefly `web/src/lib/AccountPage.svelte`,
`web/src/lib/AccountEmailForm.svelte`, `web/src/lib/SharePage.svelte`,
`web/src/lib/OpsPage.svelte`, `web/src/lib/OpsReplay.svelte`, `web/src/lib/ops.ts`).
Every colour is a token of spec 041 used for its job in `_design.md` section 2,
every string comes from `web/src/i18n/fr.json`.

### Terms

- Entry-page frame (spec 046; `_design.md` section 8 "Entry and not-found pages"):
  the page's `header`, with the Nock mark and « Nock » only, 54 px high on a phone
  and 56 px on a wider window; under it the page on `--nock-page`, holding one column
  of cards, gap 14 px: on a phone padding 20 px 16 px, so the column is the window's
  width less 32 px; on a wider window the column is at most 420 px wide, centred,
  its top 48 px under the `header`. No room code line on the pages of this spec.
- Catalogue frame (spec 046; `_design.md` section 10): the page's `header`, 56 px
  high, with the Nock mark and « Nock » only on the operator page (no « Compte »);
  under it the page on `--nock-page`, holding the main column: at most 920 px wide,
  centred, padding 24 px (16 px on a phone), gap 16 px.
- "Phone" and "wider window" are spec 046's split. The criteria of this spec measure
  at 360 by 740 (a phone) and at 1280 by 720 (a wider window) only, so they hold
  whichever threshold spec 046 picks.
- Card (`_design.md` section 11): `--nock-white`, a 1 px solid `--nock-line` border,
  radius 10 px, padding 18 px 16 px, its parts in a column with gap 12 px, each
  aligned to the card's left (they do not stretch, except fields and URL boxes,
  which take the card's width). Card title: 700 1.25rem/1.2, `--nock-navy`, margin
  0. Card text: 400 0.95rem, `--nock-ink`. Card secondary text: 400 0.85rem,
  `--nock-muted`.
- Field (`_design.md` section 11): its label above its input, gap 6 px, the label in
  600 0.85rem/1.2 `--nock-ink`; the text input with a 1 px solid `--nock-rule`
  border, radius 6 px, padding 10 px 12 px, 400 1rem/1.2, `--nock-ink` on
  `--nock-white`, as wide as the card's content; in error, the border
  `--nock-red`.

### State lines (`_design.md` section 8 « States »; P2, P4, P10)

One rule for every waiting, empty, failed or done state of the pages of this spec,
in place of the content it stands for:

| Kind | Look | Role |
| --- | --- | --- |
| Waiting (loading, signing in) | 400 0.95rem, `--nock-muted` | `role="status"` |
| Empty (nothing to show) | 400 0.95rem, `--nock-muted` | none |
| Error (something failed or was refused) | the error line: 500 0.85rem/1.3, `--nock-red` | `role="alert"` |
| Done (a confirmation) | the confirmation line: 500 0.85rem/1.3, `--nock-green` | `role="status"` |

A state line is one text element. The client has no spinner and no skeleton: no
`<progress>` element, no `role="progressbar"`, and no CSS animation (`@keyframes`,
`animation`), on any page. Transitions (spec 041's note fade) are not animations.

Where each state of the client is drawn:

| Screen | States | Spec |
| --- | --- | --- |
| Shared recap page, account page, operator page | below | this spec |
| The recap dialog | loading, unavailable | 047 |
| The opening room, the catalogue, « Mes salons », the history, a failed « Jouer » | P2, P4 | 046 |
| The account sheet in a room or on the catalogue | sent, refused | 043, 046 |

### Shared recap page `/recap/<token>` (`_design.md` section 8, spec 028, P11)

`recap-page` (spec 028: it opens no socket, stores nothing, fetches
`GET /api/recaps/<token>`) is the entry-page frame holding one card,
`data-testid="share-card"`:

- While loading: the card holds only `recap-loading` (`t("recap.loading")`), a
  waiting line.
- Loaded: the `h1` (`t("share.heading")`) as the card title; `share-grid` (when
  `grid_number` is not null) in card secondary text; `share-time` in the recap time
  style of `_design.md` section 4 (700 2.1rem/1, `--nock-navy`, tabular);
  `share-team` in card text; `share-home`, the link to `/` (spec 028), drawn as a
  primary button (spec 041's `nock-button nock-button-primary` look: navy background,
  white text, radius 6 px, padding 10 px 16 px, 600 0.95rem/1, no underline).
- Unavailable (the request failed): the card holds `share-error`
  (`t("share.error")`) as its title, an `h1` in the card title style (it is the
  page's heading, `_design.md` section 8: "the same card with the title « Ce bilan
  n'est pas disponible. »"), then `share-home` as above. (Refines spec 028: the
  error was a paragraph with no way on.)

### Account page `/account` (`_design.md` section 8, spec 033, P12, D1)

`account-page` (spec 033: its root, its `data-state`, its requests and rules) is the
entry-page frame holding one card, `data-testid="account-card"`, whose title is the
page's `h1` (`t("account.page_heading")`, « Mon compte »). After the title, by
`data-state`:

| `data-state` | The card holds, after its title |
| --- | --- |
| `loading` (while `GET /api/account` runs, before any other state) | nothing (Decision 3) |
| `signing_in` | `data-testid="account-state-line"`, a waiting line, `t("account.signing_in")` |
| `signed_in` | `account-email` (card text); `account-room-link` when spec 033 shows it, a text link (`--nock-navy`, weight 600); `data-testid="account-actions"`, a row that wraps, gap 8 px, holding `account-sign-out` then `account-delete`, both `nock-button nock-button-secondary`; then, while deletion is asked, `data-testid="account-delete-panel"` (below) |
| `link_invalid` | `account-state-line`, an error line, `t("account.link_invalid")`, above the e-mail form |
| `signed_out` | `t("account.signed_out_intro")` in card text, then the e-mail form |
| `deleted` | `account-state-line`, a done line, `t("account.deleted")`; then `data-testid="account-home"`, a link to `/` with `t("share.home")` (« Voir les grilles »), drawn as a primary button |
| `error` | `account-state-line`, an error line, `t("account.error.generic")` |

Deletion, asked once more in the same card (P12, D1; refines spec 033's "Account
page"):

- `account-delete` is a disclosure: `aria-expanded` `"false"`, and `aria-controls`
  naming `account-delete-panel`. A click shows the panel and sets `aria-expanded` to
  `"true"`; while it is `"true"`, `account-delete` has the quiet look (`nock-button
  nock-button-quiet`: `--nock-word` background, navy text, transparent border). A
  second click hides the panel, as `account-delete-cancel` does.
- `account-delete-panel`: a 1 px solid `--nock-line` top border, padding-top 12 px,
  as wide as the card's content, holding `account-delete-warning`
  (`t("account.delete_warning")`) in card text (`--nock-ink`), then a row that wraps,
  gap 8 px, 12 px below it: `account-delete-confirm` (`nock-button
  nock-button-primary`) then `account-delete-cancel` (`nock-button
  nock-button-secondary`). Spec 033's rules hold: only the confirm sends
  `DELETE /api/account`.
- No element of the page is red except an error line: no button has a
  `--nock-red` background, border or text (`_design.md` section 11, "Destructive
  action").

The e-mail form (`account-email-form`, spec 033, shared with spec 043's account
sheet): the field `t("account.email_label")` with `account-email-input`, then
`account-email-submit` (`nock-button nock-button-primary`), 12 px below the field.
(Note from the lead, 2026-10-22: since spec 043's build, `account-email-submit` in
`web/src/lib/AccountEmailForm.svelte` already has the classes `nock-button
nock-button-primary`, on the account page as in the room's account sheet, as the
screens sheet draws it; this spec keeps that class and adds the place and the
states, it does not change the button's look.)
After a 202, `account-sent` is a done line under the submit button; after a 422,
`account-email-input` has `aria-invalid="true"` and the red border, and
`account-error` is an error line under the field, above the button; after a 429 or
another failure, `account-error` shows the same way, with no red border (the address
is not at fault). A new submit clears both.

### Operator page `/ops` (`_design.md` section 8, spec 038, P14, P15)

`ops-page` (spec 038: its root, its `data-state`, its rules, its requests) is the
catalogue frame. Its main column holds the `h1` (`t("ops.heading")`) in the
catalogue heading style (700 1.7rem/1.1, `--nock-navy`, margin 0), then by
`data-state`:

- `locked`: `ops-token-form` drawn as a card: the field `t("ops.token_label")` with
  `ops-token-input` (a password input); while `ops-token-error` shows, the input has
  `aria-invalid="true"` and the red border, and `ops-token-error` is an error line
  under the field; then `ops-token-submit` (`nock-button nock-button-primary`).
- `loading`: `data-testid="ops-state-line"`, a waiting line, `t("ops.loading")`.
- `error`: `ops-state-line`, an error line, `t("ops.error")`.
- `ready`: two cards, `ops-dashboard` then `ops-replay`.

`ops-dashboard`, a card:

- Its `h2` (`t("ops.dashboard_heading")`) in the card title style.
- `data-testid="ops-period-field"`: the label `t("ops.period_label")` (field label
  style) above the group of the three `ops-period` buttons (spec 038's group,
  labelled by that label with `aria-labelledby`), a row that wraps, gap 8 px. Each
  `ops-period` is a filter chip of `_design.md` section 10: radius 16 px, padding
  7 px 14 px, a 1 px solid `--nock-line` border, `--nock-white` background,
  `--nock-navy` text, 600 0.9rem/1; the pressed one (`aria-pressed="true"`) a
  `--nock-word` background and a `--nock-navy` border.
- The six `ops-metric` items (spec 038's text and data attributes, its list) as
  tiles: the list is a grid of `repeat(auto-fill, minmax(min(100%, 270px), 1fr))`,
  gap 10 px, as wide as the card's content; each tile `--nock-white`, a 1 px solid
  `--nock-line` border, radius 8 px, padding 12 px 14px, holding spec 038's text as
  it is, in card text.

`ops-replay`, a card:

- Its `h2` (`t("ops.replay_heading")`) in the card title style.
- `ops-replay-form`: a row, items aligned to their bottom, gap 8 px, that wraps: the
  field `t("ops.replay_code_label")` with `ops-replay-code`, taking the width left
  (at least 140 px), then `ops-replay-submit` (`nock-button nock-button-primary`).
- By its `data-state` (spec 038): `idle` nothing more; `loading`
  `data-testid="ops-replay-state-line"`, a waiting line, `t("ops.loading")`;
  `not_found` the same element, an error line, `t("ops.replay_not_found")`; `error`
  the same element, an error line, `t("ops.error")`; `ready` with no edit, the same
  element, an empty line, `t("ops.replay_empty")`, and nothing else (no edit list, no
  slider, no grid; refines spec 038, Decision 5); `ready` with edits, the replay
  below.
- The replay, two forms (Decision 6):
  - Two columns, when `window.innerWidth >= 900`: `data-testid="ops-replay-body"`, a
    grid of two columns, `1fr` and `auto`, gap 20 px, items aligned to their top: on
    the left `ops-edits`, on the right a column (gap 10 px) of `ops-replay-grid`,
    then `ops-replay-position-field`, then `ops-replay-step`.
  - One column otherwise: `ops-replay-grid`, `ops-replay-position-field`,
    `ops-replay-step`, then `ops-edits`, top to bottom, gap 10 px.
- `data-testid="ops-edits"`, the `ol` of spec 038's `ops-edit` items (`role="list"`,
  no numbers, no bullets): gap 4 px, 400 0.85rem, `font-variant-numeric:
  tabular-nums`; each item padding 4 px 8 px, radius 4 px, with `data-step`, for the
  position `k` (spec 038's slider value) and the item's index `i` from 1:
  `"done"` (`i < k`: `--nock-ink`, no background), `"current"` (`i = k`:
  `--nock-word` background, weight 600, `--nock-ink`), `"later"` (`i > k`:
  `--nock-muted`). At `k = 0` every item is `"later"`.
- `ops-replay-grid` (spec 038's group and label): the cells of `_design.md` section 6
  at the chosen step, with no clue text, no arrows and no players (Decision 7):
  - one cell per grid cell, in rows and columns; the grid has a 1 px solid
    `--nock-rule` left and top border, and each cell a 1 px solid `--nock-rule`
    right and bottom border inside its side `s`;
  - the side `s` in px: `min(c, floor((w − 1) / W))`, `W` the grid's width in cells,
    `c` 44 in the two-column form and 36 in the one-column form, `w` the width the
    grid may take (the card's content width, less 20 px and 240 px in the two-column
    form);
  - a letter cell is `ops-replay-cell` (spec 038's attributes) on `--nock-white`; a
    clue cell is `data-testid="ops-replay-block"` with `data-type="clue"` on
    `--nock-clue-bg`, with no text; an empty cell (spec 002) is `ops-replay-block`
    with `data-type="empty"` on `--nock-rule`;
  - the state of a letter cell after the first `k` edits, from the edits on it among
    them (refines spec 038's replay grid): `data-letter` and the shown letter as spec
    038 says; `data-locked="true"` when one of them is of kind `locked` or
    `revealed`, else `"false"`; `data-revealed="true"` when one of them is of kind
    `revealed`, else `"false"`; `data-pencil="true"` when the last of them is of kind
    `typed` or `undone` with `pencil` true and the cell is not locked, else
    `"false"`;
  - the letter: `--nock-font-ui`, 0.56 s, line height 1, weight 500, `--nock-ink`,
    centred; a pencil letter italic in `--nock-pencil`; a locked cell
    `--nock-locked` with the letter in weight 700; a revealed cell, locked, plus the
    revealed notch of spec 042 (an orange-red triangle, `--nock-reveal`, base
    `max(7px, 0.22 s)`, height `max(4px, 0.11 s)`, centred on the bottom edge,
    `aria-hidden`).
- `data-testid="ops-replay-position-field"`: the label `t("ops.replay_position_label")`
  (field label style) above the slider, as wide as the column that holds the grid
  (the grid's width in the two-column form, the card's content in the other). The
  slider (`_design.md` section 11, P15; Decision 8): `ops-replay-position` stays the
  native range input of spec 038 (its role, keys, label, minimum, maximum, step and
  value), 18 px high, as wide as its field, transparent (`opacity: 0`), laid over
  three `aria-hidden` elements that draw it:
  - `data-testid="ops-replay-track"`: 6 px high, radius 3 px, `--nock-word`, as wide
    as the input, centred on its height;
  - `data-testid="ops-replay-fill"`: `--nock-navy`, radius 3 px, the track's height,
    from the track's left edge to the knob's centre;
  - `data-testid="ops-replay-knob"`: an 18 px `--nock-navy` circle whose centre is
    at `x = left + 9 + (width − 18) × k / m` of the input's box (`m` the maximum), on
    the input's vertical centre; while the input has `:focus-visible`, the knob has
    the focus ring of `_design.md` section 11 (`2px solid var(--nock-navy)`, offset
    2 px).
- `ops-replay-step` (spec 038's text) in card secondary text, as wide as its text,
  on the left edge of the column that holds the grid (Note from the lead,
  2026-10-23: added, the screens sheet draws it so; this line gave no width).

### Refined specs

Each refined spec carries a dated note "(Note from the lead, 2026-10-22: refined by
spec 048, the design's plain pages and states ...)" and keeps its status. The
test-writer updates the tests of the criteria named here before the implementer
runs.

| Spec | Criteria that change | What changes in their tests |
| --- | --- | --- |
| 028 | none | "Client: the public recap page": `share-error` is the card's `h1` and `share-home` shows with it; its tests read `share-error`'s text, which is unchanged |
| 033 | none | "Account page": the card, the `loading` state, `account-delete` as a disclosure, the panel, `account-home` after deletion, the red border after a 422; AC-5 and AC-9 read texts, states and scans, which hold |
| 038 | none | "Client: the ops page": the cards, the state lines, the replay's two forms, `data-step`, the cells' `data-locked`, `data-revealed`, `data-pencil` and `ops-replay-block`, a replay with no edit showing its line only; AC-7 and AC-9 read texts, positions and attributes that hold (AC-9's room has edits) |

Spec 035 gets a note and no criterion change: the three pages keep its rules (Tab
reaches every control, visible focus, labels from `fr.json`, 4.5:1), which AC-14
checks; the drawn slider keeps the native input as the control, so its role, name
and keys are the browser's.

### Test harness

- Shared recap page: as spec 028 AC-10's share-page test (the page opened on
  `/recap/tok_ABCDEFGHIJKLMNOP` with its API route answered by `page.route`), with
  `PUBLIC = PublicRecap(grid_number=12, elapsed_ms=754000, team=("ANA", "BOB"))`
  unless a criterion says otherwise.
- Account page: as spec 033 AC-9's mocked routes (`page.route("**/api/account", ...)`,
  `**/api/account/sign-in`, `**/api/account/link`, `**/api/account/sign-out`,
  `DELETE **/api/account`), the page opened on `/account`, with
  `ana.probe@example.org`; a sign-in through `/account#<43 characters>` answered
  with a `SignInResult` whose `room_code` is `K7QM2X`.
- Operator page: as spec 038 AC-7's mocked ops API
  (`page.route("**/api/ops/dashboard*", ...)` with AC-5's 7-day figures,
  `page.route("**/api/ops/rooms/*/edits", ...)`), `sessionStorage["nock.ops_token"]`
  seeded with `OPS_TOKEN` by `context.add_init_script` where a criterion opens the
  page `ready`, `timezone_id="Europe/Paris"`. `REPLAY`: a `RoomReplay` of code
  `K7QM2X` with `grid_view(fx01_grid)` and the edits, in seq order: `typed` `T` at
  (1, 0) by `p1` (`ANA`); `typed` `A` at (1, 1) by `p1`; `typed` `M` at (1, 2) by
  `p2` (`BOB`); `typed` `D` at (2, 3) by `p2` with `pencil` true; `locked` `M` at
  (1, 2); `revealed` `N` at (3, 4); `typed` `S` at (1, 4) by `p1`. `REPLAY_FX02`: the
  same with `grid_view` of `tests/fixtures/fx02.json` and one `typed` edit at
  (0, 2), FX-02's first letter cell (Note from the lead, 2026-10-23: this read "at
  (1, 0)", which is a clue cell of FX-02). `REPLAY_EMPTY`: `REPLAY` with no edit.
- Window sizes: 360 by 740 and 1280 by 720, desktop context, unless a criterion
  says otherwise; "every size" is the eight of spec 006 AC-5.
- Positions are bounding boxes; tolerances 1 px for a position, 0.5 px for a size,
  0.1 px for a font size or a line height, unless a criterion says otherwise.
  Colours as spec 041 (`parseColour`, exact channels for a token).
- Fonts: spec 041's rule (wait for `document.fonts.ready` before reading a size or a
  position that depends on text).
- Static criteria read files with Python only, as spec 041's colour scans: comments
  removed, the client sources `web/src/**/*.svelte`, `*.ts` and `*.css`, and the
  built CSS under `web/dist/assets/` (spec 041's message when `web/dist/index.html`
  is missing).
- Engines: Chromium and WebKit locally, Firefox too in CI. No check is
  Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new; refines spec 028's share page look) (browser with mocked routes) The shared recap is one card on the page grey, with the time in the recap's large style. With `PUBLIC`, at 360 by 740: the page's `header` is 54 px high and 360 px wide at the window's top, holding the Nock mark (an `svg` whose `polygon` has the `points` `0,0 10,0 10,14 5,10 0,14` and the `fill` rgb(27, 47, 85)) and the text `fr.json["app.title"]`, and no `button`; the page under it has `background-color` rgb(246, 247, 249); `share-card` has its left edge 16 px from the window's left, its width 328 px and its top 20 px under the `header` (1 px), `background-color` rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `10px`, padding `18px 16px`. At 1280 by 720: the `header` is 56 px high; `share-card` is 420 px wide, centred (its left edge 430 px from the window's left, 1 px), its top 48 px under the `header`. In both: `share-card` holds in order the `h1` (`fr.json["share.heading"]`, `font-size` 20 px, weight 700, colour rgb(27, 47, 85)), `share-grid` (`Grille n° 12`, `font-size` 13.6 px, colour rgb(94, 101, 115)), `share-time` (`Temps : 12:34`, `font-size` 33.6 px, weight 700, colour rgb(27, 47, 85), `font-variant-numeric` `tabular-nums`), `share-team` (`Équipe : Ana, Bob`, `font-size` 15.2 px, colour rgb(20, 24, 31)) and `share-home`, each the next one's top 12 px or more above (1 px); `share-home` is an `A` whose `href` is `/`, with `background-color` rgb(27, 47, 85), colour rgb(255, 255, 255), `border-radius` `6px`, padding `10px 16px`, `font-size` 15.2 px, weight 600, `text-decoration-line` `none`, as wide as its text plus its padding (not the card's width). A `PublicRecap` with `grid_number` null shows no `share-grid`.
- **AC-2** (new; refines spec 028's share page states) (browser with mocked routes) While it loads the card holds one muted line, and an unavailable recap keeps the card and its way on. With the API route held unanswered, at 360 by 740 and at 1280 by 720: `recap-page` has `data-state="loading"` and `share-card` holds only `recap-loading`, reading `fr.json["recap.loading"]`, with `role="status"`, `font-size` 15.2 px and colour rgb(94, 101, 115). With the route answering 404: `share-card` holds in order `share-error`, an `H1` reading `fr.json["share.error"]` with `font-size` 20 px, weight 700 and colour rgb(27, 47, 85), then `share-home` with AC-1's look; the page holds no other `h1`.
- **AC-3** (new; refines spec 033's account page look) (browser with mocked routes) Signed in, the account card names the address, links back to the room, and puts its two actions side by side. After a sign-in through `/account#<token>` (answered with `room_code` `K7QM2X`), at 360 by 740 and at 1280 by 720: `account-page` has `data-state="signed_in"` and sits in the entry-page frame as `share-card` does in AC-1 (same `header`, page colour, card left, width and top); `account-card` has the card look of AC-1 and holds in order its `h1` (`fr.json["account.page_heading"]`, `font-size` 20 px, weight 700, colour rgb(27, 47, 85)), `account-email` (`Connecté avec ana.probe@example.org`, `font-size` 15.2 px, colour rgb(20, 24, 31)), `account-room-link` (`Retourner au salon K7QM2X`, colour rgb(27, 47, 85), weight 600) and `account-actions`, each the next one's top 12 px or more above (1 px). `account-actions` holds `account-sign-out` then `account-delete` on one line (vertical centres within 1 px, 8 px apart, 1 px), each with the secondary button's colours (background rgb(255, 255, 255), colour and border rgb(27, 47, 85)), `border-radius` `6px` and padding `10px 16px`; `account-delete` has `aria-expanded="false"` and `aria-controls` equal to the `id` the panel has once shown. At 320 by 568 both buttons lie inside the card, wrapping onto two lines if they do not fit one, and the page has no horizontal scroll.
- **AC-4** (new; refines spec 033's deletion look, D1) (browser with mocked routes) Deleting is asked once more in the same card, with no red button. From the state of AC-3, at 360 by 740 and at 1280 by 720: a click on `account-delete` gives it `aria-expanded="true"` and the quiet look (background rgb(230, 237, 249), colour rgb(27, 47, 85), a border colour with alpha 0) and shows `account-delete-panel`, below `account-actions` inside `account-card`, as wide as the card's content (1 px), with a `1px` `solid` rgb(221, 226, 234) top border and `padding-top` `12px`, holding `account-delete-warning` (`fr.json["account.delete_warning"]`, `font-size` 15.2 px, colour rgb(20, 24, 31)) then `account-delete-confirm` (primary: background rgb(27, 47, 85), colour rgb(255, 255, 255)) and `account-delete-cancel` (secondary colours), side by side 8 px apart, their top 12 px below the warning's bottom (1 px). No element inside `account-page` has a computed `background-color`, `border-top-color` or `color` of rgb(180, 35, 24). A click on `account-delete-cancel` hides the panel and gives `account-delete` `aria-expanded="false"` and the secondary colours again; a second click on `account-delete` shows the panel, and a third hides it. A click on `account-delete-confirm` sends one `DELETE /api/account` (spec 033); with it answered 204, `account-page` has `data-state="deleted"` and `account-card` holds, after its `h1`, `account-state-line` reading `fr.json["account.deleted"]` with `role="status"`, `font-size` 13.6 px, weight 500 and colour rgb(30, 123, 69), then `account-home`, an `A` whose `href` is `/`, reading `fr.json["share.home"]`, with the primary look of AC-1's `share-home`.
- **AC-5** (new; refines spec 033's account states) (browser with mocked routes) Each other state of the account page is one line in the card. At 360 by 740 and at 1280 by 720: with `GET /api/account` held unanswered, `account-page` has `data-state="loading"` and `account-card` holds its `h1` and nothing else. With `/account#<token>` and the sign-in request held unanswered, `data-state="signing_in"` and the card holds, after its `h1`, only `account-state-line` reading `fr.json["account.signing_in"]` with `role="status"`, `font-size` 15.2 px and colour rgb(94, 101, 115). With the sign-in answered 404: `data-state="link_invalid"`, `account-state-line` reads `fr.json["account.link_invalid"]` with `role="alert"`, `font-size` 13.6 px, weight 500 and colour rgb(180, 35, 24), and lies above `account-email-form`. With `GET /api/account` answering signed out: `data-state="signed_out"`, the card holds after its `h1` the text `fr.json["account.signed_out_intro"]` (`font-size` 15.2 px, colour rgb(20, 24, 31)) then `account-email-form`, whose label `fr.json["account.email_label"]` (`font-size` 13.6 px, weight 600, colour rgb(20, 24, 31)) lies 6 px above `account-email-input` (1 px), which is as wide as the card's content (1 px), with a `1px` `solid` rgb(154, 163, 178) border, `border-radius` `6px`, padding `10px 12px` and `font-size` 16 px; `account-email-submit` is primary, its top 12 px below the input's bottom (1 px). After the test types `ana@` and submits, with the route answering 422: `account-email-input` has `aria-invalid="true"` and a border colour rgb(180, 35, 24), and `account-error` reads `fr.json["account.error.email"]` with `role="alert"` and the error line's look, between the input and `account-email-submit`; after a new submit answered 202, `account-error` is gone, the input's border is rgb(154, 163, 178) again, and `account-sent` reads `Lien envoyé à ana@. Il est valable 30 minutes.`, with `font-size` 13.6 px, weight 500 and colour rgb(30, 123, 69), under `account-email-submit`. A submit answered 429 shows `account-error` with `fr.json["account.error.too_many"]` and leaves the input's border rgb(154, 163, 178). With `GET /api/account` answering 500, `data-state="error"` and `account-state-line` reads `fr.json["account.error.generic"]` with the error line's look and `role="alert"`.
- **AC-6** (new; refines spec 038's ops page look) (browser with mocked ops API) The operator page sits in the catalogue's frame, and its token form is one card. Opening `/ops` with empty `sessionStorage`, at 1280 by 720: the page's `header` is 56 px high, holds the Nock mark and `fr.json["app.title"]` and no `button` and no link; the page under it has `background-color` rgb(246, 247, 249); the `h1` reads `fr.json["ops.heading"]` with `font-size` 27.2 px, weight 700, colour rgb(27, 47, 85), its left edge 204 px from the window's left (the 920 px column centred, plus 24 px, 1 px) and its top 24 px under the `header`; `ops-token-form` has the card look of AC-1, its left edge on the `h1`'s and its width 872 px (1 px), its top 16 px under the `h1`'s bottom (1 px), and holds the label `fr.json["ops.token_label"]` 6 px above `ops-token-input` (`type="password"`, the text input look of AC-5, as wide as the card's content), then `ops-token-submit` (primary). At 360 by 740 the `header` is 56 px high and the `h1`'s left edge 16 px from the window's left. After submitting `wrong` (answered 401): `ops-token-input` has `aria-invalid="true"` and a border colour rgb(180, 35, 24), and `ops-token-error` reads `fr.json["ops.token_refused"]` with `role="alert"`, `font-size` 13.6 px, weight 500 and colour rgb(180, 35, 24), between the input and `ops-token-submit`.
- **AC-7** (new; refines spec 038's loading and error look) (browser with mocked ops API) The page's waiting and failed states are one line under the heading. With the token seeded and the dashboard request held unanswered, at 360 by 740 and at 1280 by 720: `ops-page` has `data-state="loading"`, and its column holds the `h1` then `ops-state-line` only, reading `fr.json["ops.loading"]`, with `role="status"`, `font-size` 15.2 px and colour rgb(94, 101, 115), its top 16 px under the `h1`'s bottom (1 px). With the request answered 500: `data-state="error"` and `ops-state-line` reads `fr.json["ops.error"]` with `role="alert"`, `font-size` 13.6 px, weight 500 and colour rgb(180, 35, 24).
- **AC-8** (new; refines spec 038's dashboard look) (browser with mocked ops API) The periods are filter chips and each figure is a tile. With the token seeded and AC-5's 7-day figures, at 1280 by 720: `ops-dashboard` has the card look of AC-1, 872 px wide, and holds its `h2` (`fr.json["ops.dashboard_heading"]`, `font-size` 20 px, weight 700, colour rgb(27, 47, 85)), then `ops-period-field`, whose label reads `fr.json["ops.period_label"]` in the field label style and is the element that the periods' group names in its `aria-labelledby`; the three `ops-period` buttons are on one line, 8 px apart (1 px), each with `border-radius` `16px`, padding `7px 14px`, `font-size` 14.4 px, weight 600, colour rgb(27, 47, 85); the pressed one (`data-days="7"`) has `background-color` rgb(230, 237, 249) and a border rgb(27, 47, 85), the others rgb(255, 255, 255) and rgb(221, 226, 234). The six `ops-metric` tiles come three per row: the first three share one top (1 px), each about 272.7 px wide (1 px), 10 px apart (1 px), each with `background-color` rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `8px`, padding `12px 14px`, `font-size` 15.2 px, colour rgb(20, 24, 31), and spec 038's texts (`Salons créés : 3` first). At 360 by 740 the tiles come one per row, each as wide as the card's content (294 px, 1 px), and the three chips lie inside the card, wrapping if they do not fit one line; the page has no horizontal scroll.
- **AC-9** (new; refines spec 038's replay look) (browser with mocked ops API) The replay lists the edits with the current step marked, beside the grid on a wide window and under it on a phone. With the token seeded and `REPLAY` answered after a submit of `k7qm2x`: at 1280 by 720, `ops-replay` has the card look, its form holds the field `fr.json["ops.replay_code_label"]` and `ops-replay-submit` (primary) on one row, the button's bottom on the input's bottom (1 px); `ops-replay-body` holds `ops-edits` on the left and `ops-replay-grid` on the right, the grid's left edge 20 px right of the list's right edge, their tops equal (1 px); `ops-replay-position-field` is under the grid, as wide as it (1 px); `ops-replay-step` is under it, its left edge on the grid's left edge (1 px) and no wider than the grid (1 px), as wide as its text as the screens sheet draws it (Note from the lead, 2026-10-23: this read "`ops-replay-position-field` and `ops-replay-step` are under the grid, as wide as it (1 px)"; the drawing is the reference). `ops-edits` holds seven `ops-edit` items 4 px apart, each with `font-size` 13.6 px, `font-variant-numeric` `tabular-nums`, padding `4px 8px`, `border-radius` `4px`; at the position 7 (the maximum, as spec 038 loads it), items 1 to 6 have `data-step="done"`, colour rgb(20, 24, 31) and a background alpha 0, and item 7 `data-step="current"`, background rgb(230, 237, 249), weight 600; after the position is set to 4 (`fill` of `ops-replay-position` with `4`, which fires `input`), items 1 to 3 are `done`, item 4 `current`, items 5 to 7 `later` with colour rgb(94, 101, 115); at the position 0, all seven are `later`. `ops-replay-step` reads `Étape 4 sur 7` at the position 4, with `font-size` 13.6 px and colour rgb(94, 101, 115). At 360 by 740, the card holds top to bottom `ops-replay-grid`, `ops-replay-position-field`, `ops-replay-step` and `ops-edits`, each as wide as the card's content or narrower, and the page has no horizontal scroll.
- **AC-10** (new; refines spec 038's replay grid) (browser with mocked ops API) The replay's grid is drawn with the playing grid's cells, without clues, arrows or players. With `REPLAY` at the position 7, at 1280 by 720: `ops-replay-grid` has a `1px` `solid` rgb(154, 163, 178) left and top border and holds 25 cells in 5 rows of 5, each 44 by 44 px (0.5 px) with a `1px` `solid` rgb(154, 163, 178) right and bottom border; the 18 `ops-replay-cell` elements are at the letter cells of FX-01 and the 7 `ops-replay-block` elements at its clue cells, with `data-type="clue"`, `background-color` rgb(238, 242, 248) and no text; (1, 0) shows `T` with `font-size` 24.64 px, weight 500, colour rgb(20, 24, 31), `font-style` `normal`, on rgb(255, 255, 255), with `data-locked="false"`, `data-pencil="false"`; (2, 3) shows `D` with `data-pencil="true"`, `font-style` `italic` and colour rgb(85, 91, 103); (1, 2) shows `M` with `data-locked="true"`, `data-revealed="false"`, weight 700 on rgb(227, 231, 238); (3, 4) shows `N` with `data-locked="true"` and `data-revealed="true"`, weight 700 on rgb(227, 231, 238), and holds one `aria-hidden` notch 9.68 by 4.84 px (0.5 px) with `background-color` rgb(194, 65, 12), horizontally centred on the cell and its bottom on the cell's inner bottom edge (1 px); no cell holds a `clue-arrow`, a `remote-selection`, a `player-icon` or clue text. At the position 4, (1, 2) has `data-locked="false"`, (3, 4) shows nothing with `data-revealed="false"`, and (2, 3) shows `D` with `data-pencil="true"`. At 360 by 740 the cells of `REPLAY` are 36 by 36 px (0.5 px); with `REPLAY_FX02`, they are `floor((294 − 1) / 13)` = 22 px (0.5 px), the grid lies inside the card and the page has no horizontal scroll. With `REPLAY_EMPTY`, `ops-replay` has `data-state="ready"` and holds after its form only `ops-replay-state-line`, reading `fr.json["ops.replay_empty"]`, with `font-size` 15.2 px, colour rgb(94, 101, 115) and no `role`; no `ops-replay-grid`, no `ops-replay-position` and no `ops-edits` is on the page.
- **AC-11** (new; P15) (browser with mocked ops API; keyboard only for the focus part) The step slider is a word-blue track with a navy fill and knob, and stays a native range input. With `REPLAY` at 1280 by 720: `ops-replay-position` is an `INPUT` with `type="range"`, 18 px high, as wide as `ops-replay-position-field` (1 px), with computed `opacity` `0`, and `elementFromPoint` at its centre returns it; `ops-replay-track` is 6 px high, as wide as the input (1 px), vertically centred on it (1 px), with `border-radius` `3px` and `background-color` rgb(230, 237, 249); at the position 7 (maximum 7), `ops-replay-knob` is an 18 by 18 px circle (`border-radius` `50%`) with `background-color` rgb(27, 47, 85), its centre at the input's right edge less 9 px and on the input's vertical centre (1 px), and `ops-replay-fill`, `background-color` rgb(27, 47, 85), runs from the track's left edge to the knob's centre (1 px); after the position is set to 0, the knob's centre is 9 px right of the input's left edge and the fill is 0 to 1 px wide; at the position 4 the knob's centre is at `left + 9 + (width − 18) × 4 / 7` (1 px). The three drawn elements have `aria-hidden="true"`. `page.get_by_role("slider", name=fr.json["ops.replay_position_label"])` resolves to exactly `ops-replay-position`. Keyboard only: `tab_to` `ops-replay-position` gives `ops-replay-knob` a `2px` `solid` rgb(27, 47, 85) outline with `outline-offset` `2px`; `ArrowLeft` sets the position to 6 and `ops-replay-step` reads `Étape 6 sur 7`.
- **AC-12** (new; refines spec 038's replay states) (browser with mocked ops API) The replay's waiting, not-found and failed states are one line under its form. With the token seeded, after a submit of `K7QM2X`, at 360 by 740 and at 1280 by 720: with the replay request held unanswered, `ops-replay` has `data-state="loading"` and holds, after its form, `ops-replay-state-line` reading `fr.json["ops.loading"]` with `role="status"`, `font-size` 15.2 px and colour rgb(94, 101, 115); answered 404, `data-state="not_found"` and the line reads `fr.json["ops.replay_not_found"]` with `role="alert"`, `font-size` 13.6 px, weight 500 and colour rgb(180, 35, 24); answered 500, `data-state="error"` and the line reads `fr.json["ops.error"]` with the same look and `role`. In each, the dashboard card stays above with its figures.
- **AC-13** (new; `_design.md` section 8 « States ») (static) No page of the client has a spinner or a skeleton. With comments removed, no file of `web/src/**/*.svelte`, `web/src/**/*.ts` or `web/src/**/*.css` holds `@keyframes`, a CSS declaration whose property is `animation` or starts with `animation-`, the text `<progress`, or `role="progressbar"` (with either quote); and no `.css` file under `web/dist/assets/` holds `@keyframes` or an `animation` or `animation-*` declaration. The checker flags the samples `@keyframes spin{}`, `a{animation:spin 1s}`, `a{animation-name:spin}`, `<progress value="1">` and `<div role="progressbar">`, and accepts `a{transition:opacity .25s}`, `a{transition-duration:0s}`, `<div role="status">` and `<p>progression</p>`.
- **AC-14** (new) (browser with mocked routes and ops API) The three pages pass spec 035's scans, fit every window and keep the keyboard. At 1280 by 720 and at 360 by 740, in these states, spec 035's contrast scan (its AC-8) and language scan (its AC-9, with the nicknames, `ana.probe@example.org`, `ana@`, the room code `K7QM2X` and the share URL as test data) find no offending element: the shared recap page loading, loaded with `PUBLIC`, unavailable; the account page `loading`, `signing_in`, `signed_in`, `signed_in` with the deletion asked, `link_invalid`, `signed_out` with `account-error` after a 422, `signed_out` with `account-sent`, `deleted`, `error`; the ops page `locked` with `ops-token-error`, `loading`, `error`, `ready` with `REPLAY` at the position 4, `ready` with `REPLAY_EMPTY`, and the replay `not_found`. At every size of spec 006 AC-5, the shared recap page with `PUBLIC`, the account page `signed_in` with the deletion asked, and the ops page `ready` with `REPLAY` and with `REPLAY_FX02` have no horizontal scroll (`document.documentElement.scrollWidth <= window.innerWidth`). Keyboard only (spec 035's harness): on the account page `signed_in`, `tab_to` reaches `account-room-link`, `account-sign-out` and `account-delete`, each with a `2px` `solid` rgb(27, 47, 85) outline and `outline-offset` `2px`; `Enter` on `account-delete` shows the panel and `Tab` then reaches `account-delete-confirm` and `account-delete-cancel` with the same outline; on the shared recap page, `tab_to` reaches `share-home` with it; on the ops page `ready`, `tab_to` reaches each `ops-period`, `ops-replay-code` and `ops-replay-submit` with it.

## Edge cases and errors

- The account page's first request (AC-5): while `GET /api/account` runs the card
  shows its title only, so a signed-in player does not see a signed-out form flash
  before their address (Decision 3).
- A long address (AC-3): `account-email` wraps anywhere (spec 033's `overflow-wrap`),
  so the card never scrolls sideways.
- Deleting asked, then signing out (AC-4): `account-sign-out` stays enabled while the
  panel shows; signing out shows `signed_out`, and the panel goes with the state.
- A second press on `account-delete` (AC-4): it hides the panel, as a disclosure
  does; nothing is sent.
- A refused address, then another failure (AC-5): the red border means "this address
  is wrong" and shows only after a 422; a 429 or a send failure shows its line with
  the normal border.
- The shared recap without a grid number (AC-1): a room made outside the catalogue
  has no number; the card has no secondary line.
- A share link that expired (AC-2): the API answers 404 (spec 028), so the
  unavailable card shows, with its way to the grids.
- Replay positions (AC-9, AC-11): at 0 nothing is current; at the maximum the last
  edit is current; the knob sits 9 px inside each end of the input, as a native
  thumb does.
- A pencil letter later locked (AC-10): a lock beats the pencil flag, as in the
  playing grid (a checked or revealed letter is not a pencil letter).
- An undo that puts back a pencil letter (AC-10): the `undone` edit carries the
  pencil flag (spec 038's `RoomEdit.pencil`), so the cell is italic again.
- A wide grid on a phone (AC-10): FX-02's 13 columns get 22 px cells at 360 px, so the
  grid always fits the card; the letters are then 12.3 px, which is accepted for an
  operator's view.
- A window of exactly 900 px (AC-9): the two-column form; at 899 px, one column.
- A room with no edit (AC-10): the one empty line; a grid with no letter and a slider
  with no step would say nothing more.
- Period change while a replay shows (spec 038 AC-7): the cards stay; nothing of this
  spec changes on a period change.
- Fonts: on every state, the lines are set in Nock's fonts (spec 041).

## Out of scope

- The states of the catalogue, « Mes salons », the history, the opening room and a
  failed « Jouer » (spec 046), and of the recap dialog (spec 047).
- The account sheet in a room (spec 043) and on the catalogue (spec 046).
- Moving the focus after a state change of the account page (sign-out, deletion):
  spec 033's behaviour is kept.
- A red « danger » button variant (decided against, D1).
- Grid credits (D2).
- A dark mode, forced-colours or print styles; screenshot comparison with the screens
  sheet (`_design.md` section 13).

## Work packages

None: one pull request.

## Decisions

Decided by the human on 2026-10-22 (screens sheet P1, P11, P12, P14, P15, D1;
`_design.md` section 15), each already part of the spec above: the pages in the
phone's column, at most 420 px on a computer (P1); the shared recap as one entry
card with the time in the recap's style and « Voir les grilles » (P11); the account
page as one card, the deletion asked again in the same card, no red button (P12,
D1); the operator page in the catalogue's frame, with chips, tiles and the replay
beside the grid (P14); the slider built from the progress bar (P15); one line per
state, no spinner (P2, P4, P10).

Proposed by the spec writer, each already part of the spec above:

1. A state line has one look per kind (waiting, empty, error, done) and one role per
   kind, so every page reads the same and a screen reader hears waiting and done
   lines politely and errors at once.
2. AC-13 checks the "no spinner" rule on the whole client, since a rule that holds
   everywhere is cheapest checked once.
3. The account page shows its title only while its first request runs (Open
   question 1): the request is short, and a line « Connexion… » would read as
   signing in.
4. « Supprimer mon compte » is a disclosure button (`aria-expanded`), the screens
   sheet's "pressed (quiet)" look while the question is open, and a second press
   closes it, so the one control says whether the question is open.
5. A replay with no edit shows its empty line only (Open question 2): an empty grid
   and a slider from 0 to 0 add nothing to « Aucune modification dans ce salon. ».
6. The replay's two forms switch at a window 900 px wide, the room's own threshold
   (spec 043), so the two-column form always has room for a 13-column grid at 44 px
   beside the edits (Open question 3).
7. The replay's cells show the pencil, locked and revealed marks of the playing grid,
   worked out from the edits (Open question 4): the screens sheet draws them, and an
   operator diagnosing a game needs to see what was checked or revealed.
8. The slider is the native range input, transparent, over three drawn elements
   (Open question 5): the native thumb and track are styled differently by each
   engine (Firefox has `::-moz-range-progress`, WebKit no fill at all), so drawn
   parts give one look in all three, and the input keeps the role, the name and the
   keys.
9. `account-home` reuses `share.home` (« Voir les grilles »), so no new key holds the
   same text.

Decided by the human on 2026-10-22, with the spec's approval (these were the Open
questions, answered with their recommended answer; the text above already follows
them). The number in brackets is the question's number, which the text above cites:

10. (Open question 1.) The account page while its first request runs. Options: (a)
    the card's title only; (b) a muted line « Chargement… » (a new key,
    `account.loading`). Answer: (a) (Decision 3).
11. (Open question 2.) A replay with no edit. Options: (a) its empty line only; (b)
    the line plus the empty grid and the slider, as spec 038 has them. Answer: (a)
    (Decision 5).
12. (Open question 3.) Where the replay goes from one column to two. Options: a
    window 900 px wide (the room's threshold); spec 046's phone split; the card's
    own width (a container query). Answer: 900 px (Decision 6).
13. (Open question 4.) Marks in the replay's grid. Options: (a) pencil, locked and
    revealed, as drawn; (b) letters only, as spec 038 has it. Answer: (a)
    (Decision 7).
14. (Open question 5.) How the slider is drawn. Options: (a) drawn elements under a
    transparent native input; (b) the engines' range pseudo-elements, which cannot
    draw the navy fill in WebKit without a script-set gradient. Answer: (a)
    (Decision 8); `_design.md` section 11 carries a note on it.

## Open questions

None left (all answered with the approval of 2026-10-22).
