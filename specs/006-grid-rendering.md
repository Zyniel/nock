---
id: "006"
title: Grid rendering
status: done
---

# 006 - Grid rendering

Epic E2 Solo solving (US-2.1) · Release: MVP · Epic depends on: E1
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The room
page, its WebSocket, i18n and the test harness are those of spec 040; the grid
view is `GridView` of spec 039.

(Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells
(`_design.md` section 6): arrows are drawn in the word's first letter cell, the
separator and the clue text follow the design, and one clue size serves every clue
cell. AC-2 and the edge case "Two clues pointing right" change, so the test-writer
updates their tests before the implementer runs. The other criteria do not
change.)

## Goal

As a player, I want the grid and its clues readable on my phone, so that I can play without a desktop.

A solo game is a room of one, so nothing here is rewritten when other players join.

## Public interface

No new Python name and no new protocol message. The room page draws the `grid` of
the latest snapshot (spec 040 keeps it); this spec makes the client keep every
cell of `GridView`, not only its size.

### FX-02

The test-writer creates `tests/fixtures/fx02.json`, an original full-size grid in
the spec 002 format, and a `fx02_text` fixture in `tests/conftest.py` beside
`fx01_text`. It must:

- have `width` 13 and `height` 17;
- pass `import_grid` (spec 003) without error;
- use each of the four arrows at least once and hold at least three two-clue cells;
- hold at least one row and one column where a clue cell sits between two letter
  cells (used by spec 009 AC-1);
- hold clue texts of 1 to 32 characters, at least one of 24 characters or more
  inside a two-clue cell;
- be original: no clue or answer copied from a published grid.

### Room page additions (client)

Shown once the room page has a snapshot (`data-status="joined"`, and kept after a
later `closed`):

- `data-testid="grid-viewport"`: the scroll container of the grid. Panning scrolls
  it (`scrollLeft`, `scrollTop`). Attributes:

  | Attribute | Value |
  | --- | --- |
  | `data-zoom` | current zoom, a decimal with at most 2 decimals, for example `1` or `2.35` |
  | `data-zoom-min` | `1` |
  | `data-zoom-max` | the largest zoom, a decimal greater than 1 |

  Zoom 1 is the starting zoom: the whole grid fits inside the viewport's client
  area, in width and in height. A two-finger pinch on the viewport multiplies the zoom by the ratio
  of the finger distances (end over start), clamped to `[data-zoom-min, data-zoom-max]`.
  The implementer picks `data-zoom-max` so that AC-1 holds on a 360 px screen.
- Inside it, `data-testid="grid"` with `data-width` and `data-height` (decimal),
  holding one `data-testid="cell"` per grid cell, laid out as a `height` by
  `width` table of equal squares, (0, 0) top left. Each cell has `data-row`,
  `data-column` and `data-type` (`letter`, `clue` or `empty`).
- A letter cell also has `data-letter` (`""` or the letter `A` to `Z` of the
  snapshot) and `data-locked` (`true` or `false`), and its visible text is that
  letter (nothing when empty).
- A clue cell holds one `data-testid="clue"` per clue, in `clues` order, with
  `data-clue-index` (`0` or `1`) and `data-arrow` (the `Arrow` value). Each clue
  holds `data-testid="clue-text"`, whose text is exactly the clue text. Each clue
  has one `data-testid="clue-arrow"` with `data-arrow` (same value) and
  `data-side`: `right` for `right` and `right_then_down` (the word starts at
  (r, c + 1)), `bottom` for `down` and `down_then_right` (the word starts at
  (r + 1, c)). The arrow is a child of the word's first letter cell, drawn
  against the side that cell shares with the clue cell, with `data-clue-row`,
  `data-clue-column` and `data-clue-index` naming its clue; it is
  `aria-hidden="true"` and holds no text. Its look and its place in that cell are
  spec 042's. (Note from the lead, 2026-10-22: refined by spec 042, the design's
  grid cells: the arrow was a child of its `clue` and drawn in the clue cell, on
  that side; the design draws it in the letter cell, as printed grids do.)
- A clue cell with two clues stacks them, clue 0 on top, and holds one
  `data-testid="clue-separator"` between them: a horizontal line at least 1 px
  thick (its height, or its top or bottom border width, is 1 px or more) with a
  colour different from the cell background. (Note from the lead, 2026-10-22:
  spec 042 gives its exact look, clue ink at 55 % opacity inset 14 % on each
  side; this rule still holds.)
- An empty cell holds nothing.
- The grid element has `aria-label` `t("grid.label")`.

Messages sent: none (selection and input belong to specs 007 to 009).

New `fr.json` key:

| Key | Value |
| --- | --- |
| `grid.label` | `Grille` |

### Test harness

- "Browser with live server": the `live_server` and `room_registry` fixtures of
  spec 040; the test registers a room on FX-01 or FX-02 and opens `/r/<code>`.
- "Browser with mocked socket": spec 040's `page.route_web_socket` mock on
  `/r/ABC123`, sending a `Snapshot` built from `grid_view(fx01_grid)` with chosen
  cells replaced (`model_copy(update=...)`).
- Engines: every browser criterion runs in Chromium, Firefox and WebKit
  (`specs/_architecture.md`; Edge is covered by Chromium, Safari by WebKit; CI runs
  all three, a local run Chromium and WebKit). The only Chromium-only checks of
  this spec are the pinch and pan steps of AC-1 and the checks made after them,
  because they drive the page through Chrome DevTools Protocol touch input, which
  Firefox and WebKit do not have; the test that holds them is marked
  `@pytest.mark.only_browser("chromium")`. Every other check, including the
  at-load part of AC-1, runs in all three engines.
- Phone: a browser context with `viewport={"width": 360, "height": 740}`,
  `has_touch=True`, `is_mobile=True`, `device_scale_factor=2`. Playwright does not
  support `is_mobile` in Firefox, so under Firefox the context leaves it out (the
  test reads the `browser_name` fixture); the other options stay.
- Pinch (Chromium only): a CDP session (`page.context.new_cdp_session(page)`) sends
  `Input.dispatchTouchEvent`: `touchStart` with two points 40 px apart around the
  viewport's centre, ten `touchMove` steps moving them apart symmetrically to
  300 px, then `touchEnd`. A pinch in is the same backwards.
- Pan (Chromium only): `Input.synthesizeScrollGesture` on the viewport's centre with
  `gestureSourceType: "touch"` and `xDistance`/`yDistance` of -200.
- "Cut off" check on a `clue-text` element: `scrollWidth <= clientWidth + 1`,
  `scrollHeight <= clientHeight + 1`, its bounding box inside its clue cell's box
  (1 px tolerance), and computed `visibility` `visible`.
- Positions are read with `locator.bounding_box()`.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-2.1.1) (browser with live server, phone emulation; at-load part in all three engines, gesture part Chromium only) On a 360 px wide screen, FX-02 can be panned and pinch-zoomed, and no clue text is cut off at full zoom. With a room on FX-02 opened in the phone context: at load `data-zoom` equals `data-zoom-min` and the grid's box is no wider than the viewport's client width (all three engines). Then, in Chromium only (CDP touch input, see "Test harness"): one pinch out raises `data-zoom`; pinching out again (at most five pinches) reaches `data-zoom == data-zoom-max`; the grid is then wider than the viewport, and a pan raises the viewport's `scrollLeft` and `scrollTop` above 0; every `clue-text` of the grid passes the "cut off" check; a pinch in lowers `data-zoom`.
- **AC-2** (AC-2.1.2) (browser with live server) Each clue draws its arrow on the side of its word's first letter cell. On FX-01 in a 1280 by 800 window, for each of the 8 clues: the one `clue-arrow` whose `data-clue-row`, `data-clue-column` and `data-clue-index` name the clue is a child of the word's first letter cell, has the clue's `data-arrow` and the `data-side` of the table above, and its box centre lies on that side of the clue cell (Note from the lead, 2026-10-22: refined by spec 042, the design's grid cells: the arrow is found in the letter cell by its clue attributes, no longer inside its `clue`; the box rule below is unchanged and spec 042's places meet it): for `right`, centre x at least the cell's centre x plus a quarter of the cell width and at most the cell's right edge plus half a cell width, centre y within the cell's top and bottom; for `bottom`, the same with x and y swapped. At (0, 0), clue 0 (`down_then_right`) has side `bottom` and clue 1 (`right_then_down`) side `right`.
- **AC-3** (AC-2.1.3) (browser with live server) A cell with two clues shows both, separated by a line; FX-01 shows this at (0,0). The cell (0, 0) holds two `clue` elements whose `clue-text` read `Passoire fine` and `De la marine`, in that order, and one `clue-separator` that meets the line rule above and whose box lies between the two texts (its centre y at or below the bottom of clue 0's text and at or above the top of clue 1's text). Single-clue cells (0, 2) and (2, 0) hold one `clue` and no `clue-separator`.
- **AC-4** (AC-2.1.4) (browser with live server) A new game on FX-01 renders 7 clue cells and 18 empty letter cells. A fresh room on FX-01 shows 25 `cell` elements: 7 with `data-type="clue"`, 18 with `data-type="letter"`, all 18 with `data-letter=""`, `data-locked="false"` and no visible text, and none with `data-type="empty"`; the grid has `data-width="5"` and `data-height="5"`.
- **AC-5** (AC-2.1.5) (browser with live server, viewport emulation in Chromium, Firefox and WebKit) The game is a responsive web app with no native app and no install. Every screen works from 320 px wide up to desktop, in portrait and landscape, on current Chrome, Safari, Firefox and Edge. In each of the three engines (Chromium standing for Chrome and Edge, WebKit for Safari), for each window size 320x568, 568x320, 360x740, 740x360, 768x1024, 1024x768, 1280x800 and 1920x1080, and for each page `/` and `/r/<code>` (a room on FX-02): `document.documentElement.scrollWidth <= window.innerWidth` (no horizontal page scroll); on the room page, the `grid-viewport` box lies inside the window horizontally, is at least 100 px wide and 100 px high, and at least one `cell` is inside the window.
- **AC-6** (new) (browser with mocked socket) The grid shows the letters and locks of the snapshot. Given a FX-01 snapshot whose cell (1, 0) has `letter="T"` and whose cell (1, 2) has `letter="M"`, `locked=True`, the cell (1, 0) has `data-letter="T"` and the text `T`, the cell (1, 2) has `data-letter="M"`, `data-locked="true"` and the text `M`, and the cell (1, 1) has `data-letter=""`. A second snapshot where (1, 0) is empty makes it `data-letter=""`.
- **AC-7** (new) (browser with live server) The room page fits the window at every size of AC-5. On a fresh FX-01 room, at each window size of AC-5 and at zoom 1, the `grid-viewport` box lies inside the window (top >= 0, bottom <= window height), the page has no vertical scroll (`document.documentElement.scrollHeight <= window.innerHeight`), and every cell of the grid is inside the window.
- **AC-8** (new) (browser with mocked socket) A snapshot whose grid is malformed is ignored and the page keeps working. With FX-01's snapshot shown, when the mock sends a second snapshot with a higher `seq` whose `grid.cells` holds a duplicate position, a position outside `width` x `height`, or a number of cells different from `width` x `height`, then the page shows no error, keeps the previous grid (same cells, letters and `data-seq`), and a valid snapshot sent next is shown.

## Edge cases and errors

- Before the first snapshot (AC-4): no `grid-viewport` exists; the page shows its
  status as in spec 040. A room that is not found (4404) never shows a grid.
- After the socket closes (AC-6): the last grid stays on screen.
- Two clues pointing right from one cell (AC-2): a cell holding a `right` and a
  `right_then_down` clue (both start at (r, c + 1)) draws both arrows on the right
  side, the ↴ (`right_then_down`) within the top half of the cell and the →
  (`right`) within the bottom half, whatever their clue indexes; two `right` clues
  put clue 0's in the top half and clue 1's in the bottom half. (Note from the
  lead, 2026-10-22: refined by spec 042, the design's grid cells, whose collision
  rule gives the → the low slot; it read "clue 0's within the top half of the cell
  and clue 1's within the bottom half".)
- Long clue text (AC-1): the text wraps on several lines; it is never ended with
  an ellipsis or clipped at full zoom. At zoom 1 on a phone, small text is
  allowed. (Note from the lead, 2026-10-22: refined by spec 042, the design's grid
  cells: "and may use a smaller font inside two-clue cells" is gone, one clue size
  serves every clue cell, and the implementer may raise `data-zoom-max` to keep
  this rule (decision 3).)
- Zoom limits (AC-1): a pinch beyond the limits leaves `data-zoom` at
  `data-zoom-min` or `data-zoom-max`; a one-finger drag never changes the zoom.
- Zoom 1 (AC-1, AC-5): since the whole grid fits in the viewport, at 1280x800 and
  above FX-01 and FX-02 need no pan, and the grid box lies inside the viewport's
  box. On a short landscape phone the cells are small at zoom 1; pinching enlarges
  them.
- Unknown cell type or malformed grid in a snapshot frame: the frame is ignored as
  in spec 040 (the server never sends one).
- Letters outside A to Z in a snapshot cannot reach the client (spec 039 `Letter`).

## Out of scope

- Printing and offline play (epic E2).
- Word selection and direction: spec 007.
- Letter entry: spec 008.
- Keyboard and navigation: spec 009.
- Instant solo start: spec 010.
- Applying `letter_changed` and `cell_locked` events to the grid (specs 015, 016),
  pencil, author colours, wrong and revealed marks (specs 019, 020, 023, 024).
- Zoom on desktop beyond the browser's own zoom (no buttons, no Ctrl+wheel).
- Screen reader structure of the grid (spec 035).
- Rendering speed on FX-02 (spec 036).

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written,
except item 1 (the human chose three engines) and item 2 (reworded to match).
Each one is already part of the spec above.

1. Browsers. "Current Chrome, Safari, Firefox and Edge". Options: Chromium only;
   or add Firefox and WebKit runs. Decision (human): browser tests run in
   Chromium, Firefox and WebKit (CI runs all three; a local run Chromium and
   WebKit while Windows blocks Firefox), and every browser criterion of this spec
   must pass in all three. Edge is covered by Chromium, Safari by WebKit. A check
   that needs a Chromium-only feature is marked
   `@pytest.mark.only_browser("chromium")`; here that is only the gesture part of
   AC-1 (item 2). In Firefox the phone context leaves out `is_mobile`, which
   Playwright does not support there. Not covered: real devices (iOS Safari on a
   phone, Android Chrome on a phone).
2. Pinch and pan. Playwright has no pinch API, and real fingers on real phones
   cannot run in the gate. Pick: an app-controlled zoom exposed as `data-zoom`,
   driven by touch events and tested with CDP `Input.dispatchTouchEvent` (pinch) and
   `Input.synthesizeScrollGesture` (pan) in Chromium's touch emulation. CDP exists
   only in Chromium, so the pinch, the pan and the full-zoom "cut off" checks of
   AC-1 are Chromium-only (`only_browser("chromium")`); the at-load checks of AC-1
   run in all three engines. Not covered: iOS Safari gestures, gestures in Firefox
   and WebKit, the browser's own page zoom, and inertia.
3. "Full zoom". Pick: `data-zoom-max`, chosen by the implementer so that no clue
   text is cut off on 360 px; zoom 1 fits the whole grid. No minimum font size is
   set here; readability thresholds belong to spec 035.
4. "No clue text cut off" made measurable: no overflow of `clue-text`, its box
   inside its cell, visible. Pick: as written.
5. FX-02 size "13 by 17". Pick: `width` 13, `height` 17 (portrait, suits phones).
   Its clue texts are capped at 32 characters, one of 24 or more in a two-clue
   cell, so the "cut off" check is demanding but reachable.
6. Responsive check. Pick: the eight window sizes of AC-5, checking no horizontal
   page scroll and a usable grid viewport (100 by 100 px, threshold proposed here).
   "No native app and no install" holds by construction (a web page) and has no
   test of its own.
7. Arrow placement. Options: inside the clue cell, on the shared border, or inside
   the letter cell. Pick: the test accepts any position from the outer quarter of
   the clue cell to the near half of the letter cell, on the correct side. (Note
   from the lead, 2026-10-22: spec 042 settles the place: inside the letter cell,
   against the shared side, which this range accepts.)
8. Locked cells are shown (`data-locked`) here because the snapshot already holds
   them; their look is the implementer's choice until spec 016.

Added after the review, decided by the lead on 2026-10-10 under the human's
instruction to take technical decisions:
9. The room page fits the window: the grid area is sized from the space really
   left by the page, with no vertical page scroll (AC-7).
10. A malformed grid in a snapshot (duplicate or out-of-range position, wrong cell
    count) is ignored like any other malformed frame (AC-8).

## Open questions

None.
