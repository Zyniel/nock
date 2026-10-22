---
id: "043"
title: Room layout
status: approved
---

# 043 - Room layout

Epic E10 Quality bar · Release: MVP · No backlog story: this is build step 3 of
`specs/_design.md` (section 14). It applies `_design.md` section 8 (screens and
layout of the room: which layout, the phone and the computer layouts, the Aide
menu, the Menu, the Salon, the 3-second notes, the reactions, the connection band,
the room sheets, focus and keyboard, layers), section 9 only for the look of the
completion band ("End of grid"), section 11 (components), and the parts of
sections 2 (colour tokens and their jobs), 4 (interface type sizes) and 5 (icons,
text pictograms) that these screens use. It builds on spec 041 (tokens, fonts,
`web/src/lib/icons.ts`, the primitives `nock-button`, `nock-menu`,
`nock-menu-item`, `nock-menu-detail`, `nock-menu-heading`, `nock-menu-separator`,
`nock-badge`, `nock-note`, `nock-on-navy`) and on spec 042 (the grid cells, the
switches « Mots des autres » and « Accessibilité » with their test ids and storage
keys, `player-icon`) and redefines none of them. The FX-01 reference grid is in
`specs/_reference.md`; the stack in `specs/_architecture.md`.

## Goal

The human validated the look of the room page (`_design.md` section 8,
`docs/design/cell-sheet.html`) and asked on 2026-10-22 that the game be built on
that design. This spec replaces today's room header, toolbar, roster, feed, host
panel and chat panel by the design's room: a top bar, the Aide and Menu popovers,
the Salon (a bottom sheet on a phone, a side column on a wide window) holding one
stream of messages and events and the Joueurs list with each player's current
clue, the host's settings and the account in room sheets, the navy clue bar with
« Réagir » and « Je bloque », the reaction pill, the 3-second notes and the
connection band. The rule of the human holds throughout: the simplest design that
removes edge cases. The toolbar that scrolls sideways, its edge fades, the
compact remove button and the low-window rows of roster, feed and host panel go,
with the rules and tests that existed only for them.

## Public interface

No new Python name, no new protocol message, no new HTTP route. Client only
(`web/`: chiefly `web/src/lib/RoomPage.svelte`, split as the implementer likes into
components such as a top bar, the two popovers, the Salon, the clue bar and the
room sheets; `ChatPanel.svelte` and the roster markup are folded into the Salon).
Every colour is a token of spec 041 used for its job in `_design.md` section 2,
every icon comes from `ICONS` of `web/src/lib/icons.ts`, every string from
`web/src/i18n/fr.json`.

### Terms

- Sheet layout and column layout: the two layouts of `_design.md` section 8 ("Which
  layout"), chosen as "Which layout" below says.
- Phone top bar and computer top bar: the two forms of `room-topbar` (see "Top
  bar"). The phone top bar is used in the sheet layout and in the column layout on
  a window at most 500 px high (`window.innerHeight <= 500`); the computer top bar
  only in the column layout on a window more than 500 px high. (Note from the lead,
  2026-10-22: added, the lead's decision recorded as spec 044's Decision 8: the
  computer top bar needs about 650 px, more than the 568 to 740 px of a low
  column-layout window.)
- Popover: the Aide menu (`aide-menu`) or the Menu (`room-menu`).
- The Salon: `data-testid="salon"`, the bottom sheet of the sheet layout or the side
  column of the column layout.
- Open: a popover or the Salon is open while it is shown (no `hidden` attribute).
- The stream is shown while the Salon is open with its Discussion tab selected.
- The in-app keyboard is shown on a touch screen (`(pointer: coarse)`, spec 009)
  and nowhere else; step 4 adds the « Clavier » button that hides it. "The in-app
  keyboard is hidden" therefore means, in this spec, "the page is not on a touch
  screen". (Note from the lead, 2026-10-22: refined by spec 044, the design's
  keyboard: the in-app keyboard shows when the page has a snapshot, is on a touch
  screen, the player has not hidden it with « Clavier »
  (`localStorage["nock.keyboard_hidden"]`) and the grid is not solved; otherwise
  it is hidden and absent. Every rule of this spec that reads "the in-app keyboard
  is hidden", or "on a touch screen" for `keyboard`, reads spec 044's definition.)
- A pictogram is one of the text glyphs of `_design.md` section 5 (→ ← ✓ ▲ ✎ ▾ and
  the direction glyphs → ↓ of the clue bar). It is drawn by CSS generated content
  (`::before` or `::after`) on an element with `aria-hidden="true"` and no text
  node, so that it is never part of a text that the page, a test or a screen reader
  reads. The flag pictogram is a drawn icon (`ICONS.flag`), as `_design.md` says.

### Which layout (`_design.md` section 8)

`room-page` (spec 040) gains `data-layout`, `"sheet"` or `"column"`, once the page
has a snapshot:

- `"column"` when `window.innerWidth > window.innerHeight` and either
  (`window.innerWidth >= 900` and `window.innerHeight > 500`), or
  (`window.innerHeight <= 500` and the in-app keyboard is hidden);
- `"sheet"` otherwise.

It follows each resize and rotation within 300 ms. A change of layout closes the
popovers and the reaction picker; the Salon keeps its own state in each layout
(see "Salon").

### Document order

Once the page has a snapshot, the room page holds, in this document order:

1. `room-topbar` (a `header`);
2. `aide-menu` and `room-menu`;
3. `connection-banner` (spec 017) while reconnecting, and `room-status` (spec 040);
4. the play area: `grid-area` (holding spec 025's `vote-announcement` and
   `vote-banner`, `room-note`, `undo-message` and `grid-viewport`), `clue-bar`,
   `reaction-picker` while open, `grid-status` while shown (spec 026), `keyboard`
   on a touch screen (spec 009) (Note from the lead, 2026-10-22: refined by spec
   044: `keyboard` while it shows, by spec 044's definition);
5. `salon`;
6. `room-scrim`;
7. the dialogs: `host-settings`, `account-dialog` (spec 033), `recap` (spec 028).

The room's `h1` (spec 040, « Salon {code} ») stays first in `room-page`, with the
class `visually-hidden` (lead's decision of 2026-10-22, `_design.md` section 15
item 10). Before the first snapshot, and when no snapshot ever came (spec 040's
final statuses before a join, the nickname form of spec 012), the page keeps
today's content and look; step 5 redraws those pages.

### Top bar (`_design.md` section 8)

`data-testid="room-topbar"`: a `header`, white, with a 1 px solid `--nock-line`
bottom border, full window width, at the top of the window.

Phone top bar (Note from the lead, 2026-10-22: this read "Sheet layout"; it is also
the top bar of the column layout on a window at most 500 px high, see "Terms"): 54
px high (its border included), padding 0 4 px 0 10 px, items
centred vertically. In this order: the timer slot (`timer`, or `timer-show` while
the timer is hidden), then, pushed right (`margin-right: auto` on the timer slot),
five top-bar buttons: `undo-button`, `aide-button`, `chat-toggle`, `pencil-toggle`,
`menu-button`. Each is as high as the bar's content (53 px) and has a flex basis of
56 px; when the bar is short of room they shrink equally, never below 40 px; the
timer slot never shrinks. Each holds its 22 px icon (stroke width 1.8) above its
label (gap 2 px), the label in 500 0.68rem/1 `--nock-font-ui`, navy, on one line.
The fourth slot holds « Crayon » in this step; step 4 puts « Clavier » there and
moves the pencil toggle to the ✎ key (Decision 6). (Note from the lead, 2026-10-22:
refined by spec 044, the design's keyboard: on a touch screen the fourth slot is
`keyboard-toggle` (« Clavier ») and there is no `pencil-toggle`, the ✎ key
`key-pencil` being the pencil toggle; off a touch screen the fourth slot keeps
`pencil-toggle`. In the computer top bar on a touch screen, `keyboard-toggle` comes
between `chat-toggle` and `menu-button`, and `pencil-toggle` stays after
`undo-button`. Once the grid is solved, `keyboard-toggle` is a disabled top-bar
button.) (Note from the lead, 2026-10-22: the phone top bar has these slots and
this order in both layouts, so a touch screen in the column layout on a low window
has `keyboard-toggle` in the fourth slot and no `pencil-toggle`.)

Computer top bar (Note from the lead, 2026-10-22: this read "Column layout"; it is
used only in the column layout on a window more than 500 px high, see "Terms"): 56
px high, padding 0 16 px, gap 4 px, items centred vertically. In
this order: `topbar-brand` (the Nock mark, an `svg` with `viewBox="0 0 10 14"`, 12
by 18 px, holding one `polygon` with `NOCK_MARK_POINTS`, filled navy, then the
text `t("app.title")`, 700 1.3rem/1, navy, letter spacing 0.01em; gap 8 px) with
`margin-right: auto`; the timer slot, with a 10 px right margin; then the buttons
`undo-button`, `pencil-toggle`, `aide-button`, `chat-toggle`, `menu-button`, 38 px
high, padding 0 12 px, radius 6 px, gap 6 px, each with its 20 px icon (stroke
width 1.8) beside its label (500 0.92rem/1, navy). `aide-button` ends with
`aide-caret`, the ▾ pictogram. The grid name of the design (« Grille n° N · Force
F ») is not shown in this step (Open question 6).

Every top-bar button is a `<button type="button">`, transparent background, no
border, navy icon and label; its icon is an `svg` with `aria-hidden="true"`; its
accessible name is its label unless this spec gives an `aria-label`:

| `data-testid` | Icon | Label | State attribute | Pressed look |
| --- | --- | --- | --- | --- |
| `undo-button` (spec 018) | `undo` | `t("room.undo")` | - | - |
| `aide-button` | `aide` | `t("topbar.aide")` | `aria-expanded`, `aria-controls="aide-menu"` | `--nock-word` background while open |
| `chat-toggle` (spec 022, the « Salon » button) | `salon` | `t("topbar.salon")` | `aria-expanded`, `aria-controls="salon"` | `--nock-word` background while the Salon is open |
| `pencil-toggle` (spec 020) | `crayon` | `t("pencil.toggle")` | `aria-pressed` | `--nock-word` background while pressed |
| `menu-button` | `menu` | `t("topbar.menu")` | `aria-expanded`, `aria-controls="room-menu"` | `--nock-word` background while open |

A disabled top-bar button (`undo-button` and `pencil-toggle` once the grid is
solved, specs 020 and 026) has its icon and label in `--nock-muted`, a transparent
background and `cursor: not-allowed`.

The unread badge and the new-events dot, on `chat-toggle`:

- `chat-unread` (spec 022: its text, its presence and `aria-hidden`) is a
  `nock-badge`, absolutely placed: top 5 px and right 8 px of `chat-toggle`'s box
  in the sheet layout, top 2 px and left 24 px in the column layout.
- `data-testid="salon-dot"`, an 8 px circle in `--nock-red`, `aria-hidden="true"`,
  no text, at top 8 px and right 15 px of `chat-toggle`'s box in the sheet layout,
  and at the badge's place in the column layout (`_design.md` section 15 item 9).
- (Note from the lead, 2026-10-22: in the two items above, and for `timer-show`'s
  place, "sheet layout" reads "phone top bar" and "column layout" reads "computer
  top bar".)
  It shows while at least one event line by another player came since the stream
  was last shown (see "Discussion") and no message is unread; otherwise it is
  absent.
- `chat-toggle`'s `aria-label`: `t("topbar.salon_unread", { count })` while the
  badge shows, `t("topbar.salon_events")` while the dot shows, none otherwise.

The timer (spec 027):

- `timer` keeps spec 027's attributes and text. It is text, not a button (Open
  question 7): 600 1.15rem/1, navy, `font-variant-numeric: tabular-nums`, one
  line, padding 0 4 px.
- While the timer is hidden (spec 027's `nock.timer_hidden`), the slot holds
  `data-testid="timer-show"`, a top-bar button with the `chrono` icon and the label
  `t("timer.label")` (« Chrono »), `aria-label` `t("timer.toggle_label")`
  (« Afficher le chrono »). A click shows the timer and removes the key, as spec
  027's toggle did. It sends nothing.
- The hide control is the Menu item `timer-toggle` (see "Menu").

### Connection band and status (specs 017, 040)

- `connection-banner` (spec 017, same text `t("room.banner.offline")`, `role`
  `status`, same presence rules) is the connection band: under the top bar, full
  width, in the flow (it pushes the play area down; nothing covers the grid),
  background `--nock-clue-bg`, a 1 px solid `--nock-line` bottom border, padding
  8 px 12 px, gap 10 px, items aligned to the top; first
  `data-testid="connection-dot"`, an 8 px `--nock-red` circle, `aria-hidden`, 5 px
  from the band's content top; then the text, 500 0.85rem/1.3, `--nock-ink`.
- `room-status` (spec 040) has the class `visually-hidden` while `data-status` is
  `joined` or `reconnecting`. In any other status once the page has a snapshot
  (`removed`, `replaced` and the others of specs 011, 012, 014 and 040), it is the
  status band: the connection band's look without the dot, under the top bar,
  showing its text.

### Aide menu (`_design.md` section 8, specs 020, 023, 024, 025)

`data-testid="aide-menu"`, `id="aide-menu"`, a `nock-menu` with `role="group"` and
the `aria-label` `t("topbar.aide")`, in this order:

1. While the selected cell shows a pencil letter, is not locked and the grid is not
   solved (spec 020's enabling rule): `confirm-pencil` (spec 020), a
   `nock-menu-item` with the text `t("pencil.confirm")` in weight 600 and the ✎
   pictogram as its detail; then a `nock-menu-separator`. Otherwise neither is on
   the page.
2. While the kept `help_mode` is not `none` (specs 023, 024, 025):
   - `check-panel` (spec 023), a `role="group"` labelled (`aria-labelledby`) by its
     `nock-menu-heading` `data-testid="check-heading"`, text `t("check.label")`
     (« Vérifier »), holding the items `check-letter`, `check-word`, `check-grid`
     with the texts `t("check.letter")`, `t("check.word")`, `t("check.grid")`
     (« La lettre », « Le mot », « La grille »), no `aria-label`;
   - a `nock-menu-separator`;
   - `reveal-panel` (spec 024), the same with the heading `reveal-heading`
     (`t("reveal.label")`, « Révéler ») and the items `reveal-letter` and
     `reveal-word`, texts `t("reveal.letter")` and `t("reveal.word")` (« La
     lettre », « Le mot »), no `aria-label`, each with a `nock-menu-detail`
     (`reveal-letter-detail`, `reveal-word-detail`) holding what is left (`letters`,
     `words`, spec 024): `t("reveal.letters_left_one")` when 1,
     `t("reveal.letters_left", { count })` when more, `t("reveal.letter_none")` when
     0; for words `t("reveal.words_left_one")`, `t("reveal.words_left", { count })`,
     `t("reveal.word_none")`.
3. When the menu would hold nothing (help mode `none` and no pencil letter
   selected): `data-testid="aide-empty"`, a line in the `nock-menu-heading` margins,
   500 0.85rem/1.3, `--nock-muted`, text `t("aide.empty")`.

The items keep the test ids, the sending rules, the disabled rules and the
"sends once, does not move the selection" rules of specs 020, 023, 024, 025 and
026. A disabled item has its text and detail in `--nock-muted`, no hover
background and `cursor: not-allowed`. Activating an enabled item closes the menu,
puts the focus back on `aide-button`, then sends its message.

The Aide menu is never removed for help mode `none` (Open question 4): the pencil
confirm lives there on a computer.

### Menu (`_design.md` section 8, specs 019, 027, 033, 042)

`data-testid="room-menu"`, `id="room-menu"`, a `nock-menu` with `role="group"` and
the `aria-label` `t("topbar.menu")`, in this order. Each item is a
`nock-menu-item`; its label is in a `span`, its detail is a `nock-menu-detail`
with `aria-hidden="true"`, so the accessible name is the label.

| Item | `data-testid` | Label | Detail | Present |
| --- | --- | --- | --- | --- |
| Auteurs (spec 019) | `authors-switch` | `t("authors.switch")` | `t("authors.on")` / `t("authors.off")` | always |
| Mots des autres (spec 042) | `others-tint-switch` | `t("others_tint.switch")` | `t("others_tint.on")` / `t("others_tint.off")` | always |
| Accessibilité (spec 042) | `access-switch` | `t("access.switch")` | `t("access.on")` / `t("access.off")` | always |
| Inviter | `invite-open` | `t("menu.invite")` | `t("menu.invite_detail")` | always |
| Réglages de l'hôte | `host-settings-open` | `t("settings.heading")` | - | while `you` is host |
| Compte (spec 033) | `account-open` | `t("account.open")` | - | while accounts are on (spec 033) |
| separator | - | - | - | always |
| Masquer le chrono (spec 027) | `timer-toggle` | `t("timer.hide")`, or `t("timer.toggle_label")` while hidden | - | always |
| Retour aux grilles | `back-to-grids` | `t("menu.back")` | - | always |

- The three switches keep their `aria-pressed`, storage keys and behaviour (spec
  019: off at each load until step 5; spec 042: `nock.others_tint` and
  `nock.accessibility`). Activating one flips it and leaves the Menu open with the
  focus on it; its detail follows.
- `invite-open` closes the Menu, opens the Salon on its Joueurs tab and puts the
  focus on `copy-link`.
- `host-settings-open` closes the Menu and opens `host-settings`; `account-open`
  closes the Menu and opens `account-dialog` (spec 033's opening rules). When either
  closes, the focus goes to `menu-button`.
- `timer-toggle` closes the Menu, hides or shows the timer as spec 027's toggle did
  (same storage, sends nothing), and puts the focus on `menu-button`. It has no
  `aria-pressed`: its label says what it does.
- `back-to-grids` is an `<a href="/">` with the item's look.

### Popovers: shared rules (`_design.md` sections 8 and 11)

- Look: spec 041's `nock-menu` (white, radius 8 px, padding 6 px 0, min width
  220 px, its shadow, no border). Layer 8.
- Place, sheet layout: top 58 px from the window's top. `room-menu`'s right edge is
  6 px from the window's right edge. `aide-menu`'s left edge is `aide-button`'s
  left edge, moved left if needed so that its right edge stays at least 6 px inside
  the window.
- Place, column layout: top 4 px under the top bar; `aide-menu`'s left edge is
  `aide-button`'s left edge, `room-menu`'s right edge is `menu-button`'s right
  edge.
- (Note from the lead, 2026-10-22: the place follows the top bar's form: "sheet
  layout" in the two items above reads "phone top bar" and "column layout" reads
  "computer top bar". The scrim, the Salon and the room sheets keep following the
  layout.)
- Height: at most the window's height less its top and 6 px; its content scrolls
  inside it when higher (the Menu is about 300 px high, more than a window of 320
  px allows under the top bar).
- A click on the popover's button opens it, a second click closes it. Opening one
  moves the focus to its first enabled item, or to the popover itself (with
  `tabindex="-1"`) when it holds no enabled item.
- `Escape` while the focus is inside closes it and puts the focus on its button.
- Column layout: a `pointerdown` outside the popover and its button closes it,
  leaving the focus where the pointer puts it.
- Sheet layout: `data-testid="room-scrim"`, `aria-hidden="true"`, fixed, from 54 px
  below the window's top to its bottom, full width, `--nock-scrim`, layer 7, shows
  while a popover or the Salon is open; a tap or click on it closes them and moves
  no focus.
- One at a time: in the sheet layout at most one of `aide-menu`, `room-menu`, the
  Salon and `reaction-picker` is open, and opening one closes the others; in the
  column layout at most one of `aide-menu`, `room-menu` and `reaction-picker` is
  open, the Salon column being independent of them.
- A closed popover stays in the DOM with the `hidden` attribute, so its items keep
  their attributes and texts (for example `disabled`) while it is closed.

### Salon (`_design.md` section 8)

`data-testid="salon"`, `id="salon"`: an `aside` with the `aria-label`
`t("topbar.salon")`, white, always in the DOM once the page has a snapshot; closed,
it has the `hidden` attribute.

Sheet layout:

- Closed when the page loads. `chat-toggle` opens and closes it; `Escape` inside it
  closes it and puts the focus on `chat-toggle`.
- A bottom sheet: fixed, full width, its bottom on the window's bottom, height 62 %
  of `window.innerHeight`, top corners radius 14 px, shadow
  `0 -10px 30px -12px var(--nock-shadow)`, layer 8, over the play area (it moves
  nothing under it). At its top `data-testid="salon-handle"`, `aria-hidden`, 40 by
  4 px, radius 2 px, `--nock-handle`, margin 8 px auto 4 px (decorative: no drag in
  this step).

Column layout:

- A side column on the right of the play area, 340 px wide, white, a 1 px solid
  `--nock-line` left border, from under the top bar (and bands) to the window's
  bottom, in the flow: opening or closing it changes the play area's width, and
  the grid refits.
- Open when the page loads, unless `localStorage["nock.salon_closed"]` is `"true"`
  (decided by the human on 2026-10-16). `chat-toggle` closes it (writing `"true"`)
  and opens it again (removing the key). `Escape` inside it puts the focus on
  `chat-toggle` and leaves it open.

Opening the Salon with `chat-toggle` moves the focus into it: to `chat-input` when
its Discussion tab is selected and `chat-input` is enabled, else to the selected
tab. The Salon opened by the page itself at load (column layout) takes no focus.

Content, top to bottom:

1. `data-testid="salon-progress"`: `salon-progress-text`, the text
   `t("salon.progress", { filled, total })`, 600 0.85rem/1, navy, tabular, where
   `total` is the number of words of the grid and `filled` the number of words
   whose every cell shows a letter on the page (pending edits included); then
   `salon-progress-bar`, `aria-hidden`, 6 px high, radius 3 px, track
   `--nock-word`, a navy fill as wide as `filled / total` of the track (1 px).
   Padding 4 px 16 px 8 px (14 px top in the column layout), gap 10 px.
2. `data-testid="salon-tabs"`, a `role="tablist"`: two `role="tab"` buttons of
   equal width, `salon-tab-discussion` (`t("chat.heading")`, « Discussion ») and
   `salon-tab-players` (`t("salon.players_tab", { count })`, count the number of
   players of the snapshot), each with `aria-selected` and `aria-controls`, padding
   10 px, 600 0.95rem/1, `--nock-muted` text and a 2 px transparent bottom border,
   navy text and navy bottom border when selected; a 1 px solid `--nock-line`
   border under the row. The selected tab has `tabindex="0"`, the other
   `tabindex="-1"`; `ArrowLeft` and `ArrowRight` on a tab select the other tab and
   move the focus to it; a click selects. Discussion is selected at load; the
   choice holds for the page's life.
3. The tab panels, `role="tabpanel"`, each `aria-labelledby` its tab, the
   unselected one with the `hidden` attribute: `chat-panel` (Discussion) and
   `roster` (Joueurs). The panel fills the Salon's height left.

### Discussion: the stream (specs 013, 022, 034)

`chat-panel` (spec 022's id) holds a visually hidden `h2` `id="chat-heading"`
(`t("chat.heading")`), `data-testid="activity-feed"` (spec 013's id, now the
stream), the message box, then the slot of the chat notes (spec 022).

- `activity-feed` holds one `ul`, `data-testid="chat-list"`, `role="list"`,
  `aria-labelledby="chat-heading"`: the stream. It holds spec 022's `chat-message`
  items and spec 013's (and spec 034's) `feed-item` items, in `seq` order, oldest
  first; two items of one seq keep the order their spec gives. The stream keeps the
  last 200 messages (spec 022) and the last 100 event lines (spec 013), each kind
  counted on its own. Padding 10 px 16 px, items 8 px apart; the list fills the
  panel's height above the message box and scrolls.
- Spec 013's "Client: feed scroll position" applies to the stream list, any item
  being a new line; spec 035's "Scrolling lists" applies to it (it holds no
  focusable element).
- A message (`chat-message`, spec 022's attributes and children): first
  `data-testid="chat-dot"` with `data-colour`, the player dot of `_design.md`
  section 11 (10 px circle in `--player-colour-N`, ring
  `0 0 0 1px var(--nock-dot-ring)`), present only when the line's player is a
  player of the kept snapshot; then `chat-author` in 700, `--nock-ink`, gap 6 px;
  then `chat-text`; 400 0.92rem, `--nock-ink`. While `access-switch` is on,
  `chat-dot` has a transparent background and no ring and holds one `player-icon`
  `svg` of 12 by 12 px for that colour index (spec 042's rule for `roster-colour`).
- An event line (`feed-item`, spec 013's attributes and text): 400 0.82rem,
  padding-left 16 px, `--nock-muted`, starting with `data-testid="feed-picto"` by
  `data-kind`: `player_joined` →, `player_left`, `player_removed` and
  `player_timed_out` ← (`_design.md` section 15 item 11), `check` ✓, `reveal` ▲,
  `flag` the filled flag icon (`ICONS.flag`, 1em, `vertical-align: -0.15em`, pole
  unfilled, stroke width 2, `currentColor`); the other kinds have no pictogram. A
  `check` line whose `check_result` had an empty `wrong` list has `data-ok="true"`
  and the colour `--nock-green`; a `reveal` line has the colour `--nock-reveal`. The
  `feed-item`'s text content is exactly spec 013's text.
- No line is added for typed letters or filled words (`_design.md` section 8);
  spec 034's catch-up lines, `word_completed` included, keep their rules and take
  the event look (Open question 11).
- Message box: the chat form of spec 022 (`chat-input`, `chat-send`, its label),
  padding 8 px 12 px 12 px, a 1 px solid `--nock-line` top border, gap 8 px;
  `chat-input` with a 1 px solid `--nock-rule` border, radius 18 px, padding 7 px
  12 px, 400 0.9rem, placeholder in `--nock-muted`; `chat-send` the « Envoyer »
  pill (`--nock-word` background, navy, 600 0.85rem, radius 14 px, padding 6 px
  12 px, no border).
- The chat notes' slot (spec 022) follows the message box, padding 0 12px 8px,
  500 0.85rem/1.3, `--nock-muted`.

Read and unread (refines spec 022's "Unread lines"): `lastSeenChatSeq` is the seq
of the newest line of the history while the stream is shown (in place of "while
the panel is open"); `chat-unread` shows while the stream is not shown and a line
is unread. The new-events dot: the page notes the seq of the newest event line
when the stream is last shown; an event line added since then whose event's
`player_id` is not `you` makes `salon-dot` show (while no message is unread);
showing the stream removes it.

### Joueurs (specs 011, 012, 013, 014, 022, 035)

`roster` (spec 012's id) holds a visually hidden `h2` `id="roster-heading"`
(`t("roster.heading")`, « Joueurs »), the players' `ul` (spec 012, `role="list"`,
`aria-labelledby="roster-heading"`), then `share-panel`. Padding 10 px 16 px. The
panel scrolls vertically when its content is higher than it; the `ul` never scrolls
on its own.

Each `roster-player` (spec 012's attributes; rows 8 px apart, 0.95rem) is two
lines:

- Line 1: `roster-colour` (the player dot of `_design.md` section 11, 10 px, ring
  `0 0 0 1px var(--nock-dot-ring)`; spec 042's 12 px icon while `access-switch` is
  on); `roster-nickname` (400, `--nock-ink`; 700 on my own row; spec 035 AC-7's
  italic and struck-through styles); on my own row `roster-you`
  (`t("roster.you")`, 400 `--nock-muted`); on the host's row `roster-host`
  (`t("roster.host")`), the « hôte » tag of `_design.md` section 11 (`--nock-clue-bg`
  background, navy 600 0.72rem/1.3, radius 10 px, padding 2 px 8 px); then, pushed
  right, while `you` is host and on another player's row, `mute-player` (spec 022's
  attributes, texts and labels) and `remove-player` (spec 014's text
  `t("host.remove")` and `aria-label`), both small secondary buttons (`nock-button
  nock-button-secondary`, padding 6 px 10 px, 0.8rem), 6 px apart.
- Line 2, its left edge on `roster-nickname`'s left edge: `roster-state` (spec
  013's text), 0.85rem, `--nock-muted`; then, while the player has a selection,
  `data-testid="roster-sep"` (`aria-hidden`, the « · » drawn as a pictogram) and
  `data-testid="roster-clue"`, the text of the clue of the word of that player's
  selection (spec 007's word of a cell and a direction), 0.85rem, `--nock-muted`,
  one line, ending with an ellipsis when too long. For `you`, the clue of my own
  selected word. A player with no selection (none yet, or disconnected) has neither.
  `roster-clue` follows each `selection_moved` and each snapshot within 300 ms.

The Joueurs list is the sign, in words, of where each player is (`_design.md`
section 6); it is why the triangles may carry colour only.

`share-panel` (spec 011's id), under the rows, 14 px below the last row:

- `data-testid="share-label"`, `t("room.share.label")`, in the dialog section
  heading style (600 0.78rem/1.2, uppercase, letter spacing 0.07em,
  `--nock-muted`);
- `share-link` (spec 011: an `<a>`, `href` and text the link, `tabindex="0"`,
  `aria-describedby="share-label"`), the URL box: block, full width, 1 px solid
  `--nock-rule` border, radius 6 px, padding 8 px 10 px, 400 0.85rem, one line with
  an ellipsis;
- `copy-link` (spec 011), `nock-button nock-button-primary`, text
  `t("room.share.copy")` at all times;
- after a successful copy, `data-testid="share-copied"`, `role="status"`, the
  confirmation line of `_design.md` section 11 (500 0.85rem/1.3, `--nock-green`),
  text `t("room.share.copied")`, for 2 seconds (spec 011's time). Without a usable
  clipboard nothing changes.

### Room sheets (`_design.md` section 8, specs 014 and 033)

`host-settings` and `account-dialog` are `<dialog>` elements opened with
`showModal()`, `aria-labelledby` their title:

- Column layout: centred, 440 px wide (at most the window width less 32 px), white,
  radius 12 px, padding 20 px 22 px, gap 14 px, shadow
  `0 20px 40px -16px var(--nock-shadow-strong)`; the backdrop `--nock-scrim` over
  the whole window.
- Sheet layout: a bottom sheet: full width, its bottom on the window's bottom, at
  most the window height less 54 px high, its content scrolling inside when higher,
  white, top corners radius 16 px, padding 14 px 18 px 18 px, gap 14 px, no handle;
  the backdrop `--nock-scrim` from 54 px below the window's top (the top bar stays
  visible, and inert while the sheet is open).
- Title: 700 1.2rem/1.2, navy. `Escape`, or a click on the backdrop, closes the
  dialog; the focus then goes back to `menu-button`.

`data-testid="host-settings"` (spec 014), present on the page while `you` is host,
holds in this order:

1. The title, `t("settings.heading")` (« Réglages de l'hôte »).
2. A switch row: the label `t("host.lock")` (500 0.95rem/1.2, ink) on the left and
   `lock-room` on the right (gap 10 px): a `<button type="button">` with
   `aria-pressed` equal to `settings.locked` (spec 014) and the `aria-label`
   `t("host.lock")`, drawn as the switch of `_design.md` section 11 (track 42 by
   24 px, radius 12 px, `--nock-rule` when off, navy when on; knob an 18 px white
   circle, 3 px from the top, left 3 px off and 21 px on). A click sends spec 014's
   `lock_room` at once.
3. `settings-form` (spec 014), holding:
   - `help-mode-select`: a `fieldset` whose `legend` is
     `t("settings.help_mode_label")` (field label style, 600 0.85rem/1.2, ink),
     holding three `<input type="radio" name="help-mode">` with the values `free`,
     `vote`, `none`, each `data-testid="help-mode-option"`, labelled
     `t("settings.help_mode.<mode>")`, drawn as the segmented control of `_design.md`
     section 11 (1 px navy border, radius 6 px; options padding 8 px 10 px, 600
     0.85rem/1, navy, 1 px navy dividers; the checked one navy background and white
     text). The checked radio is the room's mode;
   - two fields side by side, 16 px apart: `reveal-letters-input` and
     `reveal-words-input` (spec 014's limits and labels), number inputs 64 px wide,
     text centred, label above (gap 6 px). Each field is a group of its `<label>`
     (the field label style, 600 0.85rem/1.2, ink, on one line) above its input,
     the input's left edge on the label's left edge; the group is as wide as the
     wider of the two, and the 16 px are between the two groups (the second
     group's left edge 16 px right of the first group's right edge), not between
     the inputs. (Note from the lead, 2026-10-22: the three sentences before this
     note were added, after spec 043 WP-1's test-writer read "16 px apart" on the
     inputs, which would make each label wrap in 64 px; they say what `_design.md`
     section 8 and the screens sheet's host settings draw, and the look does not
     change.);
   - `settings-save` (`t("settings.save")`), `nock-button nock-button-primary`,
     right-aligned. Submitting sends spec 014's `change_settings` and closes the
     dialog.

`account-dialog` (spec 033) keeps its content, ids and rules; its look is the one
above, with `_design.md` section 8's "Account" (the intro text muted 0.9rem, the
field « Adresse e-mail », the primary send button, the green line after sending,
the secondary « Fermer » right-aligned).

### Clue bar (`_design.md` section 8, specs 007, 019, 021, 022)

`clue-bar` (spec 007's id, `role`, `aria-label` and `data-word`) has the class
`nock-on-navy`, is 34 px high, and holds in this order:

1. `data-testid="clue-prev"`, a `<button type="button">` 36 px wide and the bar's
   height, the `chevron-left` icon (20 px, stroke width 2, white), `aria-label`
   `t("clue_bar.previous")`;
2. `clue-bar-text` (spec 007), centred, 500 0.95rem/1.2, white, on one line with an
   ellipsis (`white-space: nowrap`, `overflow: hidden`, `text-overflow: ellipsis`),
   its text content the clue (or `t("clue_bar.empty")`), followed while a word is
   selected by `data-testid="clue-bar-direction"`, the → (across) or ↓ (down)
   pictogram at opacity 0.8 with a 6 px left margin; spec 019's `clue-bar-author`,
   while it shows (until step 5 removes it), follows on the same line in white with
   spec 019's shrinking rules; and spec 026's `grid-status` when it sits in the row
   (see "Completion status");
3. `react-button` (spec 022): 40 px wide, radius 6 px, the `smile` icon, no visible
   text, `aria-label` `t("reaction.button_label")` (spec 022's other attributes and
   disabled rules, plus Decision 10);
4. `flag-button` (spec 021): 40 px wide, radius 6 px, the `flag` icon, no visible
   text, `aria-label` `t("flag.button_label")` (spec 021's other attributes and
   rules). Not pressed: the outline flag in white. Pressed (`aria-pressed="true"`):
   a `--nock-white` background and the filled flag in navy;
5. `data-testid="clue-next"`, as `clue-prev` with `chevron-right` and
   `t("clue_bar.next")`.

- `react-button` while the picker is open (`aria-expanded="true"`): the pressed
  look of `flag-button` with the smile icon in navy.
- A disabled `react-button` or `flag-button` draws its icon in `--nock-rule`
  (5.22:1 on navy) with `cursor: not-allowed` (Open question 10).
- The focus ring inside the bar is spec 041's `nock-on-navy` ring (white, offset
  −4 px). On a button with the white pressed background (`flag-button` pressed,
  `react-button` while the picker is open) the ring is navy, so that it is never
  white on white. Spec 035 AC-2's contrast check of a ring is measured against the
  surface behind the ring (the button's background here), as `_design.md` section
  12 asks of spec 035.
- `clue-next` does what `Tab` does in the grid (spec 009, "Tab and Shift+Tab"),
  `clue-prev` what `Shift+Tab` does, whether or not the grid has the focus. A
  pointer press on either does not move the focus (the page prevents the pointer's
  default focus), so typing goes on in the grid; a keyboard activation leaves the
  focus on the button.
- Width: in the sheet layout the bar is as wide as the window. In the column layout
  it is as wide as the grid's box at zoom 1, but never narrower than the smaller of
  320 px and the play area's content width, and it is centred under the grid.

### Reactions (`_design.md` section 8, spec 022)

- `reaction-picker` (spec 022's id, role, label and options) sits over the bottom of
  `grid-viewport`: centred on it horizontally, its bottom 8 px above the viewport's
  bottom, layer 9; white, 1 px solid `--nock-line` border, radius 24 px, padding
  5 px, gap 2 px, shadow `0 10px 24px -10px var(--nock-shadow)`. Each
  `reaction-option` is a 40 by 40 px round button (radius 20 px), no background
  (`--nock-word` on hover), emoji 22 px.
- A shown reaction (`clue-reaction`, spec 022's attributes, text and timing): a
  white pill, 1 px solid `--nock-line` border, radius 12 px, padding 2 px 6 px,
  emoji 16 px with line height 1.2, shadow `0 4px 10px -4px var(--nock-shadow-soft)`,
  layer 8, centred on its `clue` element (one half of a two-clue cell, the whole
  cell for a lone clue), drawn over the neighbouring cells.

### 3-second notes (`_design.md` section 8)

`data-testid="room-note"`: a `nock-note` (spec 041), a `<button type="button">` with
`tabindex="-1"` and `aria-hidden="true"` (other players' actions are not announced,
spec 022), centred horizontally on `grid-viewport`, its top 8 px below the
viewport's top, layer 6. It takes no room (no layout shift).

- A note is made, with its text, for: a `chat_message` whose player is not `you`
  (`t("note.message", { name, text })`); an added event line (spec 013) of kind
  `flag`, `reveal`, `player_joined`, `player_left`, `player_removed` or
  `player_timed_out`, and of kind `check` when its player is not `you` (the line's
  text, after the line's pictogram); and the `reaction` frame of `you`
  (`t("note.own_reaction", { reaction })`, `reaction` the emoji
  `t("reaction.<value>")`). Catch-up lines (spec 034) and the snapshot make no note.
  (Note from the lead, 2026-10-22: refined by spec 047, the design's room overlays:
  an added event line of kind `vote` (a closed vote, spec 047) makes a note too,
  with the line's text and no pictogram; it is made once the banner has left, so it
  is never held back, and as the newest note it replaces one that waited during the
  vote.)
- One at a time: a new note replaces the shown one at once. A note shows for
  3,000 ms, then gets `data-off` (spec 041's fade, 0.25 s, none under
  `prefers-reduced-motion: reduce`) and leaves the page once faded.
- While the stream is shown, no note is made. While `vote-banner` is on the page,
  the newest note waits (it replaces any older waiting note) and shows once the
  banner has gone.
- A tap or click on a note opens the Salon on its Discussion tab (no scroll is
  added to spec 013's rules, Open question 12) and removes the note.
- `undo-message` (spec 018, `role="status"`, `t("undo.nothing")`, 3 seconds) has the
  note's look and place. It replaces any shown note, and shows also while the
  stream is shown and while the vote banner is on the page.

### Completion status and the recap button (specs 026, 028; `_design.md` section 9)

- `grid-status` keeps spec 026's attributes, texts and its two places, with "a low
  window" now meaning the sheet layout on a window at most 500 px high: there it
  sits in the clue bar's row, after `clue-bar-text`, in white 600 0.95rem/1.2, on
  one line. Everywhere else it sits under the clue bar, as wide as the bar: the
  end band of `_design.md` section 9 (padding 8 px 12 px, gap 10 px, 600
  0.95rem/1.2); solved: background `--nock-green-bg`, text `--nock-green` preceded by
  the ✓ pictogram; full but wrong: background `--nock-clue-bg`, navy text.
- `recap-open` (spec 028's text and behaviour) sits inside `grid-status` while the
  page is solved, after its text and pushed right: `nock-button
  nock-button-primary`, padding 7 px 12 px, 0.85rem, under the bar;
  `nock-button nock-button-secondary` with the same size in the clue bar's row.
  (Note from the lead, 2026-10-22: refined by spec 044, the design's keyboard:
  `grid-status` sits in the clue bar's row only while the in-app keyboard shows on
  a window at most 500 px high, which never happens on a solved page, so
  `recap-open` is always the primary button of the band; the secondary variant
  goes.)
- The in-app keyboard stays shown on a solved page in this step (spec 026 AC-5);
  step 5 hides it. (Note from the lead, 2026-10-22: refined by spec 044, the
  design's keyboard: the keyboard goes away once the grid is solved, in step 4.)

### Play area and fit (specs 006, 013)

- Sheet layout: `grid-area` takes the height between the top bar (and bands) and
  `clue-bar`; `grid-viewport` is `grid-area`'s box less 8 px on each side; the grid
  is centred in it. Under `grid-area`: `clue-bar`, `grid-status` when under the bar,
  `keyboard` on a touch screen.
- Column layout: the play area (left of the Salon) has a padding of 12 px.
  `grid-viewport` is as wide and as high as the grid's box at zoom 1, as large as
  the room left after `clue-bar`, `grid-status` and, on a touch screen, `keyboard`;
  the block of `grid-viewport`, `clue-bar` and `grid-status` is centred in the play
  area; `keyboard` (on a touch screen) spans the play area's full width at its
  bottom (margins −12 px, 10 px above it).
- Spec 006's zoom and pan, spec 025's `vote-banner` (over the top of
  `grid-viewport`) and spec 013 AC-6's guarantees apply to this play area.
- (Note from the lead, 2026-10-22: refined by spec 044, the design's keyboard: "on
  a touch screen" for `keyboard` in the first two items of this list reads "while the in-app
  keyboard shows"; hiding it gives its room to `grid-viewport`.)

### Layers (`_design.md` section 8)

Over the play area: `room-note` 6; `room-scrim` 7; popovers, the Salon sheet,
`vote-banner` and `clue-reaction` 8; `reaction-picker` 9; the dialogs in the top
layer (`showModal`). `vote-banner` is drawn above the Salon sheet and the scrim
where they overlap (spec 022 decision 16: the vote wins); `vote-yes` and `vote-no`
are never covered by anything of this spec.

### Removed

`room-toolbar`, `room-toolbar-more`, `host-panel`, `host-panel-more`, the compact
remove button (`host.remove_short`), the low layout of spec 014 (roster, feed and
host panel side by side), the roster and feed rows above the grid, spec 022's
`chat-moderation`, `mute-row` and `mute-name`, the feed's heading
(`feed.heading`), spec 027's `⏱` toggle in the toolbar, and the text of the
toolbar buttons that became icon buttons. The scrolling, fading and pointer-focus
rules that existed only for the toolbar and the host panel go with them (specs
014, 024, 035).

### `fr.json` keys

New:

| Key | Value |
| --- | --- |
| `topbar.aide` | `Aide` |
| `topbar.salon` | `Salon` |
| `topbar.menu` | `Menu` |
| `topbar.salon_unread` | `Salon, {count} messages non lus` |
| `topbar.salon_events` | `Salon, nouvelle activité` |
| `aide.empty` | `L'aide est désactivée dans ce salon.` |
| `authors.on` | `activé` |
| `authors.off` | `désactivé` |
| `others_tint.on` | `teintés` |
| `others_tint.off` | `sans teinte` |
| `access.on` | `activée` |
| `access.off` | `désactivée` |
| `menu.invite` | `Inviter` |
| `menu.invite_detail` | `lien` |
| `menu.back` | `Retour aux grilles` |
| `timer.hide` | `Masquer le chrono` |
| `salon.progress` | `{filled} / {total} mots` |
| `salon.players_tab` | `Joueurs ({count})` |
| `clue_bar.previous` | `Définition précédente` |
| `clue_bar.next` | `Définition suivante` |
| `reveal.letters_left` | `{count} restantes` |
| `reveal.letters_left_one` | `1 restante` |
| `reveal.words_left` | `{count} restants` |
| `reveal.words_left_one` | `1 restant` |
| `note.message` | `{name} : {text}` |
| `note.own_reaction` | `Vous avez réagi : {reaction}` |

Changed values:

| Key | Value | Was |
| --- | --- | --- |
| `check.letter` | `La lettre` | `Lettre` |
| `check.word` | `Le mot` | `Mot` |
| `check.grid` | `La grille` | `Grille` |
| `reveal.letter` | `La lettre` | `Lettre ({count})` |
| `reveal.word` | `Le mot` | `Mot ({count})` |
| `pencil.confirm` | `Confirmer la lettre au crayon` | `Confirmer` |
| `settings.heading` | `Réglages de l'hôte` | `Réglages` |

Removed, since nothing shows them any more: `check.letter_label`,
`check.word_label`, `check.grid_label`, `reveal.letter_label`,
`reveal.word_label`, `reveal.letter_none_label`, `reveal.word_none_label`,
`pencil.confirm_label`, `host.unlock`, `host.remove_short`, `feed.heading`,
`chat.toggle`, `chat.toggle_label_unread`, `chat.moderation_heading`,
`reaction.button`, `flag.button`, `timer.toggle`.

`note.message` and `note.own_reaction` are no bare placeholder and hold text
around their placeholders, so spec 035 AC-9's checker still flags `Loading…` and
`Check word`. `topbar.salon` is exactly `Salon`, which spec 035 AC-9 used as a
sample that its checker flags ("no template is exactly `Salon`"): that sample
becomes `Salle`, which no template is, and `Salon` becomes a sample that the
checker accepts (see "Refined specs").

### Refined specs

Each refined spec carries a dated note "(Note from the lead, 2026-10-22: refined by
spec 043, the design's room layout ...)". The test-writer updates the tests of the
criteria named here before the implementer runs. The column "WP" names the work
package that makes the change (see "Work packages").

| Spec | Criteria that change | What changes in their tests | WP |
| --- | --- | --- | --- |
| 011 | AC-1 (browser) | After a copy, `share-copied` shows `fr.json["room.share.copied"]`; `copy-link` keeps its text | 1 |
| 013 | AC-6 | The roster and feed rows are gone: the checks run with the Salon closed and open (as spec 043 AC-28); the feed-height check reads the stream list, whose height is the panel's | 1 |
| 014 | AC-1 (browser), AC-7, AC-8, AC-9, AC-10 | AC-1: Bob sees no `host-settings-open`; AC-7 to AC-10 are rewritten for the Joueurs rows and the host sheet (no fade, no compact button, no low layout) | 1 |
| 019 | AC-1 (window 296 by 640), AC-4 (row check), AC-5 | AC-1's FX-02 page at 20 to 21 px cells is 283 by 640; AC-4's in-row checks run in the touch context only (the desktop context at 568 by 320 and 740 by 360 is the column layout, where `grid-status` is under the bar); AC-5: `authors-switch` is in `room-menu` | 1 |
| 020 | AC-2 (mocked), AC-7 | AC-2: `confirm-pencil` is absent, not disabled, while the selected cell holds no pencil letter; AC-7: `pencil-toggle` in the top bar, `confirm-pencil` first in `aide-menu`, spec 043 AC-28's checks | 1 |
| 021 | AC-6, AC-10, AC-11 | AC-6: `flag-button` in `clue-bar` after `react-button`, no visible text; AC-10: the scan no longer meets `Je bloque`; AC-11: spec 043 AC-28's checks with `flag-button` in the clue bar | 1 |
| 022 | AC-1 (browser), AC-5, AC-6, AC-7 (browser), AC-15, AC-16, AC-17, AC-18 | AC-1: each page shows the Discussion tab; AC-5: `react-button` in `clue-bar`, no visible text, the picker over the grid; AC-6: the Salon closed at load (`nock.salon_closed` seeded at 1280 by 720), the `aria-label`s of `topbar.salon_unread`; AC-7: `mute-player` in the Joueurs rows; AC-15 rewritten; AC-16: `mute-player` in the Joueurs tab, one `Tab` from the last option reaches the Salon; AC-17: the banner over the Salon sheet; AC-18: the second run in the column layout only | 1 |
| 023 | AC-9 | The items are in `aide-menu`, with the new texts and no `aria-label`; the panel is labelled by its heading | 1 |
| 024 | AC-2 (browser), AC-3, AC-7, AC-8 | AC-2 and AC-3: the counts and « Plus de … » are the items' details, no `aria-label`; AC-7: `reveal-panel` in `aide-menu` after `check-panel`; AC-8 rewritten for the Aide menu | 1 |
| 025 | AC-4 | `aide-button` exists in place of `room-toolbar` | 1 |
| 026 | AC-10 | The in-row checks run in the touch context (sheet layout); in the desktop context at 568 by 320 and 740 by 360 `grid-status` is under the bar | 1 |
| 027 | AC-4, AC-8 | AC-4: hiding is the Menu's `timer-toggle` (no `aria-pressed`), showing is `timer-show`; AC-8 rewritten for the top bar | 1 |
| 028 | AC-7 | `recap-open` is inside `grid-status` | 1 |
| 033 | AC-9 | `account-open` is a `room-menu` item after `host-settings-open`, the layout checks are spec 043 AC-28's | 1 |
| 035 | AC-2 (ring contrast), AC-3, AC-9 (samples), AC-12 | AC-2: a ring's contrast is measured against the surface behind it (navy for the clue bar's white ring), the walk's stream list check shows the Discussion tab first; AC-3: after the grid come the clue bar's buttons (no sentinel needed, no Firefox skip), before it `menu-button`; AC-9: the flagged sample `Salon` becomes `Salle`, and `Salon` (`topbar.salon`) is accepted; AC-12: the stream list (named « Discussion ») is the one scrolling list; the roster list never scrolls on its own | 1 |
| 042 | AC-19 | The two switches are `room-menu` items (spec 043 AC-11) | 1 |

(Note from the lead, 2026-10-22: spec 044, the design's keyboard, refines this
spec's AC-27 and the rows of 020 (AC-7) and 026 (AC-10) above once more; its
"Refined specs" says how.)

(Note from the lead, 2026-10-22: refined by specs 045 and 046, the design's Auteurs
mode and entry pages; no criterion of this spec changes. While the room opens,
before the first snapshot, `room-topbar` already shows, `inert` and with no timer
(spec 046 AC-20), and `room-page` has `data-layout` from the opening on, so
"Document order" and "Which layout" read "once the page opens" where they say "once
the page has a snapshot" for these two. The « Auteurs » switch `authors-switch` is
remembered in `localStorage["nock.authors"]` (spec 045), in place of "off at each
load until step 5". `clue-bar-author` goes from the clue bar (spec 045).)

(Note from the lead, 2026-10-22: spec 047, the design's room overlays, refines this
spec's AC-26 (the vote's result is a note once the banner leaves at `vote_closed`)
and "3-second notes" (a `vote` line makes a note); the stream gains spec 047's
`vote` line, which has no pictogram and the muted colour, as the kinds this spec
lists without one. Its "Refined specs" says how.)

Spec 022 and spec 027 say that spec 035 AC-9's checker "must still flag `Loading…`,
`Salon` and `Check word`"; with this refinement the sample is `Salle`. Their notes
say so; no criterion of theirs changes for it.

Specs 007, 010, 012, 017, 018, 034 and 040 get a note and no criterion change: their
checks (the roster's items and nicknames, the band's text and visibility, the undo
button and message, the catch-up lines, `room-status`'s text) still hold. The
criteria of other specs whose tests click, type into or measure an element that is
now inside a popover, the Salon or a room sheet do not change; their tests open it
first ("Test harness").

### Test harness

- "Browser with mocked socket" as in spec 040, with FX-01 snapshots built from
  `grid_view(fx01_grid)` and `model_copy`, `seq` 5, `you` `p1` (`ANA`, colour 0,
  host) unless a criterion says otherwise; other players `p2` (`BOB`, colour 1),
  `p3` (`CY`, colour 2) and on to `p8` (colour 7) as a criterion gives them. FX-02
  snapshots from `tests/fixtures/fx02.json` (spec 006). "Browser with live server"
  as in spec 040.
- `H8`, the heavy setup: spec 013 AC-6's FX-01 snapshot with `you` host among 8
  players, then spec 013's 100 line events (`check_result` by `p2`, scope `grid`,
  empty lists, `seq` 6 to 105), (3, 1) tapped, help mode `free`, budget 5 letters
  and 1 word, and the timer at 36,000,000 ms running (`10:00:00`).
- Window sizes: the eight of spec 006 AC-5 and 1280 by 720. Desktop and touch
  contexts as spec 024's "Test harness" (touch: `has_touch=True`,
  `device_scale_factor=2`, `is_mobile=True` except under Firefox, and spec 009's
  `(pointer: coarse)` init script under Firefox and WebKit, so the in-app keyboard
  shows). Default: 1280 by 720, desktop context. `localStorage` starts empty except
  where a criterion seeds it with `context.add_init_script`.
- Helpers added to `tests/conftest.py` by the test-writer of this spec and used by
  the tests of every spec:
  - `open_aide(page)`, `open_menu(page)`: click the button when its popover is
    closed, then wait until it is open;
  - `show_tab(page, tab)`, `tab` `"discussion"` or `"players"`: click `chat-toggle`
    when the Salon is closed, then the tab when it is not selected, then wait until
    its panel shows;
  - `open_host_settings(page)`: `open_menu`, then a click on `host-settings-open`;
  - keyboard variants for keyboard-only tests: `tab_to` the button (spec 035), then
    `Enter`.
- Rule for the tests of every spec: a test that clicks, taps, types into or measures
  an element inside `aide-menu`, `room-menu`, the Salon or a room sheet first opens
  it with these helpers. A test that only reads attributes, texts or computed
  colours and fonts of such an element needs not: it is in the DOM while closed
  (with `hidden`). Where a criterion of another spec says "opens the chat panel with
  `chat-toggle`", the test calls `show_tab(page, "discussion")`; where it measures
  the feed list or the chat list, it measures the stream list once
  `show_tab(page, "discussion")` returned.
- Positions are bounding boxes; tolerances 1 px for a position, 0.5 px for a size,
  0.1 px for a font size or a line height, unless a criterion says otherwise.
  Colours as spec 041 (`parseColour` of `tests/colour_contrast.js`, exact channels
  for a token). Contrast by spec 035's formula. An SVG shape's colour is its computed
  `fill` or `stroke`. A pictogram is checked on the computed `content` of its
  element's `::before` or `::after`.
- "Covered" checks: `document.elementFromPoint` at a point returns the named element
  or one of its descendants.
- Fonts: spec 041's rule (wait for `document.fonts.ready` before reading a size or a
  position that depends on text).
- Engines: Chromium and WebKit locally, Firefox too in CI. The clipboard check of
  AC-21 is Chromium only, as spec 011's; no other check is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new) (browser with mocked socket) The layout follows the window's shape, size and pointer. On a FX-01 snapshot, `room-page` has `data-layout="column"` at 1920 by 1080, 1280 by 720, 1024 by 768, 900 by 600, 740 by 360 and 568 by 320, and `data-layout="sheet"` at 899 by 600, 800 by 800, 768 by 1024, 360 by 740 and 320 by 568, in the desktop context; in the touch context it has `"column"` at 1024 by 768 and `"sheet"` at 740 by 360 and 568 by 320. In the desktop context, after `page.set_viewport_size` from 1280 by 720 to 360 by 740 it reads `"sheet"` within 300 ms, and `"column"` again within 300 ms of the way back; an open `room-menu` is closed after each change.
- **AC-2** (new) (browser with mocked socket) The phone top bar has the timer and five buttons, icons over labels. At 360 by 740: `room-topbar` is a `HEADER` with the box left 0, top 0, width 360, height 54, computed `background-color` rgb(255, 255, 255) and a `1px` `solid` rgb(221, 226, 234) bottom border; it holds no `topbar-brand` that shows; its children that show are, in document order, `timer`, `undo-button`, `aide-button`, `chat-toggle`, `pencil-toggle`, `menu-button`. Each of the five buttons is a `BUTTON` with `type="button"`, 56 px wide (0.5 px) and 53 px high (1 px), with a transparent background, and holds one `svg` with `aria-hidden="true"`, 22 by 22 px, `stroke-width` 1.8, whose shapes are those of `ICONS` for `undo`, `aide`, `salon`, `crayon` and `menu`, above its label (the icon's bottom at or above the label's top), the label's text `fr.json["room.undo"]`, `["topbar.aide"]`, `["topbar.salon"]`, `["pencil.toggle"]`, `["topbar.menu"]`, computed `font-size` 10.88 px, `font-weight` 500 and `color` rgb(27, 47, 85). `timer` has `font-size` 18.4 px, `font-weight` 600, `color` rgb(27, 47, 85) and `font-variant-numeric` `tabular-nums`, its left edge 10 px or more from the window's left edge (1 px), and `menu-button`'s right edge is 4 px from the window's right edge (1 px). The same holds, with the window's width in place of 360, at 740 by 360 and at 568 by 320 in the desktop context, where `room-page` has `data-layout="column"`. (Note from the lead, 2026-10-22: added; the phone top bar is also the column layout's on a window at most 500 px high.)
- **AC-3** (new) (browser with mocked socket) The computer top bar has the brand, the timer and five buttons, icons beside labels. At 1280 by 720: `room-topbar` is 56 px high and 1280 px wide; `topbar-brand` is its first child that shows, 16 px from its left edge (1 px), holding an `svg` with `viewBox="0 0 10 14"`, 12 by 18 px, whose one `polygon` has `points` `0,0 10,0 10,14 5,10 0,14` and computed `fill` rgb(27, 47, 85), then the text `fr.json["app.title"]` in `font-weight` 700, `font-size` 20.8 px, navy. Then, left to right: `timer` (its right edge at least 10 px left of `undo-button`'s left edge), `undo-button`, `pencil-toggle`, `aide-button`, `chat-toggle`, `menu-button`, each 38 px high (0.5 px), radius `6px`, padding left and right `12px`, 6 px from the next (1 px), its 20 by 20 px icon left of its label (the icon's right at or left of the label's left, their vertical centres within 1 px), the label in 14.72 px, weight 500, navy; `menu-button`'s right edge is 16 px from the window's right edge (1 px). `aide-button` holds `aide-caret`, `aria-hidden="true"`, with no text node and a `::after` or `::before` whose computed `content` is `"▾"`. At 740 by 360 and 568 by 320 in the desktop context (column layout), no `topbar-brand` shows and `room-topbar` is 54 px high: the computer top bar is used only on a window more than 500 px high. (Note from the lead, 2026-10-22: added, with the phone top bar of a low column-layout window.)
- **AC-4** (new) (browser with mocked socket) The top bar never overflows, and the room's heading and status are read but not seen. At 320 by 568 with the timer at 36,000,000 ms running, and at 283 by 640 with a snapshot whose `timer_elapsed_ms` is 0: each top-bar button lies inside `room-topbar`'s box, is at least 40 px wide, and its label shows its whole text on one line (`scrollWidth <= clientWidth + 1`, one `getClientRects()` line); `timer` is on one line and does not overlap `undo-button`; `document.documentElement.scrollWidth <= window.innerWidth`. The same checks hold at 568 by 320 and 740 by 360 with the timer at 36,000,000 ms running, in the desktop context and in the touch context with `nock.keyboard_hidden` seeded `"true"` (spec 044; both the column layout with the phone top bar). (Note from the lead, 2026-10-22: added, so that the low column-layout windows are checked.) At 1280 by 720 and 360 by 740 with `data-status="joined"`: the room's `h1` and `room-status` have the class `visually-hidden`, a box at most 1 by 1 px, and the texts `Salon ABC123` (from `fr.json["room.heading"]`) and `fr.json["room.status.joined"]`.
- **AC-5** (new) (browser with mocked socket) The top-bar buttons show their state, and « Salon » shows unread messages and new activity. At 360 by 740: `aide-button`, `chat-toggle` and `menu-button` have `aria-expanded="false"` and `aria-controls` `aide-menu`, `salon`, `room-menu`; after a click on each in turn, the clicked one has `aria-expanded="true"` and a computed `background-color` rgb(230, 237, 249), and the others `aria-expanded="false"`; `pencil-toggle` after a click has `aria-pressed="true"` and rgb(230, 237, 249). With the Salon closed, after `chat_message` seq 6 and 7 from `p2`: `chat-unread` is inside `chat-toggle`, has the classes of `nock-badge` (computed background rgb(180, 35, 24), colour rgb(255, 255, 255)), the text `2`, its top 5 px below and its right 8 px left of `chat-toggle`'s (1 px), and `chat-toggle` has the `aria-label` `Salon, 2 messages non lus`; no `salon-dot` shows. On a new page, after a `check_result` seq 6 by `p2` (scope `grid`, empty lists) with the Salon closed: `salon-dot` shows, an 8 by 8 px box with `border-radius` `50%` and `background-color` rgb(180, 35, 24), its top 8 px below and its right 15 px left of `chat-toggle`'s; `chat-toggle`'s `aria-label` is `fr.json["topbar.salon_events"]`; a `chat_message` seq 7 from `p2` then hides it (the badge shows); `show_tab(page, "discussion")` removes both, and `chat-toggle` has no `aria-label`. A `check_result` by `p1` (`you`) with the Salon closed makes no `salon-dot`. At 1280 by 720 with `nock.salon_closed` seeded `"true"`, the badge's top is 2 px below and its left 24 px right of `chat-toggle`'s, and `salon-dot` (after a check by `p2`) has the same top and left.
- **AC-6** (new; refines spec 027 AC-4 and AC-8) (browser with mocked socket) The timer sits in the top bar, the Menu hides it and « Chrono » shows it again. With a snapshot of 65,000 ms running at 360 by 740: `timer` reads `1:05` or later, has `role="timer"`, is no `BUTTON` and no Tab stop. After `open_menu` and a click on `timer-toggle` (text `fr.json["timer.hide"]`, no `aria-pressed` attribute): `room-menu` is closed, the focus is on `menu-button`, no `timer` is on the page, `timer-show` holds the `chrono` icon and the label `fr.json["timer.label"]`, has the `aria-label` `fr.json["timer.toggle_label"]` and the box of a top-bar button at the timer's place (left of `undo-button`), `localStorage["nock.timer_hidden"]` is `"true"`, no frame was sent within 300 ms (pings not counted), and `timer-toggle` reads `fr.json["timer.toggle_label"]`. After a reload, `timer-show` shows. A click on it shows `timer` again, removes the key, and `timer-toggle` reads `fr.json["timer.hide"]`. At 1280 by 720 the same holds with `timer-show` between `topbar-brand` and `undo-button`.
- **AC-7** (new) (browser with mocked socket) The connection band sits under the top bar and pushes the grid down; a final status shows in a band. At 360 by 740 and 1280 by 720, joined on a FX-01 snapshot, the test notes the top of `grid-area`; when the mock closes the socket with code 1011: `connection-banner` shows within 5,000 ms, its top is the top bar's bottom (1 px), it is as wide as the window, with computed `background-color` rgb(238, 242, 248), a `1px` `solid` rgb(221, 226, 234) bottom border and padding `8px 12px`; its first child `connection-dot` is 8 by 8 px with `background-color` rgb(180, 35, 24), `aria-hidden="true"`, its top 5 px below the band's content top (1 px); its text is `fr.json["room.banner.offline"]` in `font-size` 13.6 px, weight 500, colour rgb(20, 24, 31); the top of `grid-area` is the band's bottom, below the noted top; `room-status` has the class `visually-hidden`. When the mock answers the next join with a snapshot, the band is gone and `grid-area`'s top is back at the noted top (1 px). In a second run, the mock sends `error` `removed` then closes: `room-page` has `data-status="removed"`, `room-status` has no class `visually-hidden`, shows `fr.json["room.status.removed"]` under the top bar with the band's background and border, and holds no `connection-dot`.
- **AC-8** (new; refines spec 020's and spec 023's controls) (browser with mocked socket) The Aide menu holds the pencil confirm, Vérifier and Révéler, in the design's order. On a FX-01 snapshot (help mode `free`, `reveal_budget` 5 letters and 1 word) where (1, 0) holds a pencil `T` by `p2`, at 1280 by 720: with nothing selected, after `open_aide`, `aide-menu` has `role="group"` and the `aria-label` `fr.json["topbar.aide"]`, holds no `confirm-pencil`, and holds in document order `check-heading` (`fr.json["check.label"]`), `check-letter`, `check-word`, `check-grid` (texts `fr.json["check.letter"]`, `["check.word"]`, `["check.grid"]`, no `aria-label`), a `nock-menu-separator`, `reveal-heading` (`fr.json["reveal.label"]`), `reveal-letter` and `reveal-word` (texts starting with `fr.json["reveal.letter"]` and `["reveal.word"]`, no `aria-label`); `check-panel` and `reveal-panel` are `role="group"` with `aria-labelledby` the `id` of their heading; `reveal-letter-detail` reads `5 restantes` and `reveal-word-detail` `1 restant` (built from `fr.json`). After a tap on (1, 0) and `open_aide`, the first child of `aide-menu` is `confirm-pencil` (text `fr.json["pencil.confirm"]`, computed `font-weight` 600, a detail whose pictogram `content` is `"✎"`), followed by a `nock-menu-separator`. After a `reveal_result` (seq 6, scope letter) whose budget is 1 letter and 1 word, `reveal-letter-detail` reads `fr.json["reveal.letters_left_one"]`; after one with 0 letters and 0 words, the two details read `fr.json["reveal.letter_none"]` and `fr.json["reveal.word_none"]`, both items are disabled, and their text and detail have the colour rgb(94, 101, 115), a contrast of at least 4.5:1 against the menu's white. With help mode `none` (a `settings_changed` seq 7), with (2, 1) selected (empty), `aide-menu` holds no `check-panel`, no `reveal-panel` and one `aide-empty` reading `fr.json["aide.empty"]`.
- **AC-9** (new; refines spec 023 AC-9, spec 024 AC-7 and spec 020 AC-2) (browser with mocked socket) An Aide item sends its message, closes the menu and gives the focus back. On the snapshot of AC-8 at 1280 by 720, after tapping (2, 2) twice (`down`, word `0,2,0`): `open_aide` then a click on `check-word` sends one frame that parses to `Check(target=WordTarget(row=0, column=2, clue_index=0))`, `aide-menu` is closed and the focus is on `aide-button`; the same for `check-letter` (`CellTarget(row=2, column=2)`), `check-grid` (`GridTarget()`), `reveal-letter` (`Reveal(target=CellTarget(row=2, column=2))`) and `reveal-word` (`Reveal(target=WordTarget(row=0, column=2, clue_index=0))`), the selection staying (2, 2) `down`. After a tap on (1, 0), `open_aide` and a click on `confirm-pencil` send `ConfirmPencil(row=1, column=0, base_seq=5)`, close the menu, and leave the selection on (1, 0). A click on a disabled item (`check-letter` with nothing selected, on a fresh page) sends nothing within 300 ms (pings not counted) and leaves the menu open.
- **AC-10** (new) (browser with mocked socket; browser with mocked socket and routes) The Menu holds the design's items, in order, with the host's and the account's only when they apply. On a FX-01 snapshot at 360 by 740, after `open_menu`: `room-menu` has `role="group"` and the `aria-label` `fr.json["topbar.menu"]`, and holds in document order `authors-switch`, `others-tint-switch`, `access-switch`, `invite-open`, `host-settings-open`, a `nock-menu-separator`, `timer-toggle`, `back-to-grids`, with the labels of the "Menu" table; `back-to-grids` is an `A` whose `href` is `/`; each detail has `aria-hidden="true"` and the switches' details read `fr.json["authors.off"]`, `fr.json["others_tint.on"]` and `fr.json["access.off"]`; `invite-open`'s detail reads `fr.json["menu.invite_detail"]`. Its box's top is 58 px from the window's top and its right edge 6 px from the window's right edge (1 px), its width at least 220 px, background rgb(255, 255, 255), radius `8px`. With `you` not host (`p2` host in the snapshot), there is no `host-settings-open`. With accounts on (mocked `GET /api/account`, spec 033), `account-open` comes right after `host-settings-open` with the label `fr.json["account.open"]`, and right after `invite-open` when `you` is not host. At 1280 by 720, `room-menu`'s top is 4 px below the top bar's bottom and its right edge is `menu-button`'s right edge (1 px).
- **AC-11** (new; refines spec 042 AC-19) (browser with mocked socket) The Menu's switches flip in place; Inviter, Réglages and Compte open what they name. On a FX-01 snapshot with `p2` (colour 1) and `p3` (colour 2) selecting (2, 2), at 360 by 740, after `open_menu`: a click on `access-switch` gives it `aria-pressed="true"`, its detail `fr.json["access.on"]`, `localStorage["nock.accessibility"]` `"true"`, the cursors `data-shape="icon"` (spec 042 AC-11), and `room-menu` stays open with the focus on `access-switch`; the same for `others-tint-switch` (`aria-pressed="false"`, detail `fr.json["others_tint.off"]`) and `authors-switch` (`aria-pressed="true"`, `fr.json["authors.on"]`). Keyboard only: `tab_to` `menu-button`, `Enter` opens it with the focus on `authors-switch`, `Tab` reaches each switch, `Enter` flips it, and each has spec 035 AC-2's outline. A click on `invite-open` closes `room-menu`, opens the Salon with `salon-tab-players` selected and puts the focus on `copy-link`. A click on `host-settings-open` closes `room-menu` and opens `host-settings` (its `open` attribute set); `Escape` closes it and the focus is on `menu-button`. With accounts on, `account-open` opens `account-dialog` the same way.
- **AC-12** (new) (browser with mocked socket) Popovers open and close the same way and never stack. At 360 by 740 and at 1280 by 720, for each of `aide-button` and `menu-button`: a click opens its popover and puts the focus on its first enabled item; `Escape` closes it and puts the focus on the button; a second click on the button closes it. At 1280 by 720, a `page.mouse.click` on the grid's cell (2, 2) while `room-menu` is open closes it and selects (2, 2). At 360 by 740: while `aide-menu` is open, `room-scrim` shows with its top 54 px from the window's top, its bottom on the window's bottom, full width, computed `background-color` with channels 20, 24, 31 and alpha 0.35, and `z-index` 7; a `page.mouse.click` at (20, 400) on it (left of the menu, which starts at `aide-button`'s left edge) closes `aide-menu`, removes the scrim, sends no frame and selects no cell; opening `room-menu` while `aide-menu` is open closes `aide-menu`; opening the Salon closes `room-menu`; with `reaction-picker` open (after a tap on the clue cell (0, 3) and a click on `react-button`), opening the Salon closes the picker. At 1280 by 720 the Salon column stays open while `aide-menu`, `room-menu` or `reaction-picker` opens, no `room-scrim` shows, and opening `room-menu` closes `aide-menu`. A closed `aide-menu` has the `hidden` attribute and still holds `check-grid`.
- **AC-13** (new) (browser with mocked socket) The Salon is a column on a wide window, open by default and remembered closed. At 1280 by 720 with empty `localStorage`: `salon` is an `ASIDE` with the `aria-label` `fr.json["topbar.salon"]`, open, 340 px wide, its right edge on the window's right edge, its top on the top bar's bottom and its bottom on the window's bottom (1 px), background rgb(255, 255, 255) and a `1px` `solid` rgb(221, 226, 234) left border; `chat-toggle` has `aria-expanded="true"` and no element of the Salon has the focus at load. The test notes the cell side `s` of (1, 1). A click on `chat-toggle` gives `salon` the `hidden` attribute and `localStorage["nock.salon_closed"]` the value `"true"`, and `s` grows; after a reload the Salon is closed; a click opens it again, removes the key, moves the focus to `chat-input`, and `s` is the noted value (1 px). With the Salon open, `Escape` in `chat-input` puts the focus on `chat-toggle` and leaves the Salon open.
- **AC-14** (new) (browser with mocked socket) The Salon is a bottom sheet on a phone and moves nothing. At 360 by 740 with `nock.salon_closed` seeded `"true"` (it has no effect in this layout) the Salon is closed at load. The test notes the boxes of `grid-viewport` and `clue-bar`. A click on `chat-toggle` opens `salon`: its bottom on the window's bottom, its width 360, its height 0.62 × 740 (1 px), its computed `border-top-left-radius` and `border-top-right-radius` `14px`, its `box-shadow` with offsets 0 and −10 px, blur 30 px, spread −12 px and colour 20, 24, 31 at alpha 0.45, `z-index` 8; `salon-handle` is 40 by 4 px, `aria-hidden="true"`, `border-radius` `2px`, `background-color` rgb(197, 204, 216), horizontally centred, 8 px below the sheet's top; the focus is on `chat-input`; `grid-viewport` and `clue-bar` keep the noted boxes. `Escape` closes it and puts the focus on `chat-toggle`.
- **AC-15** (new) (browser with mocked socket) The Salon shows the progress and two tabs. On a FX-01 snapshot where TAMIS and VIDE are full (5 + 4 cells, (1, 0) to (1, 4) and (2, 1) to (2, 4)) and every other letter cell is empty, with 3 players, at 1280 by 720: `salon-progress-text` reads `2 / 8 mots` (built from `fr.json["salon.progress"]`), in `font-size` 13.6 px, weight 600, colour rgb(27, 47, 85), `font-variant-numeric` `tabular-nums`; `salon-progress-bar` is 6 px high, with `border-radius` `3px`, a background rgb(230, 237, 249) and a navy fill whose width is 2/8 of the bar's (1 px); after the player taps (3, 1) and types `A`, `M`, `E`, `N` (AMEN, with no answer from the mock), it reads `3 / 8 mots` once (3, 4) shows `N` (pending edits count). `salon-tabs` has `role="tablist"` and holds `salon-tab-discussion` (text `fr.json["chat.heading"]`) and `salon-tab-players` (text `Joueurs (3)`, built from `fr.json["salon.players_tab"]`), each `role="tab"`, of equal widths (1 px); the first has `aria-selected="true"`, `tabindex="0"`, colour rgb(27, 47, 85) and a `2px` `solid` rgb(27, 47, 85) bottom border, the second `aria-selected="false"`, `tabindex="-1"`, colour rgb(94, 101, 115) and a bottom border colour with alpha 0. `chat-panel` and `roster` have `role="tabpanel"`, `aria-labelledby` the `id` of their tab, and `roster` has the `hidden` attribute. With the focus on `salon-tab-discussion`, `ArrowRight` selects `salon-tab-players`, gives it the focus, shows `roster` and hides `chat-panel`; `ArrowLeft` goes back. A `player_joined` (seq 6) makes the tab read `Joueurs (4)`.
- **AC-16** (new; refines spec 013's feed and spec 022's chat list) (browser with mocked socket) Messages and events share one stream, in seq order, each with its look. On a FX-01 snapshot (`seq` 5, players `p1` to `p3`) whose `chat` holds `Salut` (seq 3, `p2`), at 1280 by 720, the mock sends `player_joined` seq 6 (`p4`, `DEE`), `check_result` seq 7 (`p2`, scope grid, empty lists), `check_result` seq 8 (`p3`, scope word, `wrong` holding (1, 1)), `chat_message` seq 9 (`p3`, `Bien vu`), `reveal_result` seq 10 (`p2`, scope letter), `flag_changed` seq 11 (`p2`, IDES), `player_left` seq 12 (`p4`, reason `left`). Then `activity-feed` holds one `ul`, `chat-list`, with `role="list"` and `aria-labelledby="chat-heading"`, whose `li` children are, in order, `chat-message` seq 3, `feed-item` seq 6, 7, 8, `chat-message` seq 9, `feed-item` seq 10, 11, 12; each `feed-item` has spec 013's text as its whole text content. The `feed-picto` of the items of seq 6 and 12 have the computed `content` `"→"` and `"←"`, of seq 7 and 8 `"✓"`, of seq 10 `"▲"`; the item of seq 11 holds an `svg` with `aria-hidden="true"` whose two `path` elements have the `d` of `ICONS.flag`. Each `feed-item` has `font-size` 13.12 px and `padding-left` `16px`; the colours are rgb(94, 101, 115) for seq 6, 8, 11 and 12, rgb(30, 123, 69) for seq 7 (`data-ok="true"`), rgb(194, 65, 12) for seq 10. Each `chat-message` holds `chat-dot` (10 by 10 px, `border-radius` `50%`, the `background-color` of its player's `roster-colour`, a `box-shadow` of spread 1 px and colour 20, 24, 31 at alpha 0.55), then `chat-author` (weight 700, colour rgb(20, 24, 31), its left edge 6 px right of the dot's right edge, 1 px), then `chat-text`; `chat-text` has `font-size` 14.72 px. A `chat_message` of `p9` (not a player) has no `chat-dot`. After 100 more line events and 200 more messages, the list holds exactly 100 `feed-item` and 200 `chat-message` items, the newest of each kind.
- **AC-17** (new; refines spec 022's "Unread lines") (browser with mocked socket) Lines are read while the stream shows, and only then. At 1280 by 720 (Salon open on Discussion at load), `chat_message` seq 6 and 7 from `p2` make no `chat-unread` and no `salon-dot`. A click on `salon-tab-players`, then `chat_message` seq 8 from `p2`: `chat-unread` reads `1`; a click on `salon-tab-discussion` removes it. A click on `salon-tab-players`, then a `check_result` seq 9 by `p2`: `salon-dot` shows; a click on `salon-tab-discussion` removes it. A click on `chat-toggle` (Salon closed), then `chat_message` seq 10 from `p1` (`you`): no `chat-unread`.
- **AC-18** (new) (browser with mocked socket) The message box has the design's look. With `show_tab(page, "discussion")` at 360 by 740 and at 1280 by 720: the chat form has a `1px` `solid` rgb(221, 226, 234) top border and padding `8px 12px 12px`; `chat-input` has a `1px` `solid` rgb(154, 163, 178) border, `border-radius` `18px`, padding `7px 12px`, `font-size` 14.4 px and its placeholder `fr.json["chat.placeholder"]`; `chat-send` has the text `fr.json["chat.send"]`, `background-color` rgb(230, 237, 249), colour rgb(27, 47, 85), weight 600, `font-size` 13.6 px, `border-radius` `14px`, padding `6px 12px` and border width `0px`, and lies right of `chat-input` with their vertical centres within 1 px; the chat notes' slot is below the form, inside the Salon.
- **AC-19** (new; refines spec 012's and spec 014's roster rows) (browser with mocked socket) Each Joueurs row names the player, the host and where the player is. On a FX-01 snapshot with `p1` (`you`, host), `p2` (`JEAN-LUC`, idle, selecting (1, 0) `across`), `p3` (`CY`, disconnected, no selection) and `p4` (`DEE`, no selection), at 360 by 740 and at 1280 by 720, after the player taps (2, 2) twice (`down`, MIME) and `show_tab(page, "players")`: the four `roster-player` rows come in snapshot order, each with line 1 (`roster-colour`, `roster-nickname`, then `roster-you` on `p1`'s row and `roster-host` on the host's row) above line 2 (`roster-state`, then `roster-sep` and `roster-clue` when the player has a selection), line 2's left edge on `roster-nickname`'s left edge (1 px). `p1`'s row: `roster-nickname` weight 700, `roster-you` reads `fr.json["roster.you"]`, `roster-host` reads `fr.json["roster.host"]` with `background-color` rgb(238, 242, 248), colour rgb(27, 47, 85), weight 600, `font-size` 11.52 px, `border-radius` `10px`, and `roster-clue` reads `Artiste muet`; `p2`'s row: weight 400, `roster-state` `fr.json["presence.idle"]`, `roster-clue` `Passoire fine`, both 13.6 px in rgb(94, 101, 115), `roster-sep` with the pictogram `content` `"·"`; `p3` and `p4` have no `roster-clue` and no `roster-sep`. `roster-colour` is 10 by 10 px with the ring of AC-16's `chat-dot`. Each other player's row holds `mute-player` then `remove-player`, `nock-button` small secondaries (background rgb(255, 255, 255), colour and border rgb(27, 47, 85), `font-size` 12.8 px, padding `6px 10px`), each at least 24 by 24 px, `remove-player` reading `fr.json["host.remove"]` with spec 014's `aria-label`, `mute-player` with spec 022's text and `aria-label`; both lie inside the row and the Salon (1 px), right of `roster-host` and `roster-nickname`. When the mock sends `selection_moved` of `p2` to (2, 1) `across`, `p2`'s `roster-clue` reads `Sans contenu` within 300 ms; after `selection_moved` of `p2` to `null`, it has none. With `you` not host, no row holds `mute-player` or `remove-player`.
- **AC-20** (new; refines spec 011's share panel) (browser with mocked socket; browser with live server, clipboard in Chromium only) The invitation link sits under the players. After `show_tab(page, "players")` at 360 by 740 and 1280 by 720: `share-panel` comes after the players' `ul` inside `roster`; `share-label` reads `fr.json["room.share.label"]` with `text-transform` `uppercase`, weight 600, `font-size` 12.48 px, colour rgb(94, 101, 115); `share-link` is an `A` whose `href` and text are `<origin>/r/ABC123`, as wide as `share-panel`'s content (1 px), with a `1px` `solid` rgb(154, 163, 178) border, `border-radius` `6px`, padding `8px 10px`, `font-size` 13.6 px, `white-space` `nowrap`, `overflow` `hidden` and `text-overflow` `ellipsis`; `copy-link` reads `fr.json["room.share.copy"]` with the primary button's colours (spec 041 AC-10). Live, in Chromium with the clipboard permissions of spec 011: a click on `copy-link` puts the link in the clipboard and shows `share-copied` (`role="status"`, `fr.json["room.share.copied"]`, colour rgb(30, 123, 69), weight 500, `font-size` 13.6 px) while `copy-link` still reads `fr.json["room.share.copy"]`; `share-copied` is gone 2,500 ms later.
- **AC-21** (new; refines spec 014's host panel) (browser with mocked socket) The host's settings are a room sheet with a switch, a segmented control and two number fields. On a FX-01 snapshot (help mode `free`, allowance 5 letters and 1 word, unlocked), at 1280 by 720, after `open_host_settings`: `host-settings` is a `DIALOG` with the `open` attribute, `aria-labelledby` its title, which reads `fr.json["settings.heading"]` in weight 700, `font-size` 19.2 px, navy; it is 440 px wide (1 px), centred in the window, with `border-radius` `12px` and padding `20px 22px`; it holds in order the switch row, `settings-form` with `help-mode-select` (a `FIELDSET` whose `LEGEND` reads `fr.json["settings.help_mode_label"]`, holding three `help-mode-option` radios with the values `free`, `vote`, `none`, labelled `fr.json["settings.help_mode.free"]`, `["…vote"]`, `["…none"]`, `free` checked, its label with background rgb(27, 47, 85) and colour rgb(255, 255, 255), the others with a background alpha 0 and colour rgb(27, 47, 85)), `reveal-letters-input` and `reveal-words-input` (each 64 px wide, `text-align` `center`, values 5 and 1; each input's label, its `labels[0]`, reads `fr.json["settings.reveal_letters_label"]` or `fr.json["settings.reveal_words_label"]` in weight 600, `font-size` 13.6 px, colour rgb(20, 24, 31), on one line (one `getClientRects()` line), its bottom 6 px above its input's top and its left edge on its input's left edge (1 px); the left edge of `reveal-words-input`'s label is 16 px right of the larger of the right edges of `reveal-letters-input` and its label (1 px)) (Note from the lead, 2026-10-22: this read "(each 64 px wide, `text-align` `center`, values 5 and 1, 16 px apart, 1 px)": the 16 px are between the two field groups, label and input, as `_design.md` section 8 and the screens sheet draw them, not between the 64 px inputs, which would make the labels wrap), and `settings-save` (primary, its right edge on the form's right edge, 1 px). `lock-room` has `aria-pressed="false"`, the `aria-label` `fr.json["host.lock"]`, a track 42 by 24 px with `background-color` rgb(154, 163, 178) and an 18 px white knob 3 px from the track's left; a click sends `LockRoom(locked=True)` at once; after the mock's `settings_changed` with `locked` true, `aria-pressed="true"`, the track rgb(27, 47, 85) and the knob 21 px from the track's left. A click on the `vote` option, `3` in `reveal-letters-input` and a click on `settings-save` send `ChangeSettings(help_mode="vote", reveal_budget=RevealBudget(letters=3, words=1))`, close the dialog and put the focus on `menu-button`. At 360 by 740, `host-settings` is a bottom sheet: full width, its bottom on the window's bottom, `border-top-left-radius` `16px`, padding `14px 18px 18px`, its top at least 54 px below the window's top; a click on the backdrop above it (at (180, 100)) closes it. With `you` not host there is no `host-settings`.
- **AC-22** (new; refines spec 033's account dialog look) (browser with mocked socket and routes) The account dialog is a room sheet too. With accounts on and signed out, after `open_menu` and a click on `account-open`: at 1280 by 720, `account-dialog` is 440 px wide, centred, `border-radius` `12px`, its heading `fr.json["account.dialog_heading"]` in weight 700, `font-size` 19.2 px, navy, its submit button primary and `account-close` secondary with its right edge on the dialog's content right edge (1 px); at 360 by 740 it is a bottom sheet as `host-settings` of AC-21. `Escape` closes it and the focus is on `menu-button`.
- **AC-23** (new; refines spec 007's clue bar, spec 021's and spec 022's buttons) (browser with mocked socket) The clue bar is navy, one line, with its four buttons. On a FX-01 snapshot at 360 by 740 and at 1280 by 720, after a tap on (2, 2) twice (`down`, MIME): `clue-bar` has the class `nock-on-navy`, `background-color` rgb(27, 47, 85), height 34 px, and holds in document order `clue-prev`, `clue-bar-text`, `react-button`, `flag-button`, `clue-next`, left to right, their vertical centres within 1 px of the bar's; `clue-prev` and `clue-next` are 36 px wide, `react-button` and `flag-button` 40 px wide with `border-radius` `6px`, each a `BUTTON` with no text and an `aria-label`: `fr.json["clue_bar.previous"]`, `fr.json["reaction.button_label"]`, `fr.json["flag.button_label"]`, `fr.json["clue_bar.next"]`, each holding a 20 by 20 px `svg` with `aria-hidden="true"`, `stroke-width` 2 and the shapes of `chevron-left`, `smile`, `flag`, `chevron-right`. `clue-bar-text` has the text content `Artiste muet`, colour rgb(255, 255, 255), `font-size` 15.2 px, weight 500, `white-space` `nowrap`, `overflow` `hidden`, `text-overflow` `ellipsis`, and holds `clue-bar-direction` (`aria-hidden="true"`, no text node, pictogram `content` `"↓"`, `opacity` 0.8, `margin-left` `6px`); after a tap on (2, 2) it is `"→"` (VIDE). `flag-button` not pressed: its flag's `stroke` rgb(255, 255, 255), `fill` none or alpha 0, the button's background alpha 0; after the mock's `flag_changed` for `p1` on MIME: `aria-pressed="true"`, background rgb(255, 255, 255), the flag shape's `fill` rgb(27, 47, 85). With nothing selected (a fresh page), `react-button` and `flag-button` are disabled, their icons' `stroke` rgb(154, 163, 178), with a contrast of at least 4.5:1 against the bar. Keyboard: `tab_to` `flag-button` gives it a `2px` `solid` rgb(255, 255, 255) outline with `outline-offset` `-4px`. Width: at 360 by 740 the bar is 360 px wide; at 1280 by 720 it is as wide as the `grid`'s box (1 px) and its left edge is the grid's left edge (1 px); on a FX-02 snapshot at 568 by 320 (desktop, column layout), it is as wide as the play area's content box (1 px), which is narrower than 320 px.
- **AC-24** (new) (browser with mocked socket) ‹ and › move to the previous and the next unfinished word, and a pointer press keeps the focus on the grid. On a FX-01 snapshot where TAMIS is full and every other cell empty, at 1280 by 720: with nothing selected, a click on `clue-next` selects `0,0,1` (NAVAL, TAMIS being finished) on its first unfilled cell (spec 009's `Tab`), sends `select_cell`, and `clue-bar` has `data-word="0,0,1"`; a second click selects `0,2,0`; a click on `clue-prev` selects `0,0,1` again. After a tap on the clue cell (2, 0) (VIDE; the grid has the focus), a `page.mouse.click` on `clue-next` selects AMEN on (3, 1) and leaves `document.activeElement` on the `grid`, and the key `I` then shows `I` in (3, 1). Keyboard only: `tab_to` `clue-next` and `Enter` move the selection and leave the focus on `clue-next`.
- **AC-25** (new; refines spec 022 AC-5's picker place and AC-4's look) (browser with mocked socket) The picker floats over the bottom of the grid, and a shown reaction is a pill over its clue. At 360 by 740 and 1280 by 720, after a tap on the clue cell (0, 3) and a click on `react-button`: `reaction-picker` is centred on `grid-viewport` (its centre x within 1 px of the viewport's), its bottom 8 px above the viewport's bottom (1 px), `z-index` 9, background rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `24px`, padding `5px`; each `reaction-option` is 40 by 40 px with `border-radius` `20px`, a background alpha 0 and `font-size` 22 px, and after `page.hover` on the first, its background is rgb(230, 237, 249); `react-button` has `aria-expanded="true"` and a background rgb(255, 255, 255); a second click closes the picker. When the mock sends a `reaction` of `p2` with `clap` on IDES (0, 3, 0), the `clue-reaction` has `background-color` rgb(255, 255, 255), a `1px` `solid` rgb(221, 226, 234) border, `border-radius` `12px`, padding `2px 6px`, `font-size` 16 px, `line-height` 19.2 px, `z-index` 8, its centre within 1 px of the centre of the `clue` element of IDES, and `elementFromPoint` at its centre returns it; a `reaction` on NAVAL (0, 0, 1) shows its pill centred on the lower `clue` element of (0, 0).
- **AC-26** (new) (browser with mocked socket) Others' actions show as a 3-second note while the stream is not shown. At 360 by 740 (Salon closed) on a FX-01 snapshot: `chat_message` seq 6 from `p2` with `IDES ?` shows within 300 ms one `room-note` reading `Bob : IDES ?` (built from `fr.json["note.message"]`), with spec 041's `nock-note` look, `aria-hidden="true"`, `tabindex="-1"`, its centre x within 1 px of `grid-viewport`'s, its top 8 px below the viewport's top (1 px), `z-index` 6, and `grid-viewport`'s box unchanged (1 px). It still shows 2,700 ms after it appeared, has `data-off` and `opacity` 0 by 3,400 ms, and is gone by 3,700 ms. A `reveal_result` seq 7 by `p2` (scope letter) shows the note `Bob a révélé une lettre` whose first child has the pictogram `content` `"▲"`; a `flag_changed` seq 8 by `p2` on IDES, 1,000 ms later, replaces it at once by `Bob bloque sur « Fatales à César »` with the flag icon first. A `check_result` by `p1` and a `chat_message` of `p1` make no note; a `check_result` by `p2` makes one; a `reaction` of `p1` with `wow` makes `Vous avez réagi : 😮`; a `reaction` of `p2` makes none. A click on a shown note opens the Salon on `salon-tab-discussion` and removes the note. With the Salon open on Discussion, a `chat_message` from `p2` makes no note. While the mock's `vote_opened` (by `p2`, a grid check) keeps `vote-banner` on the page, two `chat_message` from `p2` (`un`, `deux`) make no note; once the mock's `vote_closed` (`passed`) comes, the banner is gone within 300 ms and one note shows, reading `fr.json["vote.result.passed"]`, the newest, and no note `Bob : deux` shows. (Note from the lead, 2026-10-22: refined by spec 047, the design's room overlays; this read "once the banner has gone (after `vote_closed` and spec 025's result time), one note `Bob : deux` shows": the banner leaves at `vote_closed`, and the vote's result is a note.) Under `page.emulate_media(reduced_motion="reduce")` the note's `transition-duration` is `0s`. A click on `undo-button` answered by `error` `nothing_to_undo` shows `undo-message` (`role="status"`, `fr.json["undo.nothing"]`) with the note's look and place, also with the Salon open on Discussion.
- **AC-27** (new; refines spec 026 AC-10 and spec 028 AC-7) (browser with mocked socket) The completion status is a band under the clue bar, except in the phone row, and holds « Voir le bilan ». On a FX-01 snapshot whose 18 cells hold their solution and `solved` true, at 1280 by 720 and 360 by 740: `grid-status` (`data-state="solved"`) has its top on `clue-bar`'s bottom and its left and right on the bar's (1 px), `background-color` rgb(230, 242, 234), padding `8px 12px`, its text `fr.json["completion.solved"]` in rgb(30, 123, 69), weight 600, `font-size` 15.2 px, after a pictogram whose `content` is `"✓"`; `recap-open` is inside it, after its text, its right edge on the band's content right edge (1 px), with the primary button's colours, padding `7px 12px` and `font-size` 13.6 px; a click on it opens `recap` (spec 028). On a full and wrong grid (`grid_full_wrong`), `grid-status` (`data-state="full_wrong"`) has `background-color` rgb(238, 242, 248), text colour rgb(27, 47, 85), and no `recap-open`. At 568 by 320 in the touch context, the solved page has no `keyboard` and `data-layout="column"` (spec 044), and `grid-status` is under the bar with the primary `recap-open`; on the full-and-wrong snapshot there (sheet layout, the keyboard shown), `grid-status` lies inside `clue-bar`'s box, right of `clue-bar-text` and left of `react-button`, its text colour rgb(255, 255, 255), with no `recap-open`; at 568 by 320 in the desktop context (column layout), `grid-status` is under the bar. Build order: spec 043 is built before spec 044, so the solved page at 568 by 320 in the touch context (no `keyboard`, `data-layout="column"`, the band under the bar) is not checked by spec 043's build, whose page there still shows the keyboard in the sheet layout; spec 044's build checks it (spec 044 AC-9, and its "Refined specs" row for this criterion, whose test it updates). Spec 043's build checks the rest, the full-and-wrong case in the touch context at 568 by 320 included, which holds before and after spec 044. (Note from the lead, 2026-10-22: the two sentences before this note were added after spec 043 WP-1's test-writer's question.) (Note from the lead, 2026-10-22: refined by spec 044, the design's keyboard; this read "At 568 by 320 in the touch context (sheet layout), the solved `grid-status` lies inside `clue-bar`'s box, right of `clue-bar-text` and left of `react-button`, its text colour rgb(255, 255, 255), and `recap-open` has the secondary button's colours".)
- **AC-28** (new) (browser with mocked socket) Everything stays inside the window and the grid keeps its room, whatever is open. With `H8`, at each window size of spec 006 AC-5, in desktop and touch contexts, in four states (all closed, the column layout's Salon closed by a click on `chat-toggle`; the Salon open on Discussion; `aide-menu` open; `room-menu` open): spec 013 AC-6's checks hold (`grid-viewport` at least 100 px high, no vertical or horizontal page scroll, the grid inside the viewport at zoom 1, `clue-bar` inside the window and, in the touch context, at or above the top of `keyboard`); `room-topbar`, `clue-bar` and, when open, the popover and the Salon lie inside the window (1 px); `elementFromPoint` at the centre of each top-bar button and each clue-bar button returns it, except where the open Salon sheet or an open popover's scrim covers the clue bar (sheet layout) (Note from the lead, 2026-10-22: this read "except where the open Salon sheet covers the clue bar (sheet layout)"; in the sheet layout an open `aide-menu` or `room-menu` shows `room-scrim` from 54 px below the window's top (AC-12, "Popovers: shared rules", `_design.md` section 8), which covers the clue bar's buttons as the Salon sheet does); at the centre of each item of an open popover, after `scrollIntoView({block: "nearest"})` of the item, it returns that item; `grid-viewport`'s box is the same in the four states in the sheet layout (1 px); and the timer's text `10:00:00` is on one line. On the same page, with the Salon open in the column layout, the `grid` box is the same before and after the mock sends 3 more line events (1 px). At 568 by 320 and 740 by 360, in the desktop context and in the touch context with `nock.keyboard_hidden` seeded `"true"` (spec 044's column layout), `room-topbar` is the phone top bar (54 px high, no `topbar-brand` shown) and the checks above hold in the four states. (Note from the lead, 2026-10-22: added, the lead's decision recorded as spec 044's Decision 8; with the computer top bar these windows were narrower than the bar.)
- **AC-29** (new; refines spec 035 AC-3's order) (browser with mocked socket, keyboard only after the setup) The page reads in the design's order and every control shows its ring. At 1280 by 720 on a FX-01 snapshot with `you` host, the focusable elements that show come in this document order: `undo-button`, `pencil-toggle`, `aide-button`, `chat-toggle`, `menu-button`, the `grid`, `clue-prev`, `react-button`, `flag-button`, `clue-next`, then the Salon's `salon-tab-discussion` and its later controls. With the grid focused and (1, 0) selected, `Escape` then `Tab` puts the focus on `clue-prev` with the selection unchanged; `Escape` then `Shift+Tab` from the grid puts it on `menu-button`. Each top-bar button reached by `tab_to` has a `2px` `solid` rgb(27, 47, 85) outline with `outline-offset` `2px`, inside the window; each clue-bar button the white ring of AC-23. At 360 by 740 the order is `undo-button`, `aide-button`, `chat-toggle`, `pencil-toggle`, `menu-button`, the `grid`, then the clue bar's four buttons.
- **AC-30** (new; extends spec 042's swatch rule to the stream) (browser with mocked socket) The Accessibilité mode shows each player's icon wherever a dot shows. On a FX-01 snapshot with `p2` (colour 1) and `p3` (colour 2) and `chat` lines of `p2` and `p3`, at 1280 by 720, after `open_menu` and a click on `access-switch`: each `chat-dot` and each `roster-colour` has a background alpha 0 and holds one `player-icon`, 12 by 12 px (0.5 px), with `data-icon` equal to its `data-colour` and the shapes of `PLAYER_ICONS[N]` (spec 042 AC-11); after a second click they hold none and have their player colours again.
- **AC-31** (new) (browser with mocked socket; static) The new room passes spec 035's scans, and `fr.json` holds the keys of this spec. At 1280 by 720 and 360 by 740, in these states of `H8` with `p2`'s flag on IDES, (1, 1) holding `X` wrong and a `clap` reaction of `p2` shown on IDES: all closed; the Salon on Discussion; the Salon on Joueurs; `aide-menu` open; `room-menu` open; `host-settings` open; a `room-note` shown; `connection-banner` shown; and `grid-status` solved (on the solved snapshot of AC-27), spec 035's contrast scan (its AC-8) and language scan (its AC-9, with the nicknames, the chat texts and the clue texts as test data) find no offending element. Static: `web/src/i18n/fr.json` holds every key of "New" and "Changed values" with those values, and none of the keys of "Removed".

## Edge cases and errors

- Layout at a threshold (AC-1): 900 by 600 is a column (at least 900 wide), 899 by
  600 a sheet; a square window is never landscape, so it is a sheet. A window that
  changes layout while a popover or the picker is open closes it; the Salon takes
  the state of the new layout (closed in the sheet layout until opened; the column
  by `nock.salon_closed`).
- Salon closed on a computer (AC-13): the choice holds in every room of this
  browser. On a phone the key is ignored and the sheet starts closed.
- Popovers and dialogs (AC-11, AC-21, AC-22): a dialog is modal (`showModal`), so
  the top bar and the Salon are inert while it is open; on a phone the top bar
  stays visible above its backdrop.
- A switch in the Menu (AC-11): the Menu stays open so that several switches can be
  flipped in a row; every other item closes it.
- Aide in help mode `none` (AC-8): the menu holds the pencil confirm when it applies,
  otherwise the one muted line; the button never disappears, so the top bar does
  not change with the room's settings.
- An item that becomes disabled while the menu is open (AC-9): a `vote_opened`
  disables `check-grid` and the reveal items (spec 025); the menu stays open.
- The pencil confirm appearing while the Aide menu is open (AC-8): the item and its
  separator are added at the top; the focus stays where it was.
- Unread and new events (AC-5, AC-17): my own lines never count; a message wins over
  the dot; catch-up lines (spec 034) count as new events.
- Chat lines of a player who left (AC-16): their name is the known name (spec 022),
  their dot is absent, since the page no longer knows their colour.
- Stream caps (AC-16): each kind keeps its own cap, so a burst of messages never
  pushes the event lines out, and spec 013 AC-7's and spec 022 AC-11's full-list
  cases keep their counts.
- Current clue (AC-19): a selection whose word the grid no longer has (a later
  snapshot of another grid) shows no clue; my own row follows my selection at once,
  before the server relays it.
- A long nickname or clue in a Joueurs row (AC-19): the name wraps on line 1 before
  the buttons, the clue ends with an ellipsis on line 2; the buttons never leave
  the Salon.
- The clue bar on a narrow column (AC-23): at 568 by 320 in the column layout the
  bar is about 203 px wide, which leaves about 50 px of clue text with its
  ellipsis; spec 007 AC-4's 14 px minimum holds (15.2 px).
- Chevrons with no unfinished word (AC-24): nothing changes and nothing is sent, as
  spec 009's `Tab`.
- The picker and a vote (AC-25, Decision 10): while `vote-banner` is on the page
  `react-button` is disabled, so the picker, which sits over the bottom of the same
  viewport, can never cover the vote buttons on a short grid area; an open picker
  closes when the banner comes (spec 022's rule for a button that becomes
  disabled).
- The banner over the Salon sheet (AC-28, spec 022 AC-17): on a phone the sheet can
  reach the banner's place on a low window; the banner is drawn above it and the
  Salon stays open under it.
- Notes and the stream (AC-26): a note is never made while the stream shows, so a
  player reading the stream is not shown the same line twice; `undo-message`
  answers the player's own action and always shows.
- Notes during a vote (AC-26): only the newest waiting note shows after the banner,
  so a vote never builds a queue of notes.
- A note for a line that the player then opens (AC-26): the tap opens the Discussion
  tab; the stream keeps spec 013's scroll rules, so it shows the newest line when it
  was at its end.
- Completion in the phone row (AC-27): on a sheet layout at most 500 px high, the
  status and « Voir le bilan » share the clue bar's row, so they take no height
  from the grid while the in-app keyboard shows (spec 026 decision of 2026-10-15);
  step 4's « Clavier » and step 5's band remove this case. (Note from the lead,
  2026-10-22: refined by spec 044, the design's keyboard: the row is kept only
  while the keyboard shows on a low window, so only a full-but-wrong status uses
  it; a solved page has no keyboard, and on a phone held sideways it is the column
  layout with the band.)
- Top bar at 283 px (AC-4): the five buttons shrink to about 44 px; below 296 px
  with the timer at `10:00:00` they would reach their 40 px minimum and the timer
  may push them past the right edge. The test sizes start at 320 px for the long
  timer.
- Grid name (AC-3): no slot is drawn in this step, so nothing is empty on screen;
  `topbar-brand` takes the free room (Open question 6).
- `localStorage` that throws (AC-13): the column opens at each load and closing it
  holds for the page's life only.
- Accounts off or failed (AC-10): no `account-open`; the separator still comes
  before `timer-toggle`.

## Out of scope

Dependencies on later steps, which this step leaves as they are:

- Step 4 (keyboard): the « Clavier » button and hiding the in-app keyboard (so a
  phone held sideways keeps the sheet layout in this step), the ✎ and ⇄ keys, the
  key geometry and colours of `_design.md` section 8. Until then `pencil-toggle`
  sits in the phone top bar (Decision 6) and the in-app keyboard keeps spec 009's
  look. (Note from the lead, 2026-10-22: spec 044, the design's keyboard, does all
  of this, and also hides the in-app keyboard once the grid is solved, which the
  next item gave to step 5.)
- Step 5: the Auteurs mode (its inks, its legend, its persistence; `authors-switch`
  is moved, not changed, and `clue-bar-author` stays in the clue bar until then),
  the vote banner's look (spec 025), hiding the in-app keyboard once solved and the
  end band's final place (spec 026), the recap's look and dots (spec 028), the
  catalogue and its sections, the entry and not-found pages (specs 004, 012, 029,
  032, 040), and the grid name in the top bar if a later spec gives the client the
  grid's number and force.

Not done at all:

- Dragging the Salon sheet by its handle.
- A scroll to the line of a tapped note (Open question 12).
- A live `word_completed` line (the design drops the « a rempli » line; Open
  question 11).
- Screen reader announcements of other players' actions (spec 022 and spec 035
  leave them out); the notes are `aria-hidden`.
- Screenshot comparison with the sheet (`_design.md` section 13), a dark mode,
  forced-colours and print styles.

## Work packages

Step 3 is too large for one pull request: it rewrites the room page's whole frame
and the tests of 17 refined specs. It splits into two pull requests, built one
after the other (not by parallel implementers, since both change
`web/src/lib/RoomPage.svelte`), each leaving the app working and every test
passing:

1. WP-1, the frame: "Which layout", "Document order", the top bar with the badge
   (AC-1 to AC-4, AC-5 without `salon-dot`, AC-6, AC-7), the Aide menu and the Menu
   and their rules (AC-8 to AC-12), the Salon, its progress and tabs, the stream
   without pictograms, colours and dots, the message box, the Joueurs rows and the
   invitation (AC-13 to AC-15, AC-16's order and caps, AC-17 without the dot, AC-18
   to AC-20), the room sheets (AC-21, AC-22), the clue bar and its buttons
   (AC-23, AC-24), the picker's place (AC-25's picker part), the completion status
   and « Voir le bilan » (AC-27), the layout and focus checks (AC-28, AC-29), the
   scans and keys (AC-31, without its `room-note` state), and every refined
   criterion of "Refined specs". Files:
   `RoomPage.svelte` and the components it is split into, `ChatPanel.svelte`
   (folded in), `chat.ts`, `activityFeed.ts`, `i18n/fr.json`, `app.css` (no new
   token).
2. WP-2, the feedback: the new-events dot (AC-5's dot part, AC-17's dot part), the
   stream's pictograms, colours and player dots (the rest of AC-16), the reaction
   pill (AC-25's pill part), the 3-second notes and `undo-message` as a note
   (AC-26), the Accessibilité icons in the stream (AC-30), and AC-31's `room-note`
   state. Files: the stream and note components, `GridViewport.svelte` (the pill),
   `roomSession.ts` (the note events). Until WP-2, `undo-message` keeps today's
   look, inside `grid-area`.

The test-writer of each package writes the tests of its criteria (and of the parts
named) and updates the refined tests of WP-1 with WP-1.

## Decisions

Decided by the lead on 2026-10-22, on the human's instruction of 2026-10-22, and
already recorded in `_design.md` section 15: the 900 px rule and the phone held
sideways (item 5), « Compte » in the room Menu after « Réglages de l'hôte » (item
7), the new-events dot at the badge's place on a computer (item 9), `room-heading`
visually hidden (item 10), ← for departures (item 11), and a reaction on a
two-clue cell centred on its own half (item 8).

Proposed by the spec writer, each already part of the spec above:

1. Test ids are kept where the role is the same, so that the tests of every spec
   that uses them follow with the least change: `chat-toggle` is the « Salon » button,
   `chat-unread` its badge, `chat-panel` the Discussion tab, `activity-feed` the
   stream and `chat-list` its list, `roster` the Joueurs tab, `share-panel` the
   invitation block, the check, reveal, pencil and switch ids their menu items,
   `timer-toggle` the Menu item, `lock-room` the switch.
2. The popovers, the Salon and its panels are always in the DOM once the page has a
   snapshot and carry `hidden` while closed. Tests that read attributes, texts and
   computed colours keep working; only tests that act or measure open them first,
   with shared helpers.
3. Messages and events share one list, ordered by seq, each kind with its own cap;
   spec 013's scroll rules apply to the whole list. One list removes the two lists'
   separate scroll, Tab-stop and height rules.
4. Pictograms are CSS generated content on an empty `aria-hidden` element, so the
   texts of spec 013's lines, the clue bar's text and the menu labels stay exactly
   what their specs and tests read.
5. The host's « Couper » moves from the chat panel to the Joueurs rows, beside
   « Retirer », and each row gets a second line for the state and the current clue
   (Open questions 2 and 3). The chat panel has no room for a moderation list in the
   design, and the current clue, the one word sign of where a player is, needs a
   line of its own to stay readable at 340 px.
6. « Crayon » takes the phone top bar's fourth slot until step 4 puts « Clavier »
   there and the ✎ key on the keyboard (Open question 5), so a touch player keeps
   the pencil mode in this step. (Note from the lead, 2026-10-22: spec 044, the
   design's keyboard, does it on touch screens; off a touch screen, where there is
   no keyboard to hide, « Crayon » keeps the fourth slot.)
7. The Aide button stays in help mode `none` (Open question 4); its menu then holds
   the pencil confirm or a muted line.
8. Aide items have no `aria-label`: their names are their visible texts, inside a
   group named by its heading (« Vérifier », « Révéler »), which meets WCAG 2.5.3
   without the long labels of specs 023 and 024. Menu details are `aria-hidden`, so
   a switch's name is its label and its state is `aria-pressed`.
9. The completion status keeps spec 026's in-row place only in the phone layout of a
   low window, where the in-app keyboard leaves no height for a band (Open question
   8); everywhere else it is the design's band, and « Voir le bilan » moves into it
   now, since the toolbar it lived in goes. (Note from the lead, 2026-10-22: refined
   by spec 044, the design's keyboard: the row is used only while the keyboard
   shows on a low window, never on a solved page.)
10. `react-button` is disabled while the vote banner shows (Open question 9): the
    picker and the banner sit over the same viewport and could meet on a short grid
    area.
11. The room sheets are modal dialogs in both layouts: one rule for focus, inertness
    and `Escape`.
12. The clue bar is never narrower than the smaller of 320 px and the play area: the
    design's "as wide as the grid" would leave no room for the clue text beside four
    buttons on a small grid.

Decided by the human on 2026-10-22, with the spec's approval (these were the Open
questions, answered with their recommended answer; the text above already follows
them). The number in brackets is the question's number, which the text above cites:

13. (Open question 1.) One pull request or two. Options: one; the two work packages
    above. Answer: two (WP-1 the frame, WP-2 the feedback).
14. (Open question 2.) Where the host mutes a player. Spec 022 decision 11 (the
    human's, 2026-10-14) put the mute buttons in the chat panel because the old
    roster had no room. Options: keep a moderation block in the Discussion tab,
    under the stream; or « Couper » beside « Retirer » in each Joueurs row. Answer:
    the Joueurs row (Decision 5).
15. (Open question 3.) The Joueurs row on one line, as drawn (state and clue on the
    right of the name), or on two lines. Answer: two lines, state and clue under
    the name (Decision 5); `_design.md` section 8 carries a note on it.
16. (Open question 4.) Aide in help mode `none`: hidden, as `_design.md` section 12
    suggested "to confirm", or kept with the pencil confirm and a muted line.
    Answer: kept (Decision 7).
17. (Open question 5.) The pencil toggle on touch screens before step 4. Options:
    « Crayon » in the phone top bar's fourth slot; or no pencil mode on touch
    screens until step 4. Answer: the fourth slot (Decision 6). (Note from the
    lead, 2026-10-22: spec 044 settles what follows step 4: « Clavier » on touch
    screens, « Crayon » kept off them; its Open question 2.)
18. (Open question 6.) The grid name « Grille n° N · Force F » of the computer top
    bar. The client knows the grid number only for rooms started on this device
    (spec 010's room record) and never the force. Options: leave it out in this
    step; show « Grille n° N » when known; add the number and force to the snapshot
    (a protocol change, a new spec). Answer: leave it out now, and a later spec
    adds them to the snapshot.
19. (Open question 7.) The timer: a button with no border (the sheet), or text.
    Nothing is said to happen on a press. Answer: text, as spec 027 has it, never
    a Tab stop.
20. (Open question 8.) The completion status on a phone held sideways. Options: the
    design's band under the clue bar now (the grid then falls under spec 013 AC-6's
    100 px at 568 by 320 with the in-app keyboard); or spec 026's place in the clue
    bar's row there until step 4 can hide the keyboard. Answer: the row there, the
    band elsewhere (Decision 9). (Note from the lead, 2026-10-22: spec 044 keeps
    the row only while the keyboard shows on a low window; a solved page has no
    keyboard, so its status is always the band.)
21. (Open question 9.) Reactions during a vote. Options: `react-button` disabled
    while the banner shows; the picker drawn under the banner (against the design's
    layers). Answer: disabled (Decision 10).
22. (Open question 10.) A disabled icon on the navy clue bar. `_design.md` section 2
    asks 4.5:1 for disabled controls too, and no token has that job on navy.
    Options: `--nock-rule` (5.22:1 on navy, a new job for the rule grey); hide the
    disabled buttons. Answer: `--nock-rule`; `_design.md` section 2 carries a note
    on it.
23. (Open question 11.) Spec 034's `word_completed` catch-up lines against the
    design's dropped « a rempli » line. Options: keep them (spec 034 was approved
    after the design, for the catch-up only) and add no live line; drop them.
    Answer: keep them, no live line.
24. (Open question 12.) A tap on a note "opens the Salon on that line". Options:
    open the Discussion tab and leave the stream to spec 013's scroll rules; or
    also scroll the line into view. Answer: the first; a scroll would break the
    rule that the page never moves a list the player is reading.

## Open questions

None left (all answered with the approval of 2026-10-22).
