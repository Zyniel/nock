---
id: "047"
title: Room overlays
status: approved
---

# 047 - Room overlays

Epic E10 Quality bar · Release: MVP · No backlog story: this is the "overlays" part
of build step 5 of `specs/_design.md` (section 14; `docs/build-plan.md` Phase 7,
order 7). It applies `_design.md` section 9 (the vote banner, the end-of-grid band,
the recap), section 8 where it speaks of them ("3-second notes": a vote's result;
"Salon": the chat notes and a muted player's message box; "States": the recap's
loading and unavailable states; "Layers"), section 11 (components) and the parts of
sections 2 (colour tokens and their jobs) and 4 (vote question, vote seconds,
dialog title, dialog section heading, recap time, recap lines and rows, URL box,
error and confirmation lines) that these overlays use. It builds on spec 041
(tokens, fonts, the primitives `nock-button`, `nock-note`), spec 042 (`player-icon`),
spec 043 (the room layout: `grid-area`, `grid-viewport`, the Salon and its stream,
`room-note`, `grid-status` as the end band, `recap-open` in it, the room sheets'
dialog rules, the layers) and spec 044 (the keyboard gone once solved), and
redefines none of them; where it changes one of their rules, "Refined specs" says
so. The FX-01 reference grid is in `specs/_reference.md`; the stack in
`specs/_architecture.md`.

## Goal

The human validated the look of the room's overlays (`_design.md` section 9 and the
screens sheet, parts 4 and 5) and decided on 2026-10-22 how the vote reads after a
player has voted and how it ends (P6), how the recap reads while it loads or fails
(P10), and that « Lien copié » is a line under the recap's link, not a new label of
its button (P16). This spec draws the vote banner with its countdown, ends a vote
with a 3-second note and a line in the stream instead of a result held in the
banner, settles the end band on narrow windows, and draws the recap as the design's
dialog on a computer and bottom sheet on a phone. It also gives spec 022's chat
notes and a muted player's message box the look `_design.md` section 8 now gives
them. The rule of the human holds throughout: the simplest design that removes edge
cases. A vote has one place on screen while it is open (the banner) and one way to
tell how it ended (a note and a stream line, which every other room event uses), so
the banner's result state and its timer go.

## Public interface

No new Python name, no new protocol message, no new HTTP route. Client only
(`web/`: chiefly `web/src/lib/RoomPage.svelte` and the components spec 043 split it
into, `web/src/lib/RecapDialog.svelte`, `web/src/lib/roomSession.ts`,
`web/src/lib/activityFeed.ts`, `web/src/i18n/fr.json`). Every colour is a token of
spec 041 used for its job in `_design.md` section 2, every string comes from
`web/src/i18n/fr.json`.

### Terms

- Sheet layout and column layout, the play area, `grid-area`, `grid-viewport`, the
  stream, "the stream is shown", a pictogram: as spec 043's "Terms".
- The grid area of the banner: `grid-area` in the sheet layout; `grid-viewport` in
  the column layout, where spec 043 makes the viewport the grid's own box.
- `VOTE`: the `VoteOpened` event of "Test harness".
- A vote the page saw open: a vote whose `vote_opened` event this page applied (spec
  040), as opposed to one it only learned from a snapshot's `open_vote` (a page
  loaded or reloaded while the vote was open, or a player who joined during it).

### Vote banner (`_design.md` section 9, spec 025)

`vote-banner` keeps spec 025's role, label, presence rule while the vote is open,
its place in document order (before the `grid`), its ids and its focus rules, and
spec 043's layer (9, drawn above the Salon sheet and the scrim; Note from the lead,
2026-10-22: this read "8"; spec 043's "Layers" puts the banner on layer 9 since
spec 043 WP-1's first review, as its code has it). Its look:

- Place: absolutely positioned over the top of the grid area, its top, left and right
  edges 8 px inside those of the grid area, so it lies inside `grid-viewport` (spec
  025) and moves nothing (no layout shift).
- Box: `--nock-white` background, a `2px solid var(--nock-navy)` border, radius
  10 px, padding 10 px 12 px, a column of its parts with gap 8 px, shadow
  `0 10px 24px -12px var(--nock-shadow)`.

Its parts, top to bottom:

1. `vote-question` (spec 025's text): 600 0.95rem/1.3 `--nock-font-ui`,
  `--nock-ink`; it wraps.
2. `data-testid="vote-row"`: a row, items centred vertically, gap 8 px, at least
  31 px high. It holds, while this page can still vote, `vote-yes` (`nock-button
  nock-button-primary`) and `vote-no` (`nock-button nock-button-secondary`), each
  with padding 7 px 16 px; once it has voted, or on the requester's page, spec 025's
  `vote-status` instead (see "After a vote"). Last in the row, pushed right
  (`margin-left: auto`), `data-testid="vote-seconds"` (see "Countdown").
3. `data-testid="vote-timebar"`, `aria-hidden="true"`: 4 px high, radius 2 px,
  background `--nock-word`, clipped, holding `data-testid="vote-timebar-fill"`, full
  height, `--nock-navy`, its width the share of the time left (see "Countdown").

After a vote (refines spec 025 and its `fr.json` key, `_design.md` section 9, P6):

- `vote-status` sits in `vote-row` in place of the two buttons: 500 0.85rem/1.3,
  `--nock-muted`, one line or more, its `tabindex="-1"` and focus rules unchanged
  (spec 025). It reads `t("vote.cast")` on a page that voted and
  `t("vote.waiting")` on the requester's page, as spec 025 says; the value of
  `vote.cast` becomes « Vote enregistré. En attente des autres joueurs… », so that
  the line says both what was done and what comes next.
- `vote-seconds` and `vote-timebar` stay.

Countdown (`_design.md` section 9; Decision 2):

- For a vote the page saw open, the page notes `opened`, its own clock time when it
  applied that `vote_opened` (`performance.now()`), and `deadline = opened +
  timeout_seconds × 1000`. A later snapshot that holds the same `vote_id` (a
  reconnection, spec 017) keeps them.
- `vote-seconds` reads `t("vote.seconds_left", { count })` with `count =
  max(0, ceil((deadline − now) / 1000))`, 500 0.85rem/1 `--nock-font-ui`,
  `--nock-muted`, `font-variant-numeric: tabular-nums`, on one line; it is updated
  at least every 250 ms, so it reads « 20 s » when the vote opens and « 0 s » once the
  time is up, until `vote_closed` comes.
- `vote-timebar-fill` is `max(0, (deadline − now) / (timeout_seconds × 1000))` of the
  bar's width (1 px), updated at the same pace. It has no CSS transition, so it
  moves in steps with `prefers-reduced-motion: reduce` as without it.
- For a vote known only from a snapshot, the page does not know when it opened (the
  snapshot carries no opening time, spec 039): there is no `vote-seconds` and no
  `vote-timebar`. The banner keeps its question and its row.
- The countdown is the page's own: nothing is sent, and the vote still ends when the
  server says so (`vote_closed`).

The end of a vote (refines spec 025's "Client: votes", `_design.md` sections 8 and 9,
P6; Decision 1):

- When the page applies a `vote_closed`, `vote-banner` leaves the page at once
  (within 300 ms). It never shows a result: `vote-result` and spec 025's
  `VOTE_RESULT_MS` and `closedVote` go.
- `vote-announcement` (spec 025: visually hidden, `role="status"`, polite, atomic)
  then holds `t("vote.result.<outcome>")`, so a screen reader hears how it ended.
- The stream gets one event line for it (refines spec 013's feed table): a
  `feed-item` with `data-kind="vote"`, `data-seq` the `vote_closed`'s seq, and the
  text `t("vote.result.<outcome>")`. It has spec 043's event look with no pictogram
  and the colour `--nock-muted`, whatever the outcome. It counts toward spec 013's
  100 event lines. It does not make `salon-dot` show (it is by no player, and every
  page showed the banner). The snapshot and spec 034's catch-up add no such line.
- That line makes a 3-second note (refines spec 043's "3-second notes"): a
  `room-note` with the line's text, made after the banner has left, so it is never
  held back by it. It follows spec 043's rules: no note while the stream is shown,
  one note at a time (the newest wins, so it replaces a note that waited during the
  vote).
- When the grid is solved while a vote is open, the banner leaves as spec 025 says;
  the later `vote_closed` still adds its line and its note.

### End-of-grid band (`_design.md` section 9, specs 026, 028, 043)

`grid-status` keeps spec 026's role, states and texts, spec 043's band look
(background, colours, padding 8 px 12 px, 600 0.95rem/1.2, the ✓ pictogram) and
spec 044's places. This spec adds how the band lays out its two parts:

- The band is a row, items centred vertically, gap 10 px: first
  `data-testid="grid-status-text"` (the pictogram and the text of spec 026; its text
  content is spec 026's text), then, on a solved page, `recap-open` (spec 043:
  primary, padding 7 px 12 px, 0.85rem), pushed right.
- `grid-status-text` wraps when the band is too narrow for both parts on one line;
  `recap-open` never wraps or shrinks (`white-space: nowrap`, `flex: none`) and stays
  inside the band, on its right. The band grows by the extra line; it is still
  inside the window, and spec 013 AC-6's checks still hold.
- In the clue bar's row (spec 044: a full-but-wrong status while the keyboard shows
  on a low window), nothing changes: spec 026's one-line rule holds there.

### Recap (`_design.md` section 9, spec 028)

`recap` keeps spec 028's element (`<dialog>` opened with `showModal()`, labelled by
its `h2`), its opening and closing rules (opens only on `recap-open`, fetches each
time it opens, `Escape` and `recap-close` close it, the focus goes back to
`recap-open`), its test ids and texts. Its frame:

- Column layout: centred, 440 px wide (at most the window's width less 32 px), at
  most the window's height less 32 px high, its content scrolling inside it when
  taller, `--nock-white`, radius 12 px, padding 20 px 22 px, its parts in a column
  with gap 14 px, shadow `0 20px 40px -16px var(--nock-shadow-strong)`.
- Sheet layout: a bottom sheet: full width, its bottom on the window's bottom, at
  most the window's height less 54 px high, its content scrolling inside it when
  taller, `--nock-white`, top corners radius 16 px, bottom corners 0, padding 14 px
  18 px 18 px, gap 14 px, no grab handle.
- In both: its `::backdrop` is `--nock-scrim-dialog` over the whole window, the top
  bar included (unlike spec 043's room sheets, whose scrim starts under the top
  bar); the dialog is in the top layer (`_design.md` section 8's layer 20).

Content once loaded, in this order (spec 028's elements, reordered as section 9
draws them):

1. The `h2` (`t("recap.heading")`): 700 1.2rem/1.2, `--nock-navy`, margin 0.
2. `recap-time`: 700 2.1rem/1 `--nock-font-ui`, `--nock-navy`, tabular.
3. `data-testid="recap-lines"`, a column with gap 4 px holding `recap-checks`,
   `recap-reveals` and `recap-revealed`, in that order; each 400 0.95rem,
   `--nock-ink`. (`recap-revealed` moves here from after the players.)
4. The `h3` `recap-players-heading` (`t("recap.players_heading")`): the dialog
   section heading of `_design.md` section 4 (600 0.78rem/1.2, uppercase, letter
   spacing 0.07em, `--nock-muted`), margin 0.
5. `recap-players` (spec 028's list, rule and order), rows 8 px apart. Each
   `recap-player` is a row that wraps, items centred vertically, gap 8 px:
   - `recap-colour`: the player dot of `_design.md` section 11 (10 px circle,
     `--player-colour-N`, ring `0 0 0 1px var(--nock-dot-ring)`). While
     `access-switch` (spec 042) is on, it has a transparent background and no ring
     and holds one `player-icon` `svg` of 12 by 12 px for that colour index (spec
     043's rule for `chat-dot`). With `data-colour=""` (a player the kept snapshot
     no longer lists), it draws nothing: a 10 by 10 px box with a transparent
     background, no `background-image` and no shadow, so the names stay aligned
     (Decision 4; this replaces spec 028's hatching);
   - `recap-name`: weight 600, 0.95rem, `--nock-ink`;
   - on my row, `t("roster.you")` in `data-testid="recap-you"`, 400 0.95rem,
     `--nock-muted`;
   - `data-testid="recap-values"`, pushed right (`margin-left: auto`), 0.85rem,
     `--nock-muted`, tabular, holding `recap-letters`, then
     `data-testid="recap-sep"` (the « · » pictogram, `aria-hidden`, with a space on
     each side), then `recap-words`.
   - Sheet layout: `recap-values` always takes a line of its own under the name,
     its left edge 18 px right of the row's left edge (the dot and the gap). Column
     layout: it sits on the name's line, at the right; when the row is too narrow
     it wraps under the name the same way.
6. When `share_path` is not null (spec 028): `data-testid="recap-share-heading"`,
   `t("recap.share_label")` in the dialog section heading style, the element that
   labels `recap-share-link` (spec 028's label); then `data-testid="recap-share-row"`:
   - column layout: one row, items centred vertically, gap 8 px: `recap-share-link`,
     the URL box of `_design.md` section 11 (block, 1 px solid `--nock-rule` border,
     radius 6 px, padding 8 px 10 px, 400 0.85rem, one line with an ellipsis), which
     takes the width left (`flex: 1`, `min-width: 0`); then `recap-copy`;
   - sheet layout: `recap-share-link` takes the full width, and `recap-copy` goes
     under it, on the left, 8 px below;
   - `recap-copy`: `nock-button nock-button-secondary`, padding 8 px 12 px, its text
     `t("room.share.copy")` at all times;
   - after a successful copy, `data-testid="recap-copied"`, `role="status"`, under
     `recap-share-row`: the confirmation line of `_design.md` section 11 (500
     0.85rem/1.3, `--nock-green`), text `t("room.share.copied")`, for 2 seconds
     (spec 011's time). Without a usable clipboard nothing changes.
7. `recap-close`: `nock-button nock-button-primary`, its right edge on the dialog's
   content right edge.

Loading and unavailable (`_design.md` section 8 « States », P10): while the request
runs, the dialog holds the `h2`, then `recap-loading` (`t("recap.loading")`), a
muted line (400 0.95rem, `--nock-muted`, `role="status"`), then `recap-close`; when
it failed, the `h2`, `recap-error` (`t("recap.error")`, `role="alert"`), an error
line (500 0.85rem/1.3, `--nock-red`), then `recap-close`. The frame is the same as
loaded, with the same gap.

### Chat notes and a muted player's message box (`_design.md` section 8, spec 022, P5)

Spec 022's notes and spec 043's slot keep their rules (one slot, one note at a time,
`chat-muted` winning over `chat-wait`). Their look:

- `chat-wait` and `chat-muted`: 500 0.85rem/1.3, `--nock-muted`, on one line, their
  left edge 12 px right of the Salon's left edge (spec 043's slot padding).
- While I am muted (spec 022), `chat-input` and `chat-send` are disabled and look
  it: `chat-input` has the `--nock-clue-bg` background and `--nock-muted` text and
  placeholder; `chat-send` has spec 041's disabled look (`--nock-clue-bg`
  background, `--nock-muted` text). `chat-send` has the same disabled look whenever
  spec 022 disables it (an empty input, pacing, a page not joined).

### `fr.json` keys

New:

| Key | Value |
| --- | --- |
| `vote.seconds_left` | `{count} s` |

Changed values:

| Key | Value | Was |
| --- | --- | --- |
| `vote.cast` | `Vote enregistré. En attente des autres joueurs…` | `Vote enregistré.` |

`{count}` is already a number placeholder of spec 035 AC-9's checker, so
`vote.seconds_left` matches « 18 s » and not « Salle » or « Check word ».

### Refined specs

Each refined spec carries a dated note "(Note from the lead, 2026-10-22: refined by
spec 047, the design's room overlays ...)" and keeps its status. The test-writer
updates the tests of the criteria named here before the implementer runs.

| Spec | Criteria that change | What changes in their tests |
| --- | --- | --- |
| 013 | none | The feed table gains the `vote` line ("Client: activity feed"); AC-5 sends no vote, so it holds |
| 025 | AC-2 (browser), AC-3 (browser), AC-7, AC-8 | AC-2: after Bob's yes, both pages show no `vote-banner` within 1 s and a `feed-item` `data-kind="vote"` reading `fr.json["vote.result.passed"]` (the Salon column is open on Discussion at 1280 by 720, so no note), and `reveal-letter-detail` reads `4 restantes` (the `Lettre (4)` of spec 024 became a detail with spec 043); AC-3: after `vote_closed` `rejected`, `vote-banner` is gone within 300 ms, `vote-announcement` and a `vote` line read `fr.json["vote.result.rejected"]`, `reveal-letter-detail` reads `5 restantes`, the same with `timed_out`; AC-7: after `vote_closed` `passed`, the banner is gone within 300 ms and `vote-announcement` reads the result, in place of `vote-result` and the 2,500 to 4,500 ms; AC-8: the boxes compared are those of `room-topbar` (in place of "the room header"), `grid-viewport`, `clue-bar` and `keyboard`, and after the `vote_closed` the banner is gone and the focus is on the `grid` (no `vote-result`) |
| 028 | AC-2 (browser), AC-5 (browser, Chromium copy check), AC-10 | AC-2: after the `player_left` of `p2`, `p2`'s `recap-colour` has `data-colour=""` and draws nothing (background alpha 0, `background-image` `none`, `box-shadow` `none`), in place of the hatching; AC-5: after the click on `recap-copy`, `recap-copied` reads `fr.json["room.share.copied"]` while `recap-copy` still reads `fr.json["room.share.copy"]`; AC-10: on the solved page spec 043 AC-28's checks hold (no `H8` needed: the snapshot of AC-2) and `elementFromPoint` at the centre of `recap-open` returns it, in place of spec 024 AC-8's toolbar checks and the toolbar's `scrollLeft` |
| 043 | AC-26 | The vote part: once the mock's `vote_closed` comes, `vote-banner` is gone within 300 ms and one note shows, reading `fr.json["vote.result.passed"]` (the newest note); `Bob : deux` is not shown |

Specs 022, 026 and 035 get a note and no criterion change:

- Spec 022: the chat notes and the disabled message box get the design's look; its
  criteria read texts, presence, boxes and the focus, which do not change.
- Spec 026: the band's text wraps before `recap-open` on a narrow window; AC-10
  measures the clue bar's row only in the full-but-wrong case (spec 044), which this
  spec does not change.
- Spec 035: the vote's result is still announced by `vote-announcement`; the
  countdown is not a live region, so it announces nothing every second; its scans
  run on the new states through this spec's AC-14.

### Test harness

- "Browser with mocked socket" as in spec 043's "Test harness" (FX-01 snapshots from
  `grid_view(fx01_grid)` and `model_copy`, `seq` 5, `you` `p1` (`ANA`, colour 0,
  host), other players `p2` (`BOB`, colour 1) and `p3` (`CY`, colour 2)), with its
  helpers (`open_menu`, `show_tab`, `tab_to`) and its contexts and window sizes.
  Default: 1280 by 720, desktop context, empty `localStorage`.
- `VOTE_ROOM`: that snapshot with help mode `vote` and `reveal_budget` 5 letters and
  1 word. `VOTE`: `VoteOpened(seq=6, vote_id=1, player_id="p2",
  request=Reveal(target=CellTarget(row=1, column=0)), timeout_seconds=20,
  eligible_voters=3)`, built as spec 025's harness builds vote frames.
  `CLOSED(outcome)`: `VoteClosed(seq=7, vote_id=1, outcome=outcome, yes_votes=2,
  eligible_voters=3)`.
- Clock: criteria that read the countdown call `page.clock.install()` before the
  page opens, then move time with `page.clock.run_for(ms)` (as specs 014, 017 and
  027's harnesses do); the mocked socket's frames are sent between the steps.
- `SOLVED`: spec 044's (a FX-01 snapshot whose 18 letter cells hold their solution,
  `solved` true). The recap route `**/api/rooms/ABC123/recap` is answered by
  `page.route` with a chosen `Recap` JSON, as spec 028's harness; `RECAP` is spec
  028 AC-2's (`p1` `ANA` 8 letters 4 words, `p2` `BOB` 5 letters 3 words,
  `elapsed_ms` 754,000, `checks` 2, `letter_reveals` 1, `word_reveals` 1,
  `revealed_letters` 5) with `share_path` `/recap/tok_ABCDEFGHIJKLMNOP`.
- Clipboard (Chromium only): spec 011's harness, in a test marked
  `@pytest.mark.only_browser("chromium")`, as spec 028 AC-5.
- Positions are bounding boxes; tolerances 1 px for a position, 0.5 px for a size,
  0.1 px for a font size or a line height, unless a criterion says otherwise.
  Colours as spec 041 (`parseColour` of `tests/colour_contrast.js`, exact channels
  for a token, alpha within 0.01). A shadow is read from the computed `box-shadow`.
  A pictogram is checked on the computed `content` of its element's `::before` or
  `::after`. The `::backdrop` is read with `getComputedStyle(recap, "::backdrop")`.
- Fonts: spec 041's rule (wait for `document.fonts.ready` before reading a size or a
  position that depends on text).
- Engines: Chromium and WebKit locally, Firefox too in CI. Only the clipboard check
  of AC-11 is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (new; refines spec 025's banner look) (browser with mocked socket) The vote banner floats over the top of the grid area with the design's look. On `VOTE_ROOM`, after the mock sends `VOTE`, at 360 by 740 and at 1280 by 720: `vote-banner` has computed `position` `absolute`, `z-index` 9 (Note from the lead, 2026-10-22: this read "`z-index` 8"; spec 043's "Layers" puts the banner on layer 9 since spec 043 WP-1's first review), `background-color` rgb(255, 255, 255), a `2px` `solid` rgb(27, 47, 85) border on each side, `border-radius` `10px`, padding `10px 12px`, and a shadow with offsets 0 and 10 px, blur 24 px, spread −12 px and colour 20, 24, 31 at alpha 0.45; its top, left and right edges are 8 px inside those of `grid-area` at 360 by 740 and of `grid-viewport` at 1280 by 720 (1 px), and the boxes of `grid-viewport` and `clue-bar` are those read before `VOTE` (1 px). Inside it, top to bottom with 8 px between them (1 px): `vote-question` reading `Bob propose de révéler une lettre.` with `font-size` 15.2 px, `font-weight` 600, `line-height` 19.76 px and colour rgb(20, 24, 31); `vote-row`, at least 31 px high, holding left to right `vote-yes` (text `fr.json["vote.yes"]`, background rgb(27, 47, 85), colour rgb(255, 255, 255)), `vote-no` (text `fr.json["vote.no"]`, background rgb(255, 255, 255), colour and border rgb(27, 47, 85)), each with padding `7px 16px` and 8 px apart (1 px), and `vote-seconds`, whose right edge is the row's right edge (1 px), with `font-size` 13.6 px, `font-weight` 500, colour rgb(94, 101, 115) and `font-variant-numeric` `tabular-nums`; then `vote-timebar`, `aria-hidden="true"`, 4 px high, `border-radius` `2px`, background rgb(230, 237, 249), holding `vote-timebar-fill` with background rgb(27, 47, 85). The vertical centres of `vote-yes`, `vote-no` and `vote-seconds` are within 1 px of each other.
- **AC-2** (new) (browser with mocked socket, `page.clock`) The banner counts the seconds left of a vote the page saw open, and shows no count for a vote it only learned from a snapshot. On `VOTE_ROOM` at 1280 by 720 with `page.clock.install()`: once the mock's `VOTE` shows the banner, `vote-seconds` reads `20 s` (built from `fr.json["vote.seconds_left"]`) and `vote-timebar-fill` is as wide as `vote-timebar` (1 px). After `page.clock.run_for(5000)`: `vote-seconds` reads `15 s` and the fill is 0.75 of the bar's width (1 px). After 15,000 ms more: `0 s` and a fill 0 px wide (1 px); after 5,000 ms more, still `0 s`, and the banner still shows (only `vote_closed` ends it). With `page.emulate_media(reduced_motion="reduce")` the same steps give the same texts and widths, and the fill's `transition-duration` is `0s` in both runs. Reconnection: after `VOTE` and `run_for(5000)`, the mock closes the socket with code 1011 and answers the next join with a `VOTE_ROOM` snapshot whose `open_vote` is `VOTE` (seq 6); once `data-status` is `joined` again, `vote-seconds` reads `15 s` or less, never `20 s`. A page whose first snapshot is `VOTE_ROOM` with `open_vote` `VOTE` shows `vote-banner` with `vote-question`, `vote-yes` and `vote-no`, and no `vote-seconds` and no `vote-timebar`.
- **AC-3** (new; refines spec 025's `vote-status` look and `fr.json` value) (browser with mocked socket) Once I have voted, a muted line takes the buttons' place, and the requester sees the waiting line from the start. On `VOTE_ROOM` after `VOTE`, at 360 by 740 and at 1280 by 720: after a click on `vote-yes` (one frame that parses to `Vote(vote_id=1, yes=True)`), `vote-row` holds no `vote-yes` and no `vote-no`, and holds `vote-status` reading `fr.json["vote.cast"]`, which is `Vote enregistré. En attente des autres joueurs…`, with `font-size` 13.6 px, `font-weight` 500, `line-height` 17.68 px and colour rgb(94, 101, 115), its left edge on the row's left edge (1 px), then `vote-seconds` at the row's right edge; `vote-timebar` still shows; `vote-status` is `document.activeElement` (spec 025); a contrast of at least 4.5:1 against the banner's white. On a page whose first snapshot holds a vote by `p1` (`you`), `vote-row` holds `vote-status` reading `fr.json["vote.waiting"]` with the same look, and no button.
- **AC-4** (new; refines spec 025's end of a vote and spec 013's feed) (browser with mocked socket) A vote ends with the banner leaving, a line in the stream and, when the stream is not shown, a 3-second note. On `VOTE_ROOM` at 360 by 740 (the Salon closed), after `VOTE` and a click on `vote-yes`: when the mock sends `CLOSED("passed")`, within 300 ms no `vote-banner` and no `vote-result` is on the page, `vote-announcement` reads `fr.json["vote.result.passed"]`, one `room-note` shows reading `fr.json["vote.result.passed"]` with no pictogram (its text content is exactly that value), and the stream (`show_tab(page, "discussion")` afterwards) ends with one `feed-item` with `data-kind="vote"`, `data-seq="7"` and the text `fr.json["vote.result.passed"]`, with `font-size` 13.12 px, colour rgb(94, 101, 115) and no `feed-picto`; before that `show_tab`, no `salon-dot` showed and `chat-unread` was absent. The same with `rejected` and `timed_out` gives their `fr.json["vote.result.<outcome>"]` texts, the line's colour still rgb(94, 101, 115). At 1280 by 720 (the Salon column open on Discussion), `CLOSED("passed")` adds the same line and makes no `room-note`. A page whose first snapshot holds no vote and a `chat` history, and a page given `VOTE_ROOM` with `open_vote` `VOTE` then a snapshot with no vote after a reconnection, hold no `vote` line. When the mock sends `grid_solved` (seq 7) while `VOTE` is open, the banner leaves (spec 025); a `VoteClosed` with seq 8 and outcome `rejected` then adds its `vote` line.
- **AC-5** (new; refines spec 043 AC-26's vote part) (browser with mocked socket) Notes that waited during a vote give way to the vote's result. On `VOTE_ROOM` at 360 by 740 (the Salon closed), after `VOTE`, the mock sends two `chat_message` from `p2` (`un`, seq 7; `deux`, seq 8): no `room-note` shows while `vote-banner` is on the page. When it sends `VoteClosed(seq=9, vote_id=1, outcome="passed", yes_votes=2, eligible_voters=3)`, within 300 ms the banner is gone and exactly one `room-note` shows, reading `fr.json["vote.result.passed"]`; no note reading `Bob : deux` or `Bob : un` shows in the 3,500 ms that follow; `chat-unread` reads `2`.
- **AC-6** (new; settles the band on narrow windows, refines spec 026's band layout) (browser with mocked socket) The end band keeps « Voir le bilan » whole on its right and lets its text wrap. On `SOLVED`, in the desktop context: at 1280 by 720, `grid-status` holds `grid-status-text` then `recap-open`, `grid-status-text`'s text content is `fr.json["completion.solved"]` with its ✓ pictogram (computed `content` `"✓"`) before it, the left edge of `recap-open` is 10 px or more right of the right edge of `grid-status-text` (1 px), `recap-open`'s right edge is the band's content right edge (1 px), their vertical centres are within 1 px of each other, and the band is one line of text high (`grid-status-text` has one `getClientRects()` line box for its text). At 320 by 568: `recap-open` shows its whole text on one line (`scrollWidth <= clientWidth + 1`, computed `white-space` `nowrap`), lies inside `grid-status` and inside the window, its right edge on the band's content right edge (1 px), and is at least as wide as at 1280 by 720 (0.5 px); `grid-status-text` lies left of it, may take two lines, and keeps its whole text; spec 013 AC-6's checks hold (after a tap on (1, 0)). On a full-and-wrong FX-01 snapshot (spec 044's `FULL_WRONG`) at 320 by 568 in the desktop context, `grid-status` holds `grid-status-text` with `fr.json["completion.full_wrong"]` whole, no `recap-open`, and lies inside the window.
- **AC-7** (new; refines spec 028's dialog look) (browser with mocked socket and routes) The recap is a 440 px dialog on a wide window and a bottom sheet on a phone, over a darker scrim that covers the whole window. On `SOLVED` with the route answering `RECAP`, after a click on `recap-open`: at 1280 by 720, `recap` is a `DIALOG` with the `open` attribute, 440 px wide (1 px), centred in the window (1 px), with `border-radius` `12px` on each corner, padding `20px 22px`, `background-color` rgb(255, 255, 255), a shadow with offsets 0 and 20 px, blur 40 px, spread −16 px and colour 20, 24, 31 at alpha 0.5, and a `::backdrop` whose `background-color` has the channels 20, 24, 31 and alpha 0.38; at 568 by 320 (desktop, column layout) it is 440 px wide and lies inside the window, at most 288 px high, and `recap-close` can be scrolled into view inside it. At 360 by 740 (sheet layout), it is 360 px wide, its bottom on the window's bottom and its left on the window's left (1 px), its top at least 54 px below the window's top, with `border-top-left-radius` and `border-top-right-radius` `16px`, `border-bottom-left-radius` and `border-bottom-right-radius` `0px`, padding `14px 18px 18px`, the same `::backdrop`, and no element with `data-testid` `salon-handle` inside it; `elementFromPoint` at (180, 20), over the top bar, does not return `room-topbar` or one of its descendants while the dialog is open.
- **AC-8** (new; refines spec 028's contents) (browser with mocked socket and routes) The recap's parts come in the design's order with the design's type. On `SOLVED` with `RECAP`, after `recap-open`, at 1280 by 720 and at 360 by 740: the children of `recap` that show are, in document order, the `h2`, `recap-time`, `recap-lines`, `recap-players-heading`, `recap-players`, `recap-share-heading`, `recap-share-row`, `recap-close`, each the next one's top 14 px or more above (gap 14 px, 1 px). The `h2` reads `fr.json["recap.heading"]` with `font-size` 19.2 px, weight 700, colour rgb(27, 47, 85); `recap-time` reads `Temps : 12:34` with `font-size` 33.6 px, weight 700, `line-height` 33.6 px, colour rgb(27, 47, 85), `font-variant-numeric` `tabular-nums`; `recap-lines` holds `recap-checks` (`Vérifications : 2`), `recap-reveals` (`Révélations : 1 lettres et 1 mots`) and `recap-revealed` (`Lettres révélées : 5`) in that order, 4 px apart (1 px), each with `font-size` 15.2 px, weight 400, colour rgb(20, 24, 31); `recap-players-heading` and `recap-share-heading` read `fr.json["recap.players_heading"]` and `fr.json["recap.share_label"]` with `font-size` 12.48 px, weight 600, `text-transform` `uppercase`, letter spacing 0.8736 px (0.01 px) and colour rgb(94, 101, 115); `recap-close` reads `fr.json["recap.close"]` with the primary button's colours (spec 041 AC-10) and its right edge on the dialog's content right edge (1 px).
- **AC-9** (new; refines spec 028's player rows and AC-2's departed swatch) (browser with mocked socket and routes) Each row reads dot, name, « (vous) » and the counts, and a player who left has no dot. On `SOLVED` with `RECAP`, after `recap-open`: at 1280 by 720, `p1`'s row holds left to right `recap-colour`, `recap-name` (`Ana`), `recap-you` (`fr.json["roster.you"]`) and `recap-values`, whose text content is `8 lettres · 4 mots complétés`, holding `recap-letters` (`8 lettres`), `recap-sep` (`aria-hidden="true"`, no text node, pictogram `content` `"·"`) and `recap-words` (`4 mots complétés`); `recap-colour` is 10 by 10 px with `border-radius` `50%`, the `background-color` of `p1`'s `roster-colour` and a `box-shadow` of spread 1 px and colour 20, 24, 31 at alpha 0.55; `recap-name` 8 px right of it (1 px), weight 600, `font-size` 15.2 px, colour rgb(20, 24, 31); `recap-you` colour rgb(94, 101, 115); `recap-values` `font-size` 13.6 px, colour rgb(94, 101, 115), `font-variant-numeric` `tabular-nums`, its right edge on the list's right edge (1 px), its vertical centre within 1 px of `recap-name`'s; the two rows 8 px apart (1 px). At 360 by 740, each `recap-values` lies under its `recap-name` (its top at or below the name's bottom), its left edge 18 px right of the row's left edge (1 px). After a `player_left` of `p2` (reason `timed_out`) applied before opening, `p2`'s `recap-colour` has `data-colour=""`, is 10 px wide, and has a background with alpha 0, `background-image` `none` and `box-shadow` `none`, and `p2`'s `recap-name` has the same left edge as `p1`'s (1 px). After `open_menu` and a click on `access-switch` (spec 042), then `recap-open`, `p1`'s `recap-colour` has a background with alpha 0 and holds one `player-icon` of 12 by 12 px (0.5 px) with `data-icon="0"`.
- **AC-10** (new; refines spec 028's share link and AC-5's copy check) (browser with mocked socket and routes; clipboard in Chromium only) The share link sits in a URL box beside « Copier le lien », and a copy shows « Lien copié » under them. On `SOLVED` with `RECAP`, after `recap-open`: at 1280 by 720, `recap-share-row` holds `recap-share-link` then `recap-copy` on one line (vertical centres within 1 px, 8 px apart, 1 px), `recap-share-link`'s right edge 8 px left of `recap-copy`'s left edge and its left edge on the row's left edge (1 px), with `href` and text `<origin>/recap/tok_ABCDEFGHIJKLMNOP`, a `1px` `solid` rgb(154, 163, 178) border, `border-radius` `6px`, padding `8px 10px`, `font-size` 13.6 px, `white-space` `nowrap`, `overflow` `hidden` and `text-overflow` `ellipsis`; `recap-copy` reads `fr.json["room.share.copy"]`, has the secondary button's colours (spec 041 AC-10) and padding `8px 12px`. At 360 by 740, `recap-share-link` is as wide as `recap-share-row` (1 px) and `recap-copy` is under it, its left edge on the row's left edge, its top 8 px below the link's bottom (1 px). Chromium, with spec 011's clipboard permissions: a click on `recap-copy` puts that link in the clipboard; then `recap-copied` shows under `recap-share-row` (its top at or below the row's bottom), with `role="status"`, the text `fr.json["room.share.copied"]`, colour rgb(30, 123, 69), weight 500 and `font-size` 13.6 px, while `recap-copy` still reads `fr.json["room.share.copy"]`; `recap-copied` is gone 2,500 ms later. A `RECAP` with `share_path` null shows no `recap-share-heading` and no `recap-share-row`.
- **AC-11** (new; refines spec 028's loading and error look) (browser with mocked socket and routes) While the recap loads, and when it is not available, the dialog holds its title, one line and « Fermer ». On `SOLVED`, at 1280 by 720 and at 360 by 740, with the route held unanswered: after `recap-open`, `recap` has the frame of AC-7 and holds, in document order, the `h2`, `recap-loading` and `recap-close`; `recap-loading` reads `fr.json["recap.loading"]`, has `role="status"`, `font-size` 15.2 px and colour rgb(94, 101, 115); `recap-close` is primary, right-aligned as in AC-8. With the route answering 404, the dialog holds the `h2`, `recap-error` and `recap-close`; `recap-error` reads `fr.json["recap.error"]`, has `role="alert"`, `font-size` 13.6 px, weight 500, `line-height` 17.68 px and colour rgb(180, 35, 24).
- **AC-12** (new; refines spec 022's notes and muted box look) (browser with mocked socket) The chat notes are one muted line under the message box, and a muted player's box looks disabled. With `show_tab(page, "discussion")` at 360 by 740 and at 1280 by 720: with the input empty, `chat-send` is disabled with `background-color` rgb(238, 242, 248) and colour rgb(94, 101, 115); after the test types `salut` in `chat-input`, it has `background-color` rgb(230, 237, 249) and colour rgb(27, 47, 85). When the mock sends `player_muted` (seq 6, `p1`, `muted` true): `chat-muted` reads `fr.json["chat.muted"]` with `font-size` 13.6 px, weight 500, `line-height` 17.68 px and colour rgb(94, 101, 115), on one line, its left edge 12 px right of `salon`'s left edge (1 px), its top at or below the chat form's bottom; `chat-input` is disabled with `background-color` rgb(238, 242, 248) and colour rgb(94, 101, 115); `chat-send` has the disabled colours above; each text keeps a contrast of at least 4.5:1 against its background. Pacing: on a new page, after five messages `m1` to `m5` sent with `Enter` and answered by the mock (seq 6 to 10), `chat-wait` reads `fr.json["chat.wait"]` with the same look as `chat-muted`, and `chat-send` has the disabled colours.
- **AC-13** (new) (browser with mocked socket) The overlays meet spec 035's keyboard rules. On `VOTE_ROOM` after `VOTE` at 1280 by 720, keyboard only (spec 035's harness): after `tab_to` `grid`, `Escape` then `Shift+Tab` focuses `vote-no`, which has a `2px` `solid` rgb(27, 47, 85) outline with `outline-offset` `2px`, and its box grown by 4 px on each side (the ring) lies inside `vote-banner`'s box (1 px). On `SOLVED` with `RECAP`: `tab_to` `recap-open` gives it the same outline; `Enter` opens `recap`; `Tab` reaches `recap-share-link`, `recap-copy` and `recap-close`, each with the same outline, and no element outside `recap` gets the focus during 10 presses of `Tab`; `Escape` closes it and the focus is on `recap-open`.
- **AC-14** (new) (browser with mocked socket and routes; static) The overlays pass spec 035's scans, and `fr.json` holds this spec's keys. At 1280 by 720 and at 360 by 740, in these states: `VOTE_ROOM` with `VOTE` shown (buttons and countdown); the same after a click on `vote-yes`; a first snapshot holding `VOTE` (no countdown); a `room-note` showing `fr.json["vote.result.timed_out"]`; the stream holding a `vote` line; `SOLVED` with the band; `recap` loaded with `RECAP`; `recap` loading; `recap` unavailable; the Discussion tab while muted; spec 035's contrast scan (its AC-8) and language scan (its AC-9, with the nicknames, the share URL and the clue texts as test data) find no offending element. Also at 320 by 568, `SOLVED` with the band. Static: `web/src/i18n/fr.json` holds `vote.seconds_left` with the value `{count} s` and `vote.cast` with the value `Vote enregistré. En attente des autres joueurs…`, and still `vote.waiting` and the three `vote.result.*` keys with spec 025's values.

## Edge cases and errors

- A vote learned from a snapshot (AC-2): a page loaded or a player who joined during
  a vote does not know when it opened, so it shows no seconds and no bar rather than
  wrong ones. A reconnection that keeps the page keeps its own count.
- The page's clock (AC-2): the count starts when the page applies `vote_opened`, so
  it can read up to the network delay more than the server's; the server's
  `vote_closed` (20 to 21 seconds after the opening, spec 025) ends the banner, and
  « 0 s » may show for up to a second before it.
- A count that reaches 0 (AC-2): the banner stays at « 0 s » with an empty bar until
  `vote_closed`; the buttons stay enabled, since a ballot that arrives late is the
  server's to refuse (`no_open_vote`, spec 025).
- Voting at « 0 s » or offline (AC-3): spec 025's rules hold (buttons disabled while
  not joined); the line after a vote is the same whatever the count.
- The vote closes while I read the stream (AC-4): the stream gets the line and no
  note is made; a reader of the stream sees it in place.
- The vote closes while the focus is in the banner (AC-4): spec 025 decision 19
  holds, the focus goes to the `grid` and `vote-announcement` says the result.
- A vote closed after the grid is solved (AC-4): the banner left at the solve; the
  line and the note come at `vote_closed`, as for any vote.
- Many votes (AC-4): each closed vote adds one line; the stream keeps spec 013's 100
  event lines, so old vote lines go first, as other event lines do.
- A catch-up after an absence (AC-4): spec 034's catch-up adds no vote line, so a
  player who was away does not see how a vote ended; their reveals and checks still
  show (spec 034).
- The band on a narrow window (AC-6): at 320 px wide the text « ✓ Grille terminée,
  bravo ! » and « Voir le bilan » do not fit one line; the text takes a second line
  and the band grows by it, which spec 013 AC-6 allows (the keyboard is gone once
  solved, spec 044).
- The recap on a low window (AC-7): at 568 by 320 the dialog is at most 288 px high
  and scrolls inside; at 740 by 360 the same with 328 px.
- A player who left (AC-9): their row keeps its place, name and counts, with no dot,
  since the page no longer knows their colour (spec 043 does the same for a chat
  line of a player who left). A former player (spec 033) reads « Ancien joueur ».
- Long nicknames (AC-9): a name wraps on its line; `recap-values` goes under it.
- No share link (AC-10): a room made before spec 028 has none; the dialog shows no
  heading and no row for it.
- No clipboard (AC-10): nothing changes, as in the Joueurs tab (spec 043).
- The recap opened again (AC-11): each opening fetches again and shows the loading
  line first (spec 028).
- Both chat notes (AC-12): `chat-muted` wins, as spec 022 says.

## Out of scope

- A tally of ballots while a vote is open (spec 039 has no ballot event), and the
  server's opening time in the snapshot (a protocol change, Open question 2).
- A stream line or a note when a vote opens: the banner is its place.
- An automatic opening of the recap at the solve (spec 028 decision 11), animations,
  sounds, a celebration.
- Dragging the recap sheet; a grab handle.
- The account page, the shared recap page, the operator page and the states of the
  other screens (spec 048; the catalogue's and the opening room's are spec 046's).
- The Auteurs legend and spec 019's band (spec 045), whose hatching this spec no
  longer uses in the recap.
- Screenshot comparison with the screens sheet (`_design.md` section 13).

## Work packages

None: one pull request.

## Decisions

Decided by the human on 2026-10-22 (screens sheet P6, P10, P16; `_design.md` section
15), each already part of the spec above: the muted line after a vote and the
requester's waiting line (P6); the result as a 3-second note when the banner goes,
and a line in the stream (P6); the recap's loading and unavailable states inside its
sheet or dialog (P10); « Lien copié » as a line under the recap's link, the button
keeping its label (P16).

Proposed by the spec writer, each already part of the spec above:

1. The banner leaves when the vote closes and never shows a result (Open question
   1). P6 says the result "comes as a 3-second note when the banner goes"; keeping
   spec 025's 3-second result in the banner as well would show the same words twice,
   for 6 seconds, in two places. One place for an open vote, the note and the stream
   for how it ended, as for every other room event.
2. The countdown is the page's own, from the moment it applied `vote_opened`, and is
   absent for a vote known only from a snapshot (Open question 2). The snapshot
   carries no opening time and Phase 7 changes no protocol; an absent count is never
   wrong, a guessed one could be.
3. The bar moves in steps of at most 250 ms with no transition, so it needs no rule
   for reduced motion: it never slides.
4. A departed player's recap row has no dot (Open question 3). Spec 028 hatched their
   swatch as spec 019 hatched a departed author's band; spec 045 removes that band,
   `_design.md` has no hatch, and spec 043 gives a chat line of a departed player no
   dot. No dot is the one rule for every list.
5. The vote's stream line is muted for every outcome. Green means "done" and is kept
   for checks that found no error; a passed vote is followed by its own check or
   reveal line, which carries the colour.
6. The vote's line does not light `salon-dot`: it is by no player, and every page
   showed the banner while the vote was open.
7. The band's text wraps and « Voir le bilan » never does, so the action stays whole
   and in one place on the narrowest window (320 px).
8. The recap keeps spec 043's layout rule for its frame (dialog in the column layout,
   bottom sheet in the sheet layout), with its own scrim over the whole window
   (`_design.md` section 9), so the dialog never depends on a width of its own.
9. In the column layout the share link and « Copier le lien » share a row, as the
   screens sheet draws them; in the sheet layout the button goes under the link, so
   the URL keeps the full width of a phone.

Decided by the human on 2026-10-22, with the spec's approval (these were the Open
questions, answered with their recommended answer; the text above already follows
them). The number in brackets is the question's number, which the text above cites:

10. (Open question 1.) The end of a vote. Options: (a) the banner leaves at
    `vote_closed`, the result is a note and a stream line; (b) the banner shows the
    result for 3 seconds (spec 025), then the note follows for 3 more. Answer: (a)
    (Decision 1).
11. (Open question 2.) The countdown of a vote known only from a snapshot (a reload,
    a late joiner). Options: (a) no seconds and no bar for that vote; (b) a new
    protocol field giving the time left in the snapshot's `open_vote` (a change of
    spec 039, outside Phase 7); (c) no countdown at all, for every vote (the
    design's seconds and bar go). Answer: (a) (Decision 2).
12. (Open question 3.) A departed player in the recap. Options: (a) no dot, the slot
    kept so names align; (b) keep spec 028's grey hatching (a pattern `_design.md`
    does not have); (c) a neutral grey dot (a colour colour-blind players read as a
    player's, spec 028 decision 13). Answer: (a) (Decision 4).
13. (Open question 4.) The colour of the vote's stream line. Options: muted for every
    outcome; green for a passed vote. Answer: muted (Decision 5).

## Open questions

None left (all answered with the approval of 2026-10-22).
