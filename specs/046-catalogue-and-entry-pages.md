---
id: "046"
title: Catalogue and entry pages
status: approved
---

# 046 - Catalogue and entry pages

Epic E10 Quality bar · Release: MVP · No backlog story: this is the second spec of
build step 5 of `specs/_design.md` (section 14). It applies `_design.md` section 10
(the catalogue, with « Mes salons » of spec 032, the history of spec 029 and the
« Compte » of spec 033), section 8 "Entry and not-found pages" (the nickname card,
the entry statuses, a room not found or expired, the page not found, and the frame
of these pages on a computer), section 8 "States" for the catalogue and for the
opening room, section 8 "Room sheets" for the account sheet outside a room, section
11 (card, list row, field, text input, error line, buttons, top-bar button, status
pill, filter chip) and the parts of sections 2, 4 and 5 that these pages use. It
builds on spec 041 (tokens, fonts, the button primitives, `NOCK_MARK_POINTS`), spec
043 (the room's top bar, `topbar-brand`, the room sheets, `visually-hidden`) and
spec 044 (the top bar's « Clavier »), and redefines none of them; where it changes
one of their rules, "Refined specs" says so. The decisions of the screens sheet it
applies are P1 (plain pages on a computer), P2 (the opening room), P3 (an expired
room), P4 (the catalogue's states) and P13 (the account sheet outside a room). The
FX-01 reference grid is in `specs/_reference.md`; the stack in
`specs/_architecture.md`.

## Goal

The pages a player sees before the game take the design: the catalogue with its
grid cards, its « Mes salons » and its « Grilles terminées », the account sheet
from its « Compte », the grid page, the nickname card that a guest fills to enter
a room, the cards that say why a room refuses entry or no longer exists, the page
not found, and the room while it opens. Their content, their routes, their test ids
and their rules stay those of specs 004, 010, 012, 029, 032, 033 and 040; only their
look and their layout change, with three small changes of behaviour that the human
decided with the screens sheet: « Mes salons » shows nothing while it loads or when
it is empty (P4), an expired room says why it is gone (P3), and every refusal card
leads back to the grids. The rule of the human holds: the simplest design that
removes edge cases; the core is the game.

## Public interface

No new Python name, no new protocol message, no new HTTP route. Client only
(`web/`: chiefly `web/src/lib/CataloguePage.svelte`, `CatalogueItem.svelte`,
`MyRooms.svelte`, `HistoryList.svelte`, `HistoryItem.svelte`, `GridPage.svelte`,
`NotFoundPage.svelte`, `AccountDialog.svelte` and the pre-snapshot part of
`RoomPage.svelte`). Every colour is a token of spec 041 used for its job in
`_design.md` section 2, every icon and mark comes from `web/src/lib/icons.ts`, every
string from `web/src/i18n/fr.json`.

### Terms

- Wide window: `window.innerWidth > window.innerHeight`, `window.innerWidth >= 900`
  and `window.innerHeight > 500`, the windows on which the room shows spec 043's
  computer top bar (Open question 1). Every other window is narrow. A page follows
  each resize within 300 ms.
- Plain page: a page that is not the room in play: the catalogue (`/`), the grid
  page (`/g/<number>`), the not-found page, and the room page while it shows the
  nickname card or a status card ("Entry pages"). Spec 048 puts its pages (the
  account page, the shared recap page, the operator page) in this spec's two frames,
  the entry frame and the catalogue frame, with their top bar and their split
  between wide and narrow windows.
- A pictogram: as spec 043's "Terms" (CSS generated content on an empty
  `aria-hidden` element). This spec uses one, the separator « · », drawn by
  `data-testid="meta-sep"`.

### Page top bar (`_design.md` sections 8 and 10)

`data-testid="page-topbar"`: a `header`, white, a 1 px solid `--nock-line` bottom
border, full window width, at the top of the window, items centred vertically,
holding spec 043's `topbar-brand` (the Nock mark, 12 by 18 px, navy, and
`t("app.title")` in 700 1.3rem/1, navy, letter spacing 0.01em, gap 8 px) and, on the
catalogue only, `account-open` (see "« Compte » on the catalogue"). The brand is not
a link.

- On the catalogue and the grid page: 56 px high (its border included), padding 0
  16 px, on every window.
- On the entry pages and the not-found page: 56 px high and padding 0 16 px on a
  wide window; 54 px high and padding 0 14 px on a narrow window.

### Entry frame (`_design.md` section 8, P1)

Under `page-topbar`, `data-testid="page-body"` fills the rest of the window's
height, background `--nock-page`, padding 48 px 24 px on a wide window and 20 px
16 px on a narrow one. It holds `data-testid="page-column"`, horizontally centred,
`width: min(420px, 100%)`, a grid with a 14 px gap, items aligned to the start:

1. on the room page only, the room code line: spec 040's `h1` (`t("room.heading",
   { code })`, « Salon {code} »), in 600 0.85rem/1, `--nock-muted`;
2. one card: white, a 1 px solid `--nock-line` border, radius 10 px, padding 18 px
   16 px, a grid with a 12 px gap, items aligned to the start (a button keeps its
   own width). The card's title is in 700 1.25rem/1.2, navy; a muted line in its
   400 0.85rem, `--nock-muted`.

### Catalogue frame (`_design.md` section 10)

The catalogue page (`catalogue-page`, spec 004) is white and holds `page-topbar`,
then `data-testid="catalogue-column"`: horizontally centred, at most 920 px wide,
padding 24 px on a wide window and 16 px on a narrow one, a grid with a 16 px gap,
holding in this order:

1. the `h1` `t("catalogue.heading")` (« Grilles »), 700 1.7rem/1.1, navy;
2. `my-rooms` (spec 032), when the page shows it (see "« Mes salons »");
3. the force filter row (`catalogue-filters`), when it shows (see "States");
4. `catalogue-status` or `catalogue-list` (see "States" and "Grid cards");
5. `history` (spec 029), when the page shows it.

### « Compte » on the catalogue (`_design.md` sections 8 and 10, P13; refines spec 033's catalogue link)

While accounts are on (spec 033: `GET /api/account` answered 200), `page-topbar`
holds `data-testid="account-open"` on its right (`margin-left: auto`), in place of
spec 033's `account-link`: a `<button type="button">` with the text
`t("account.open")` (« Compte »), `aria-haspopup="dialog"` and `aria-expanded`
(`"true"` while its dialog is open), drawn as a computer top-bar button of spec 043
with no icon: transparent background, no border, radius 6 px, padding 0 12 px, the
label in 500 0.92rem/1, navy, 38 px high on a wide window and 34 px high on a narrow
one, its right edge 16 px from the window's right edge; `--nock-word` background
while its dialog is open. While accounts are off there is no `account-open`.

A click opens spec 033's `account-dialog` (its ids, its content and its rules), as a
modal `<dialog>` (`showModal()`), labelled by its heading, in the look of spec 043's
room sheets:

- wide window: centred, 440 px wide (at most the window's width less 32 px), white,
  radius 12 px, padding 20 px 22 px, gap 14 px, shadow
  `0 20px 40px -16px var(--nock-shadow-strong)`; the backdrop `--nock-scrim` over
  the whole window;
- narrow window: a bottom sheet, full width, its bottom on the window's bottom, at
  most the window's height less 56 px, its content scrolling inside when higher,
  white, top corners radius 16 px, padding 14 px 18 px 18 px, gap 14 px, no handle;
  the backdrop `--nock-scrim` from 56 px below the window's top (the top bar stays
  visible, and inert while the dialog is open);
- the title in 700 1.2rem/1.2, navy; the intro in 400 0.9rem, `--nock-muted`;
  `account-close` (`t("account.close")`) a secondary button, right-aligned; the
  submit button primary; `account-page-link` a text link (navy, weight 600).

Signed out, the intro is `t("account.signed_out_intro")` (« Recevez par e-mail un
lien pour vous connecter. »), since `account.dialog_intro` speaks of « ce salon »
(P13), and the form sends spec 033's link request with `"room": null`; its answers
show as spec 033 says (`account-sent`, `account-error`). Signed in, the dialog
shows `t("account.signed_in_heading")`, `t("account.signed_in_as", { email })` and
`account-page-link` to `/account`, as in a room. `Escape`, `account-close` or a
click on the backdrop closes it, and the focus goes back to `account-open`.

### « Mes salons » (`_design.md` section 10, P4; refines spec 032's "My rooms")

`my-rooms` keeps spec 032's rules (when it exists, its request, `data-state`, its
items and their attributes and texts), with these changes of look and of states:

- It has the `hidden` attribute while `data-state` is `loading`, and while it is
  `ready` with no summary: nothing shows while it loads, and an empty answer shows
  no section (P4). It shows no `t("my_rooms.loading")` and no
  `t("my_rooms.empty")`, which leave `fr.json`.
- Its `h2` (`t("my_rooms.heading")`) is the catalogue section heading: 700
  1.15rem/1.2, navy.
- `error`: the heading, then `data-testid="my-rooms-error"`, the error line of
  `_design.md` section 11 (500 0.85rem/1.3, `--nock-red`) with
  `t("my_rooms.error")`.
- `ready`: the heading, then the list (`ul`, `role="list"`), its rows 10 px apart.
  Each `my-room` is a list row of `_design.md` section 11: white, a 1 px solid
  `--nock-line` border, radius 8 px, padding 12 px 14 px, a flex row with a 12 px
  gap, items centred; a text column (all the width left, lines 3 px apart) and
  `my-room-link` on the right:
  - `data-testid="my-room-title"` (the row's `h3`), weight 700, ink, the size of the
    page text: the grid label, a `meta-sep`, the size `t("catalogue.item.size")`,
    then, when the room is solved, `my-room-solved` (spec 032's text
    `t("catalogue.progress.finished")`) drawn as the « Terminée » status pill (see
    "Grid cards");
  - `my-room-players` and `my-room-activity`, 400 0.85rem, `--nock-muted`, wrapping
    rather than widening the page (spec 006 AC-5);
  - `my-room-link` (spec 032's `<a>`, attributes and texts) with the button look of
    spec 041: `nock-button nock-button-primary`, or `nock-button
    nock-button-secondary` when the room is solved.

### Force filter (`_design.md` section 10)

`data-testid="catalogue-filters"`: a flex row, wrapping, gap 8 px, items centred,
`role="group"` and `aria-labelledby="catalogue-filter-label"` (in place of spec
004's `aria-label`), holding:

- `data-testid="catalogue-filter-label"`, `id="catalogue-filter-label"`, the text
  `t("catalogue.filter.label")` (« Force »), 600 0.85rem/1, `--nock-muted`;
- the five `force-filter` buttons of spec 004 (their attributes, texts and rules),
  drawn as filter chips: white background, a 1 px solid `--nock-line` border,
  radius 16 px, padding 7 px 14 px, 600 0.9rem/1, navy text; pressed
  (`aria-pressed="true"`): `--nock-word` background and a navy border.

### Grid cards (`_design.md` section 10)

`catalogue-list` (spec 004) is a CSS grid with `grid-template-columns:
repeat(auto-fill, minmax(min(100%, 400px), 1fr))` and a 12 px gap, so one card per
row on a phone and two on a computer. Each `catalogue-item` (spec 004's attributes
and texts; spec 010's button) is white, with a 1 px solid `--nock-line` border,
radius 8 px, padding 12 px 14 px, a flex row with a 14 px gap, items centred, holding
in this order:

1. `data-testid="catalogue-thumb"`, the generic grid drawing, only while
   `catalogue-list`'s content box is at least 812 px wide (room for two 400 px
   columns and their gap; P4's "more than one per row"); otherwise absent. An `svg`
   with `aria-hidden="true"`, the attributes `width` round(51 × W / H) and `height`
   51 (W and H the item's `data-width` and `data-height`), `viewBox` `0 0 10W 10H`,
   a 1 px solid `--nock-rule` border (CSS, outside its 51 px), holding in this
   order: one `rect` covering the viewBox with `fill="var(--nock-white)"`; one
   `rect` `data-testid="thumb-clue"` per clue cell of the drawing, 10 by 10 units,
   `fill="var(--nock-thumb)"`, at row 0 for each even column (0, 2, 4, …) and at
   column 0 for each even row from 2 (2, 4, …); one `line` `data-testid="thumb-line"`
   per inner grid line (W − 1 vertical, H − 1 horizontal), across the whole
   drawing, `stroke="var(--nock-line)"` and `stroke-width="1"`. It shows the
   proportions only: spec 004's `GridSummary` does not change (decided by the human
   on 2026-10-17).
2. A text column, all the width left, lines 3 px apart:
   - the item's `h2` (`t("catalogue.item.number")`), 700 1.05rem/1.2, ink, followed
     on its line (gap 8 px) by `catalogue-progress` (spec 004) when there is one,
     drawn as a status pill: radius 12 px, padding 3 px 9 px, 600 0.75rem/1.2;
     « Commencée » (`started`) navy on `--nock-word`, « Terminée » (`finished`)
     `--nock-green` on `--nock-green-bg`;
   - the publication line (`t("catalogue.item.published")`), 400 0.85rem,
     `--nock-muted`;
   - the force line, 400 0.85rem, `--nock-muted`, a flex row with a 6 px gap:
     `data-testid="catalogue-force-marks"` (`aria-hidden="true"`), four Nock marks
     2 px apart, each an `svg` with `viewBox="0 0 10 14"`, 8 by 11 px, holding one
     `polygon` with `NOCK_MARK_POINTS`, filled `--nock-navy` for the marks 1 to the
     grid's force and `--nock-thumb` after; then the texts
     `t("catalogue.item.force")`, `t("catalogue.item.size")` and
     `t("catalogue.item.words")`, with a `meta-sep` between each two. The force is
     written, so it never relies on the drawing or the marks alone.
   - after a failed « Jouer » (spec 010), `catalogue-error` (spec 010's text and
     `role="alert"`), the error line of `_design.md` section 11, under the force
     line, inside the card.
3. `catalogue-play` (spec 010's text and rules): `nock-button nock-button-primary`,
   padding 9 px 16 px, never shrinking, on the right.

### « Grilles terminées » (`_design.md` section 10; refines spec 029's history list)

`history` keeps spec 029's rules (when it exists, its records, their order, the
items' attributes and texts, the replay). Its `h2` is the catalogue section
heading (as « Mes salons »'s); its list's rows are 10 px apart. Each `history-item`
is a list row, as a `my-room`, holding a text column and, when present,
`history-replay` (`nock-button nock-button-secondary`) on the right:

- `data-testid="history-title"` (the row's `h3`), weight 700, ink: the grid label,
  a `meta-sep`, the size;
- `data-testid="history-line"`, one line that wraps when it must, 400 0.85rem,
  `--nock-muted`: `history-date`, a `meta-sep`, `history-time`, a `meta-sep`,
  `history-teammates`, each keeping spec 029's text;
- after a failed replay, `history-error` (spec 029), the error line, under
  `history-line`.

### States (`_design.md` section 8 "States", P4)

One rule: a state is one line of text where its content will be; muted while
waiting or when empty (400 1rem/1.5, `--nock-muted`), the error line when something
failed. No spinner, no skeleton. On the catalogue, `data-testid="catalogue-status"`
is that line, after `my-rooms`:

| `catalogue-page` | Shows, after the heading (and `my-rooms`) |
| --- | --- |
| `loading` | `catalogue-status` muted, `t("catalogue.loading")`; no `catalogue-filters` |
| `error` | `catalogue-status` as the error line, `t("catalogue.error")`; no `catalogue-filters` |
| `ready`, no grid at all | `catalogue-status` muted, `t("catalogue.empty")`; no `catalogue-filters` (P4: the chips are not shown) |
| `ready`, none of the selected force | `catalogue-filters`, then `catalogue-status` muted, `t("catalogue.empty_filtered")` |
| `ready`, grids shown | `catalogue-filters`, then `catalogue-list`; no `catalogue-status` |

### Grid page (refines spec 004's grid page)

`grid-page` (spec 004) has the catalogue's frame: `page-topbar` (with no
`account-open`), then a `catalogue-column` with no heading, holding a
`catalogue-list` with its one `catalogue-item` (the card above), or, in place of it,
`catalogue-status`: muted `t("catalogue.loading")` while loading, the error line
`t("catalogue.error")` on error, muted `t("not_found.heading")` for `not_found`
(spec 004's texts).

### Entry pages (`_design.md` section 8; refines specs 012 and 040)

Before its first snapshot, the room page (`room-page`, spec 040) shows an entry page
in these statuses, with `page-topbar` and the entry frame, and no `room-topbar`:

- `nickname`, and `joining` while the nickname form shows (spec 012: the form stays,
  its button disabled, until the snapshot): the nickname card;
- `full`, `locked`, `removed`, `replaced`, `throttled` and `not_found`: a status
  card.

In these statuses `room-page` has no `data-layout`. Once a snapshot came, spec 043's
room and its status band apply.

The nickname card is `nickname-form` (spec 012's ids, texts and rules), drawn as the
card of "Entry frame":

- its `h2` (`t("join.heading")`, « Choisissez un pseudo ») is the card's title;
- the field: the label (`t("join.nickname_label")`) above `nickname-input` (gap
  6 px), the label in 600 0.85rem/1.2, ink; `nickname-input` as wide as the card's
  content, a 1 px solid `--nock-rule` border, radius 6 px, padding 10 px 12 px, 400
  1rem/1.2, ink on white, `text-transform: uppercase` (spec 012), its placeholder in
  `--nock-muted`;
- while `nickname-error` shows: `nickname-input`'s border is `--nock-red`, and
  `nickname-error` (spec 012's text and `role="alert"`) is the error line, right
  under the field;
- `nickname-submit`: `nock-button nock-button-primary`.

`room-status` (spec 040) has the class `visually-hidden` while the nickname card
shows.

A status card is `data-testid="entry-card"`, the card of "Entry frame", holding in
this order:

1. `room-status` (spec 040's text), as the card's title;
2. on `not_found` only, `data-testid="entry-detail"`, the card's muted line,
   `t("room.status.not_found_detail")` (« Un salon est effacé 30 jours après sa
   dernière modification. »): spec 032 deletes an expired room, so an expired room
   and a room that never existed read alike, and the line says why a room may be
   gone (P3);
3. `data-testid="entry-home"`: an `<a href="/">` with `tabindex="0"` (spec 035:
   WebKit Tab-focuses a link only with one) and the text `t("share.home")`
   (« Voir les grilles »), with the look of `nock-button nock-button-secondary`, and
   `nock-button nock-button-primary` on `not_found`, where it is the only way on
   (P3).

### Page not found (refines spec 040's not-found page)

`not-found-page` (spec 040) has `page-topbar` and the entry frame with no room code
line, and one card: its `h1` (`t("not_found.heading")`, « Page introuvable ») as
the card's title, then `entry-home` with the look of `nock-button
nock-button-primary` (an addition to spec 040, decided in `_design.md` section 8).

### Opening the room (`_design.md` section 8 "States", P2; refines spec 043's page before a snapshot)

While the room page has no snapshot yet and shows no entry page (statuses
`connecting`, and `joining` when the page joined at once by spec 012's cases a and
b, with no form):

- `room-topbar` shows as spec 043 and spec 044 give it for this window (the phone or
  the computer top bar by spec 043's "Terms"; before a snapshot the in-app keyboard
  does not show, by spec 044's definition), with its buttons in their places, but
  no `timer` and no `timer-show` (the timer slot is empty) and no grid name; the
  whole `room-topbar` has the `inert` attribute, so that nothing in it acts before
  the room exists, and its look is the look it has once joined;
- `room-page` has `data-layout` (spec 043's rule) from the opening on;
- `grid-area` takes all the height under `room-topbar` and holds only
  `room-status` (its text `t("room.status.connecting")` or
  `t("room.status.joining")`), without the class `visually-hidden`: one line, 400
  1rem/1.5, `--nock-muted`, centred horizontally and vertically in `grid-area`;
- there is no `grid-viewport`, `clue-bar`, `grid-status`, `keyboard`, `salon`,
  `connection-banner` (spec 040: no banner before a snapshot) or `page-topbar`; the
  room's `h1` has the class `visually-hidden`.

When the first snapshot arrives, `inert` goes and spec 043's room shows. When the
status becomes `nickname` or a final status instead, the page shows its entry page.

### `fr.json` keys

New:

| Key | Value |
| --- | --- |
| `room.status.not_found_detail` | `Un salon est effacé 30 jours après sa dernière modification.` |

Removed, since nothing shows them any more: `my_rooms.loading`, `my_rooms.empty`.

Reused: `share.home` (`Voir les grilles`, spec 028) for `entry-home`, as spec 048's
pages use it.

`room.status.not_found_detail` has no placeholder; spec 035 AC-9's checker still
flags its samples with it.

### Refined specs

Each refined spec carries a dated note "(Note from the lead, 2026-10-22: refined by
spec 046, the design's catalogue and entry pages ...)" and keeps its status. The
test-writer updates the tests of the criteria named here before the implementer
runs.

| Spec | Criteria that change | What changes in their tests |
| --- | --- | --- |
| 004 | The check of the edge case "Empty catalogue" (whichever test holds it) | With an empty catalogue the page shows `catalogue-status` with `fr.json["catalogue.empty"]` and no `force-filter` (P4); the filter group is labelled by `aria-labelledby`, not `aria-label` |
| 032 | AC-5 | An answer `[]` gives `my-rooms` `data-state="ready"`, the `hidden` attribute and no text (no `fr.json["my_rooms.empty"]`); an error shows `my-rooms-error`; `fr.json` has no `my_rooms.loading` or `my_rooms.empty` |
| 033 | AC-11 (the browser part) | For the lead: spec 033 belongs to the spec-writer of specs 047 and 048, so its note is the lead's to place. The catalogue has `account-open` in its top bar, opening `account-dialog`, in place of `account-link`; once signed in, that dialog's `account-page-link` points to `/account`. Spec 033's catalogue item of "Client" changes the same way (`account.signed_out_intro` and `"room": null` outside a room) |

Specs 004, 010, 012, 029, 040 and 044 get a note and no other criterion change:
their checks read ids, attributes and texts that this spec keeps (spec 010's play
button and failure text, spec 012's form and statuses, spec 029's history items,
spec 040's `room-status` and not-found heading); spec 044's « Clavier » now also
shows, inert, while the room opens. Specs 035 (its states K1, K5 and K7 are
redrawn, its criteria hold) and 043 (its top bar also shows, inert, while the room
opens, and `data-layout` is set from the opening on) need no criterion change; they
carry the notes of specs 047 and 048, and the lead adds this spec's line to them.

This spec takes every state of the catalogue (its loading, empty and error lines,
« Mes salons »' states, the history's failed replay, a failed « Jouer ») and the
opening room; spec 048 leaves them here.

### Test harness

- "Browser with live server" as in specs 040 and 004, with spec 004's reference
  catalogue `CAT` served for `/` unless a criterion says otherwise. "Browser with
  mocked routes": `page.route` on `**/api/grids`, `**/api/rooms/summaries`,
  `**/api/account`, `**/api/account/link`, `**/api/account/history` and
  `**/api/rooms` as a criterion says, the answers built from the models of specs
  004, 029, 032 and 033 (`model_dump(mode="json")`), a delayed answer being one that
  the handler holds until the test releases it. "Browser with mocked socket" as in
  spec 040, on `/r/ABC123`, with `nock.identity.ABC123` or `nock.room.ABC123` seeded
  with `context.add_init_script` as spec 012's cases a, b and c need; a mock that
  never answers the join keeps the page `joining`.
- `ROOMS2`: the two summaries of spec 032 AC-5 (`XYZ789`, grid 2, 5 by 5, `Ana`,
  `Bob`, not solved; `ABC234`, grid null, 13 by 17, `Ana`, solved), with the
  identities of both rooms seeded. `HIST2`: the two history records of spec 029
  AC-2 (`XYZ789`, with `Avec Bob, Cy`; `QQQQQQ`, `En solo`). The context has
  `timezone_id="Europe/Paris"`.
- `BIG`: a mocked `GET /api/grids` answer of one `GridSummary` of 13 by 17 (number
  12, force 3, 54 words) and one of 5 by 5 (number 2, force 2, 8 words).
- Windows: 1280 by 720 (wide) and 360 by 740 (narrow) unless a criterion says
  otherwise; desktop context; `localStorage` empty except what a criterion seeds.
- Positions are bounding boxes; tolerances 1 px for a position, 0.5 px for a size,
  0.1 px for a font size or a line height, unless a criterion says otherwise.
  Colours as spec 041 (`parseColour` of `tests/colour_contrast.js`, exact channels
  for a token, alpha within 0.01). A pictogram is checked on the computed `content`
  of its element's `::before` or `::after`. Contrast by spec 035's formula. Fonts:
  spec 041's rule (wait for `document.fonts.ready` before reading a size or a
  position that depends on text).
- The not-found page (AC-19): the server never serves the app on an unknown path
  (spec 040), so the test answers `GET /nowhere` with the content of
  `web/dist/index.html` through `page.route` (setup) and opens it.
- Engines: Chromium and WebKit locally, Firefox too in CI. No check is
  Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new) (browser with live server) The entry pages have one frame: a brand bar, the page grey and one centred column. On `/r/ZZZZZZ` (`not_found`, an empty registry) at 1280 by 720 and at 1024 by 768 (wide), `page-topbar` is a `HEADER` with the box left 0, top 0, the window's width and height 56 px, `background-color` rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) bottom border, and `topbar-brand` 16 px from its left edge (1 px), holding the 12 by 18 px Nock mark filled rgb(27, 47, 85) and the text `fr.json["app.title"]` in `font-size` 20.8 px, weight 700; `page-body` has `background-color` rgb(246, 247, 249), its top on `page-topbar`'s bottom, its bottom on the window's bottom, and `page-column` is 420 px wide, horizontally centred in the window, its top 48 px below `page-topbar`'s bottom. At 360 by 740 and at 768 by 1024 (narrow), `page-topbar` is 54 px high and `topbar-brand` 14 px from its left edge; `page-column` is `min(420, width − 32)` px wide (328 px at 360), centred, its top 20 px below `page-topbar`'s bottom. In both, `page-column`'s first child is the room's `h1` reading `Salon ZZZZZZ`, with `font-size` 13.6 px, weight 600, colour rgb(94, 101, 115), and its second child is the card, 14 px below it, with background rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `10px` and padding `18px 16px`. The page has no `room-topbar`.
- **AC-2** (new; refines spec 004's page) (browser with live server) The catalogue has a 56 px brand bar and a 920 px column on white. With `CAT`, at 1280 by 720 and at 360 by 740, `catalogue-page` holds `page-topbar` (56 px high in both, the window's width, `topbar-brand` 16 px from its left edge, with no other control while accounts are off) then `catalogue-column`; `catalogue-page` has the background rgb(255, 255, 255). At 1280 by 720, `catalogue-column` is 920 px wide, centred (its left at 180 px), with padding `24px`; at 360 by 740 it is 360 px wide with padding `16px`. Its children are, in order, the `h1` reading `fr.json["catalogue.heading"]` (`font-size` 27.2 px, weight 700, colour rgb(27, 47, 85)), `catalogue-filters`, `catalogue-list`, and each next child's top is 16 px below the bottom of the one before (1 px).
- **AC-3** (new; refines spec 033's catalogue link) (browser with mocked routes; keyboard only for the walk) « Compte » in the catalogue's top bar opens the account sheet, with the intro for a page outside a room. With `CAT` and `GET /api/account` answering 200 `{"signed_in": false, "email": null}`: at 1280 by 720, `page-topbar` holds `account-open`, a `BUTTON` with `type="button"`, the text `fr.json["account.open"]`, no `svg`, 38 px high (0.5 px), its right edge 16 px from the window's right edge, colour rgb(27, 47, 85), `font-size` 14.72 px, a background with alpha 0, `aria-expanded="false"`; there is no `account-link`. A click opens `account-dialog` (its `open` attribute set): 440 px wide (1 px), centred, `border-radius` `12px`, padding `20px 22px`; its heading reads `fr.json["account.dialog_heading"]` (700, 19.2 px, navy); its intro reads `fr.json["account.signed_out_intro"]` and not `fr.json["account.dialog_intro"]`, colour rgb(94, 101, 115), `font-size` 14.4 px; `account-open` has `aria-expanded="true"` and the background rgb(230, 237, 249). Typing `ana@example.org` in `account-email-input` and submitting sends one `POST /api/account/link` whose body parses to `{"email": "ana@example.org", "room": null}`; its answer 202 shows `account-sent`. `Escape` closes the dialog and the focus is on `account-open`, with `aria-expanded="false"`. At 360 by 740, `account-open` is 34 px high (0.5 px) and the dialog is a bottom sheet: the window's width, its bottom on the window's bottom, `border-top-left-radius` `16px`, padding `14px 18px 18px`, its top at least 56 px below the window's top; a click at (180, 80) on the backdrop closes it. With `{"signed_in": true, "email": "ana@example.org"}`, the dialog shows `fr.json["account.signed_in_heading"]`, `Connecté avec ana@example.org` (built from `fr.json["account.signed_in_as"]`) and `account-page-link` whose `href` is `/account`. With `GET /api/account` answering 404 there is no `account-open`. Keyboard only, at 1280 by 720 signed out: `tab_to` `account-open` gives it spec 035 AC-2's outline; `Enter` opens the dialog with the focus on `account-email-input`; `Escape` puts the focus back on `account-open`.
- **AC-4** (new; refines spec 004's force filter) (browser with live server) The force filter is a label and five chips. With `CAT` at 1280 by 720: `catalogue-filters` has `role="group"` and `aria-labelledby="catalogue-filter-label"`, no `aria-label`, and `page.get_by_role("group", name="Force", exact=True)` resolves to it; its first child is `catalogue-filter-label` reading `fr.json["catalogue.filter.label"]` (`font-size` 13.6 px, weight 600, colour rgb(94, 101, 115)), then the five `force-filter` buttons, each with `border-radius` `16px`, padding `7px 14px`, a `1px` `solid` border, `font-size` 14.4 px, weight 600 and colour rgb(27, 47, 85), 8 px apart (1 px); `data-force="all"` (pressed) has the background rgb(230, 237, 249) and the border colour rgb(27, 47, 85), the four others the background rgb(255, 255, 255) and the border colour rgb(221, 226, 234). After a click on `data-force="1"`, that chip has the pressed look and `all` the other.
- **AC-5** (new; refines spec 004's list) (browser with live server) Grid cards sit two per row on a computer and one per row on a phone. With `CAT` (three published grids), at 1280 by 720, `catalogue-list` has a computed `grid-template-columns` of two columns of 430 px (1 px) and `column-gap` `12px`; the cards of grids 3 and 2 share a top, the card of grid 1 is 12 px below them, each card 430 px wide. At 360 by 740 there is one column, each card 328 px wide, the next card 12 px below the one before. Each `catalogue-item` has the background rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `8px`, padding `12px 14px` and `display` `flex`; its `h2` reads `Grille n° N` (`font-size` 16.8 px, weight 700, colour rgb(20, 24, 31)); its publication line has `font-size` 13.6 px and colour rgb(94, 101, 115); `catalogue-play` is its last child, with the primary colours of spec 041 AC-10, padding `9px 16px`, its right edge 14 px left of the card's right edge (1 px, the padding and the border) and its vertical centre within 1 px of the card's.
- **AC-6** (new; refines spec 004 AC-3's status) (browser with live server) The progress of a grid is a status pill after its number. With `CAT` and `nock.progress` seeded `{"1": "started", "2": "finished"}`, at 1280 by 720: in item 1, `catalogue-progress` reads `fr.json["catalogue.progress.started"]`, lies on the line of the item's `h2`, right of it (its left 8 px right of the `h2`'s right, 1 px; their vertical centres within 2 px), with `border-radius` `12px`, padding `3px 9px`, `font-size` 12 px, weight 600, background rgb(230, 237, 249) and colour rgb(27, 47, 85); in item 2 it reads `fr.json["catalogue.progress.finished"]` with background rgb(230, 242, 234) and colour rgb(30, 123, 69); item 3 has none. Each pill's text reaches 4.5:1 on its background.
- **AC-7** (new) (browser with mocked routes) The force line shows four Nock marks and the force, size and words. With `BIG` at 1280 by 720: in the card of grid 12, `catalogue-force-marks` has `aria-hidden="true"` and holds four `svg` with `viewBox="0 0 10 14"`, each 8 by 11 px, 2 px apart (1 px), each holding one `polygon` whose `points` are `0,0 10,0 10,14 5,10 0,14`, whose computed `fill` is rgb(27, 47, 85) for the first three and rgb(201, 210, 224) for the fourth; it is followed by the texts `Force 3`, `13 × 17` and `54 mots`, with one `meta-sep` between each two, whose pictogram `content` is `"·"`; the line has `font-size` 13.6 px and colour rgb(94, 101, 115). In the card of grid 2 the first two marks are navy and the last two rgb(201, 210, 224).
- **AC-8** (new; decided by the human on 2026-10-17) (browser with mocked routes) Cards show a generic drawing of the grid's proportions, only when two fit per row. With `BIG` at 1280 by 720: each `catalogue-item`'s first child is `catalogue-thumb`, an `svg` with `aria-hidden="true"`; for grid 12 (13 by 17) its `width` attribute is `39`, its `height` `51`, its `viewBox` `0 0 130 170`, its content box 39 by 51 px and its border `1px` `solid` rgb(154, 163, 178); its first child is a `rect` of `width` 130 and `height` 170 whose computed `fill` is rgb(255, 255, 255); it holds 15 `thumb-clue` `rect` elements (7 in row 0 at `x` 0, 20, …, 120 and `y` 0; 8 in column 0 at `x` 0 and `y` 20, 40, …, 160), each 10 by 10 with the computed `fill` rgb(201, 210, 224), and 28 `thumb-line` elements (12 vertical, 16 horizontal) with the computed `stroke` rgb(221, 226, 234) and `stroke-width` 1; for grid 2 (5 by 5), `width` `51`, `height` `51`, 5 `thumb-clue` and 8 `thumb-line`. At 360 by 740 and at 768 by 1024 no card holds a `catalogue-thumb`. After `page.set_viewport_size` from 1280 by 720 to 360 by 740, the drawings are gone within 300 ms, and they come back on the way back.
- **AC-9** (new; P4) (browser with mocked routes) The catalogue's states are one line where the cards will be. At 1280 by 720 and at 360 by 740, with `GET /api/grids` delayed: `catalogue-page` has `data-state="loading"`, `catalogue-status` reads `fr.json["catalogue.loading"]` with colour rgb(94, 101, 115), `font-size` 16 px and `line-height` 24 px, its top 16 px below the `h1`'s bottom, and there is no `catalogue-filters` and no `catalogue-list`. Answered 500: `catalogue-status` reads `fr.json["catalogue.error"]` with colour rgb(180, 35, 24), `font-size` 13.6 px and weight 500, and there is no `catalogue-filters`. Answered `[]`: `catalogue-status` reads `fr.json["catalogue.empty"]`, muted, and there is no `force-filter`. With `CAT` (live) and a click on `data-force="4"`: `catalogue-filters` shows, followed by `catalogue-status` reading `fr.json["catalogue.empty_filtered"]`, muted, and no `catalogue-list`. In no state does the page hold an element with `role="progressbar"` or an animation (`getAnimations()` of the document is empty).
- **AC-10** (new; refines spec 010's failure message) (browser with live server) A failed « Jouer » shows its error line inside its card. With `CAT` and `POST /api/rooms` answering 500, after a click on the `catalogue-play` of item 2 at 1280 by 720 and at 360 by 740: `catalogue-error` is inside that `catalogue-item`, reads `fr.json["catalogue.play_failed"]`, has `role="alert"`, colour rgb(180, 35, 24), `font-size` 13.6 px, weight 500, its top below the bottom of the card's force line and its left on the left of the card's `h2` (1 px); the card's box lies inside `catalogue-list`'s; `catalogue-play` is enabled again; no other card holds a `catalogue-error`.
- **AC-11** (new; refines spec 032's "My rooms") (browser with mocked routes) « Mes salons » lists each room as a row, its button primary, secondary once solved. With `CAT`, `ROOMS2` seeded and answered, at 1280 by 720 and at 360 by 740: `my-rooms` comes right after the `h1` and before `catalogue-filters` (16 px below the `h1`, 1 px), its `h2` reads `fr.json["my_rooms.heading"]` with `font-size` 18.4 px, weight 700, colour rgb(27, 47, 85); its two `my-room` rows are 10 px apart, each with background rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `8px`, padding `12px 14px`. The row of `XYZ789`: `my-room-title` reads `Grille n° 2` then a `meta-sep` (`content` `"·"`) then `5 × 5`, weight 700, colour rgb(20, 24, 31), with no `my-room-solved`; `my-room-players` and `my-room-activity` are under it, 3 px apart, each `font-size` 13.6 px, colour rgb(94, 101, 115); `my-room-link` is on the right (its right edge 14 px left of the row's right edge, 1 px), reads `fr.json["my_rooms.open"]`, with the primary colours of spec 041 AC-10, padding `10px 16px` and `border-radius` `6px`. The row of `ABC234`: `my-room-solved` is inside `my-room-title`, after the size, with the « Terminée » pill's look of AC-6; `my-room-link` has the secondary colours. With 8 players of 20 characters in `XYZ789`, at 320 by 568, `my-room-players` wraps and `document.documentElement.scrollWidth <= window.innerWidth`.
- **AC-12** (new; P4; refines spec 032 AC-5's states) (browser with mocked routes) « Mes salons » shows nothing while it loads or when it is empty, and an error line when it fails. With `CAT` and `ROOMS2` seeded, at 1280 by 720: with the summaries request delayed, `my-rooms` has `data-state="loading"` and the `hidden` attribute, its box is empty (0 by 0), `catalogue-filters` is 16 px below the `h1`, and no text of the page reads `Chargement de vos salons…`; answered `[]`, `my-rooms` has `data-state="ready"`, the `hidden` attribute and no `my-room`; answered 500, `my-rooms` has `data-state="error"`, shows its `h2`, then `my-rooms-error` reading `fr.json["my_rooms.error"]` with colour rgb(180, 35, 24) and `font-size` 13.6 px, and `catalogue-page` still reaches `data-state="ready"`. Static: `web/src/i18n/fr.json` has no key `my_rooms.loading` and no key `my_rooms.empty`.
- **AC-13** (new; refines spec 029's history list) (browser with mocked routes) « Grilles terminées » lists each finished grid as a row with its date, time and team on one line. With `CAT` and `HIST2` seeded (no account), at 1280 by 720 and at 360 by 740: `history` is the last child of `catalogue-column`, 16 px below `catalogue-list`, its `h2` reading `fr.json["history.heading"]` in the section heading's look of AC-11; its rows are 10 px apart, in the list row's look of AC-11. In the row of `XYZ789`, `history-title` reads `Grille n° 2`, a `meta-sep`, `5 × 5`, weight 700; `history-line` holds `history-date` (`Terminée le 14 octobre 2026`), a `meta-sep`, `history-time` (`en 12 min 34 s`), a `meta-sep`, `history-teammates` (`Avec Bob, Cy`), in that order, `font-size` 13.6 px, colour rgb(94, 101, 115), on one line at 1280 by 720 (the vertical ranges of the three texts' boxes overlap pairwise); `history-replay` is on the right with the secondary colours of spec 041 AC-10. The row of `QQQQQQ` has no `history-replay`. With `POST /api/rooms` answering 500, after a click on `history-replay`, `history-error` is inside the row, under `history-line`, with the error line's colour rgb(180, 35, 24) and `font-size` 13.6 px.
- **AC-14** (new; refines spec 004's grid page) (browser with live server) The grid page shows its one card in the catalogue's frame. With `CAT`, on `/g/2` at 1280 by 720 and 360 by 740: `grid-page` holds `page-topbar` (56 px high, `topbar-brand`, no `account-open`) and a `catalogue-column` with no `h1`, holding one `catalogue-list` with one `catalogue-item` (`data-number="2"`) in the card look of AC-5, with a `catalogue-thumb` at 1280 by 720 and none at 360 by 740; `grid-page` reaches `data-state="ready"`. With `GET /api/grids/2` answering 500 (`page.route`), `catalogue-status` reads `fr.json["catalogue.error"]` with the error line's colour.
- **AC-15** (new; refines spec 012's nickname form) (browser with mocked socket) The nickname form is a card under the room code. On `/r/ABC123` with nothing seeded (spec 012 case c), at 1280 by 720 and at 360 by 740, once `data-status="nickname"`: the frame of AC-1 (with no `room-topbar` and no `data-layout` on `room-page`), the room's `h1` reading `Salon ABC123` as the room code line, then `nickname-form` as the card of AC-1, its first child its `h2` reading `fr.json["join.heading"]` with `font-size` 20 px, weight 700, `line-height` 24 px, colour rgb(27, 47, 85); then the label `fr.json["join.nickname_label"]` (`font-size` 13.6 px, weight 600, colour rgb(20, 24, 31)) with `nickname-input` 6 px below it (1 px), as wide as the card's content box (1 px), with a `1px` `solid` rgb(154, 163, 178) border, `border-radius` `6px`, padding `10px 12px`, `font-size` 16 px, `text-transform` `uppercase` and background rgb(255, 255, 255); then `nickname-submit` reading `fr.json["join.submit"]` with the primary colours of spec 041 AC-10, its left on the card's content left (1 px) and narrower than the card's content. `room-status` reads `fr.json["room.status.nickname"]` and has the class `visually-hidden`.
- **AC-16** (new; refines spec 012's nickname error) (browser with mocked socket) A refused nickname turns the field red and shows its reason under it. On the page of AC-15, after typing `A` and a click on `nickname-submit`: `nickname-input` has the border colour rgb(180, 35, 24) on each side; `nickname-error` reads `fr.json["join.error.length"]`, has `role="alert"`, colour rgb(180, 35, 24), `font-size` 13.6 px and weight 500, and its top is below `nickname-input`'s bottom and above `nickname-submit`'s top; no frame was sent (spec 017's pings not counted). After `Ana` is typed instead and the form submitted, `data-status` is `joining`, the card still shows with `nickname-submit` disabled (the disabled look of spec 041 AC-11), and when the mock answers with a FX-01 snapshot, the entry frame is gone and `room-topbar` shows.
- **AC-17** (new; refines the entry statuses of specs 011, 012, 014 and 040) (browser with mocked socket) A room that refuses entry shows its reason as a card title and leads back to the grids. On `/r/ABC123` with `nock.identity.ABC123` seeded (spec 012 case a), at 1280 by 720 and at 360 by 740, in five runs where the mock answers the join with `error` `room_full`, with `error` `room_locked`, with `error` `removed`, closes the socket with code 4429, and closes it with code 4001 before any snapshot: `room-page` reaches `data-status` `full`, `locked`, `removed`, `throttled` and `replaced`; it shows the frame of AC-1 with the room code line `Salon ABC123` and no `room-topbar`; `page-column`'s card is `entry-card`, whose first child is `room-status` reading `fr.json["room.status.<status>"]` in `font-size` 20 px, weight 700, colour rgb(27, 47, 85), not `visually-hidden`; it holds no `entry-detail`; its last child is `entry-home`, an `A` with `href="/"` and `tabindex="0"`, reading `fr.json["share.home"]`, with the secondary colours of spec 041 AC-10 (background rgb(255, 255, 255), colour and border rgb(27, 47, 85)), `border-radius` `6px` and padding `10px 16px`.
- **AC-18** (new; P3) (browser with live server) A room that does not exist or has expired says why it may be gone, with one way on. On `/r/ZZZZZZ` with an empty registry, at 1280 by 720 and at 360 by 740: `room-page` has `data-status="not_found"`; `entry-card` holds in order `room-status` reading `fr.json["room.status.not_found"]` in the card title's look of AC-17, `entry-detail` reading `fr.json["room.status.not_found_detail"]` with `font-size` 13.6 px and colour rgb(94, 101, 115), and `entry-home` reading `fr.json["share.home"]` with the primary colours of spec 041 AC-10. A click on `entry-home` loads `/`, where `catalogue-page` shows. (An expired room is deleted by spec 032 and its socket closed with code 4404, so it gives this same page; spec 032 AC-2 checks the close.)
- **AC-19** (new; refines spec 040's not-found page) (browser with live server, routed path; keyboard only for the walk) The page not found has its card and a way back. On `/nowhere` (see "Test harness") at 1280 by 720 and at 360 by 740: `not-found-page` holds `page-topbar` and `page-body` with the frame of AC-1, but no room code line: `page-column`'s only child is the card, whose first child is the `h1` reading `fr.json["not_found.heading"]` in the card title's look of AC-17, then `entry-home` (an `A`, `href="/"`, `tabindex="0"`, `fr.json["share.home"]`) with the primary colours. Keyboard only: `tab_to` `entry-home` gives it spec 035 AC-2's outline, and `Enter` loads `/`, where `catalogue-page` shows.
- **AC-20** (new; P2) (browser with mocked socket) While the room opens, its top bar is in place and one muted line says what happens. On `/r/ABC123` with `nock.identity.ABC123` seeded and a mock that never answers the join, once `data-status="joining"`: at 360 by 740 in the desktop context, `room-topbar` is the phone top bar of spec 043 (54 px high, the window's width), with the `inert` attribute, no `timer` and no `timer-show`, and its children that show are `undo-button`, `aide-button`, `chat-toggle`, `pencil-toggle` and `menu-button`, at the places they have once joined (`menu-button`'s right edge 4 px from the window's right edge, each 56 px wide), with the label colour rgb(27, 47, 85); at 360 by 740 in the touch context the fourth is `keyboard-toggle`; at 1280 by 720 it is the computer top bar with `topbar-brand`, `undo-button`, `pencil-toggle`, `aide-button`, `chat-toggle` and `menu-button`. In each, `room-page` has `data-layout` (`"sheet"` at 360 by 740, `"column"` at 1280 by 720); `grid-area` has its top on `room-topbar`'s bottom and its bottom on the window's bottom (1 px) and holds only `room-status`, reading `fr.json["room.status.joining"]`, without the class `visually-hidden`, colour rgb(94, 101, 115), `font-size` 16 px, its centre within 1 px of `grid-area`'s centre; the room's `h1` has the class `visually-hidden`; there is no `grid-viewport`, `clue-bar`, `keyboard`, `salon`, `page-topbar` and no element with `role="progressbar"`. A `page.mouse.click` at the centre of `menu-button` opens no `room-menu` and sends no frame (spec 017's pings not counted). When the mock answers with a FX-01 snapshot, within 300 ms `room-topbar` has no `inert` attribute, `timer` shows, and `clue-bar` and `grid-viewport` are on the page.
- **AC-21** (new) (browser with mocked socket) The opening gives way to the page that the room's answer calls for. On `/r/ABC123` with `nock.room.ABC123` seeded `{"grid": 1, "selection": null}` (spec 012 case b): while the join is unanswered the page shows the opening of AC-20; when the mock answers `error` `room_full`, within 300 ms there is no `room-topbar` and no `data-layout`, and `entry-card` shows as in AC-17. In a second run, when the mock answers `error` `invalid_nickname` (spec 012 step 6), the page shows `nickname-form` as in AC-15, with `nickname-error` reading `fr.json["join.error.characters"]`. In a third run, the mock closes the socket with code 1011 before any snapshot: the page keeps the opening, `room-status` reading `fr.json["room.status.connecting"]`, with no `connection-banner` (spec 040).
- **AC-22** (new) (browser with live server and mocked routes; browser with mocked socket) Every page of this spec fits every window. At each window size of spec 006 AC-5: on `/` with `CAT`, `ROOMS2` (with 8 players of 20 characters in `XYZ789`), `HIST2` (with 7 team-mates of 20 characters in `XYZ789`) and accounts on and signed out; on `/g/2`; on `/r/ABC123` showing the nickname card with `nickname-error`; showing the `full` card; showing the `not_found` card; and showing the opening of AC-20: `document.documentElement.scrollWidth <= window.innerWidth`, `page-topbar` (or `room-topbar`) lies inside the window, and every `catalogue-item`, `my-room`, `history-item` and card lies inside its column's box horizontally, with each of its buttons and links inside its own box (1 px).
- **AC-23** (new) (browser with live server and mocked routes; browser with mocked socket; static) The pages of this spec pass spec 035's scans, and `fr.json` holds this spec's keys. At 1280 by 720 and at 360 by 740, in each of these states: `/` with `CAT`, `nock.progress` `{"1": "started", "2": "finished"}`, `ROOMS2` and `HIST2`; `/` loading, in error, empty, and with no grid of the selected force; `/` after a failed « Jouer »; `/` with `account-dialog` open signed out (after `account-error` for `ana@`) and signed in; `/g/2`; the nickname card with `nickname-error`; each of the five status cards of AC-17; the `not_found` card; the page not found; and the opening of AC-20: spec 035's contrast scan (its AC-8) and language scan (its AC-9, with the nicknames, the room codes and the dates as test data) find no offending element. Static: `web/src/i18n/fr.json` holds `share.home` with the value `Voir les grilles` and `room.status.not_found_detail` with the value `Un salon est effacé 30 jours après sa dernière modification.`, and none of `my_rooms.loading` and `my_rooms.empty`; no file under `web/src` contains `account-link`.

## Edge cases and errors

- Wide or narrow (AC-1, AC-2, AC-3): a window that changes from one to the other
  (a rotation, a resize) takes the other form within 300 ms; an open account
  dialog keeps its content and takes the other form's look.
- A portrait tablet (768 by 1024): narrow, so the entry pages have the phone's bar
  and padding, in a 420 px column; the catalogue keeps one card per row and no
  drawing (AC-8).
- The drawing's threshold (AC-8): it follows the list's width, not the window's, so
  it never shows on a card that is alone on its row because the window is narrow.
  A catalogue of one grid on a computer still has two columns, so its card has its
  drawing.
- Long texts (AC-11, AC-13, AC-22): the rows' lines wrap (spec 029 and 032 keep
  `overflow-wrap`), and the buttons never shrink, so a row grows in height, never
  in width.
- « Mes salons » that loads after the cards (AC-12): it appears above the filter row
  when its answer comes, which moves the cards down once; while loading it takes no
  room, so a page whose answer is empty never moves.
- The account dialog on the catalogue (AC-3): a sign-in link asked from the
  catalogue has no room (`"room": null`, as on the account page, spec 033); after
  the sign-in the page that opens is `/account`. Accounts that fail to answer show
  no « Compte » (spec 033's rule).
- A nickname refused by the server (AC-21): the form comes back with its error, the
  input keeps its text, as spec 012 step 6 says.
- `replaced` after a snapshot (spec 043): the room keeps its frame and shows the
  status band; this spec's card is only for a page that never had a snapshot.
- The opening (AC-20): its top bar is `inert`, so a tap there does nothing and no
  button takes the focus; the page announces nothing new, `room-status` being the
  same element whose text screen readers already read (spec 040). The opening may
  last only a few hundred milliseconds; its top bar does not change look when the
  snapshot comes, except the timer that appears and the pressed state of « Clavier »
  on a touch screen.
- A room code line is shown on every entry page of a room, `not_found` included
  (the player sees which code they followed); the page not found has none.
- No spinner, no skeleton, no animation anywhere (AC-9, AC-20).

## Out of scope

- The account page `/account`, the shared recap page, the operator page and their
  states (spec 048); the recap's states (spec 047).
- Grid credits on the cards (`_design.md` section 10, decision D2: not shown while
  no spec sends them).
- Searching, sorting or paging the catalogue; filtering by size (spec 004).
- A real thumbnail of each grid's layout (decided against by the human on
  2026-10-17).
- Making the brand a link; a second action on the status cards.
- Any change to the routes, the requests or the room page flow of specs 004, 010,
  012, 029, 032, 033 and 040.

## Work packages

None: one pull request.

## Decisions

Decided by the human on 2026-10-17 and 2026-10-22 (`_design.md` sections 8, 10 and
15): the catalogue's look and its generic drawing (2026-10-17); P1 (the entry and
plain pages on a computer: the phone's column, centred, at most 420 px, 48 px under
the 56 px top bar, on the page grey); P2 (the opening room); P3 (an expired room's
line and « Voir les grilles » primary); P4 (the catalogue's and « Mes salons »'s
states); P13 (the account sheet's intro outside a room); D2 (no grid credits).

Proposed by the spec writer, each already part of the spec above:

1. One threshold for every plain page: a window is wide when the room would show
   its computer top bar (landscape, at least 900 px wide, more than 500 px high), so
   no new breakpoint is added (P1's "no new breakpoint"; Open question 1).
2. The drawing shows while the list's content box is at least 812 px wide, the
   width that holds two 400 px columns and their gap: "more than one card per row"
   made exact, read from the list, not the window.
3. The catalogue's « Compte » opens spec 033's dialog, as the design draws it (P13),
   in place of the link to `/account`; the dialog keeps its ids, so the account
   page and the room keep theirs (Open question 2).
4. Test ids are kept wherever an element keeps its role (`catalogue-progress`,
   `catalogue-error`, `my-room-solved`, `my-room-link`, `history-*`,
   `nickname-form`, `room-status`, `not-found-page`), so the tests of specs 004,
   010, 012, 029, 032, 035 and 040 follow with the least change; new ids name only
   new elements (`page-topbar`, `page-body`, `page-column`, `catalogue-column`,
   `catalogue-filters`, `catalogue-thumb`, `catalogue-force-marks`, `meta-sep`,
   `entry-card`, `entry-detail`, `entry-home`, `my-rooms-error`, `history-title`,
   `history-line`, `my-room-title`).
5. `room-status` is the title of a status card, the room's `h1` the room code line,
   and the nickname form's `h2` the nickname card's title, so no text moves to a
   new element and spec 040's and spec 012's checks hold as written.
6. While the room opens its top bar is drawn as it will be once joined, and
   `inert`, rather than disabled: nothing changes look when the snapshot comes, and
   no button acts before the room exists (P2's "top bar in place"; Open question 3).
7. « Mes salons » keeps its element and `data-state` while loading or empty, with
   the `hidden` attribute, so spec 032's checks of its state hold and the page never
   moves for an empty answer.
8. « Voir les grilles » reuses spec 028's key `share.home` on every refusal card and
   the page not found, as spec 048's account and shared recap pages do: one string,
   one key, no new key.
9. The e-mail form of the catalogue's account sheet is spec 033's, shared with the
   account page and the room's sheet, so its look in error (the input's red border
   after a 422, spec 048 AC-5) is the same here; this spec adds no rule of its own
   for it.

## Open questions

The pick of each is already in the spec above; the human may change it at approval.

1. What "a computer (and any window wider than a phone)" is, for the entry pages'
   bar and padding and the catalogue's padding and « Compte » height. Options: (a)
   the room's threshold for its computer top bar (landscape, at least 900 px wide,
   more than 500 px high); (b) a width only, for example 600 px, so that a portrait
   tablet gets the computer form. Pick and recommendation: (a), no new number; a
   portrait tablet then has the phone's form in a centred 420 px column, which the
   screens sheet does not draw.
2. The catalogue's « Compte ». Options: (a) a button that opens the account sheet or
   dialog, as drawn (P13); (b) a link to `/account`, as spec 033 has it today, with
   no sheet on the catalogue. Pick and recommendation: (a), the design the human
   decided; (b) would be simpler (no dialog on the catalogue) and P13 would lapse.
   Either way, spec 033's catalogue item and its AC-11 are refined by the lead or
   the spec-writer of specs 047 and 048.
3. The room's top bar while it opens. Options: (a) drawn as once joined and
   `inert`; (b) its buttons `disabled`, in spec 043's disabled look (muted), until
   the snapshot; (c) no buttons until the snapshot, only the brand. Pick and
   recommendation: (a), which matches the screens sheet's drawing and changes no
   look when the snapshot comes; (b) makes the bar flash from muted to navy at each
   opening.
</content>
</invoke>
