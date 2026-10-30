# Web client review

Senior code review of `web/` (the Svelte 5 + TypeScript client: 81 files and
about 17,200 lines under `web/src`) on `feat/b-039-frontend-review`, cut
from `origin/main` at `4d1165d`. Every file was read in full, in three parts: the
session and data layer (`roomSession.ts` and the plain modules), the room page
(`RoomPage.svelte` and its components), and the grid with the other pages
(`GridViewport.svelte`, catalogue, account, ops, share). The findings below were
checked against the code, and against the domain specs where a spec decides what
is right. The focus ring of M4 was checked on screenshots in Chromium and WebKit.

## Executive summary

The client is careful work. There is no `{@html}`, no `innerHTML` and no `any`
anywhere; every `href` is a same-origin path built from a code the route regex
checked; the ops token lives in `sessionStorage` and travels only in a header;
the sign-in token is dropped from the URL before it is used. Every interface
string goes through `t()`, `aria-label`s included, and every key of `fr.json` is
used. `roomSession.ts` is a defensive reducer: each server field is checked
before use, unknown messages are ignored, and the sequence buffer follows
`client/shell.md` rule 4 exactly. The grid implements the ARIA contract of
`product.md` rule 17 as written, and letter entry handles composition, dead keys
and accent folding. Timers and listeners are cleaned up almost everywhere, and
the comments say why, citing their spec. svelte-check and tsc pass with
0 errors; the build is one 238 KB script (75 KB gzipped).

The weak side is **what happens around a reconnection**, and it has one cause:
the socket, heartbeat, back-off, edit queue and join plan are closures inside
`RoomPage.svelte` (2,720 lines, 53 `$state`, 69 `$derived`, 22 `$effect`), where
no test can reach them but a browser test. Most of the Medium findings come from
there:

- an undo, check or reveal pressed while queued edits are being resent overtakes
  them, so Ctrl+Z can erase the wrong letter for everyone (M1, against
  `platform/server.md` rule 9);
- a browser that refuses storage is stuck after its first reconnection (M2);
- after a reconnection the others no longer see the player's cursor (M3).

One finding is about security: **signing out does not end what the sign-in
brought to the device** (H1). The account's seat tokens are copied into
`localStorage` and stay there after « Se déconnecter » or « Supprimer mon
compte », so the next person on a shared computer can take the account's seats.

Two findings break a product baseline today: the grid's focus ring is painted
under the letter cells (M4, rule 14; confirmed in Chromium and WebKit, and the
test only reads the computed style), and every frame received, the pong
included, re-runs the template of every letter cell (M5, on the path of rules 23
and 24).

| Severity | Count |
| --- | --- |
| Critical | 0 |
| High | 1 |
| Medium | 11 |
| Low | 27 |

Each finding ends with its fix strategy: what changes, its size (S, M, L), and
whether a spec changes first. The fixes are grouped into proposed items at the
end.

## Findings

### High

#### H1. Sign-out and account deletion leave the account's seats on the device

`storeMissingIdentities` (`web/src/lib/account.ts:192`) writes an identity
(`player_id`, `resume_token`, nickname) into `localStorage` for every room of the
account that the device has none for. It runs after a sign-in and on every
catalogue load while signed in (`web/src/lib/CataloguePage.svelte:105`).
Neither `leave` nor `confirmDeletion` (`web/src/lib/AccountPage.svelte:103`,
`:112`) removes anything, and nothing ever prunes `nock.identity.*`,
`nock.room.*` or `nock.history`.

Failure: Ana signs in on a library computer, so every seat of her account is
copied to the browser. She clicks « Se déconnecter » and leaves. The next person
opens `/`: « Mes salons » lists her rooms and « Reprendre » takes her seat, with
her nickname and colour; they can type and chat as her and, where she is host,
remove players or lock the room. After « Supprimer mon compte » the seats stay
too (as `--`, `account/account.md` rule 18), and `nock.history` keeps her
team-mates' nicknames on the device.

The device's own seats, those it took before signing in, are expected to stay:
they are how a guest comes back. The defect is that the sign-in widens what the
device holds, and the sign-out does not narrow it back.

Fix strategy (M, spec change first):

- mark what the account brought: a `from_account` flag in the identity record,
  or a `nock.account_rooms` list of codes written by `storeMissingIdentities`;
- on a 204 from sign-out or deletion, remove those identities, their
  `nock.room.*` records and the account-sourced history, then show the state;
- optionally, forget an identity whose room the summaries no longer return.
- Spec: `account/account.md` rules 13 and 17 say what sign-out and deletion
  forget on the device; the line of `client/hud.md` « Out of scope » about
  forgetting identities is reworded.

### Medium

#### M1. Undo, check and reveal overtake the edits being resent

Only edits go through the queue: `sendEdit` (`web/src/lib/RoomPage.svelte:1718`)
queues behind a running resend, while `onUndo` (`:868`), `onCheck` (`:876`) and
the reveal (`:934`) call `send` directly, which sends at once when the socket is
open and drops the message otherwise (`:552`). After a reconnection,
`resendPendingEdits` (`:1839`) sends the pending edits one every 100 ms.

Failure: offline, the player types A, B, C. On the new snapshot A goes at 0 ms,
B at 100 ms, C at 200 ms; Ctrl+Z at 50 ms reaches the server before B and
undoes A. C, the letter meant, stays; A disappears for everyone. A check pressed
in the same window checks the old letter, strikes it wrong and spends a check.
Between the socket's opening and its snapshot the undo gets `not_joined` and is
lost. `platform/server.md` rule 9 says « An undo made while edits are pending is
sent after them »; the comment at `:867` says the same and is wrong.

Fix strategy (S): one `sendAfterEdits(message)`: while not synced, keep the
message in a list that `resendPendingEdits` appends after the resent edits;
while the resend runs, push it on `editQueue`; otherwise send it. Use it for
undo, check and reveal. Spec: none for undo (rule 9 already says it; a test of
the reconnection case is missing); `gameplay/hints.md` gains the same ordering
rule for check and reveal.

#### M2. With storage refused, the page cannot rejoin after a reconnection

`joinOnOpen` (`web/src/lib/RoomPage.svelte:1850`) asks `planAutomaticJoin`
(`web/src/lib/joinRules.ts:96`), which reads the identity from `localStorage`
only; `writeIdentity` fails silently when storage throws
(`web/src/lib/storage.ts:34`).

Failure: a browser that blocks site data joins through the form and plays. At
the first network drop the new socket opens, no identity is found, the room was
not created here, so the status becomes `nickname`. A snapshot already exists,
so `isEntryPage` (`:417`) is false and no form shows: the band says « Choisissez
un pseudo pour entrer. » and no join is ever sent. The heartbeat still gets its
pongs, so nothing times out; typed letters stay pending until a reload, which
then takes a new seat. A full quota or storage cleared from another tab gives
the same.

Fix strategy (S): keep the identity of the last snapshot in memory (set in
`rememberJoin`) and have `joinOnOpen` use it first; storage is read only before
the first snapshot. Spec: `lobby/joining.md` rule 8, a page that has joined
rejoins with the identity it holds, as `social/catch-up.md` rule 1 already does
for the seen seq.

#### M3. After a reconnection the player's selection is not sent again

The server clears a player's selection when they disconnect and tells the
others (`src/nock/room.py:1146`). On the reconnection snapshot the page keeps
its selection (`web/src/lib/RoomPage.svelte:1881` restores one only on the
first snapshot), and `select()` sends nothing for an unchanged selection.

Failure: a phone loses the network for a second. Its page still shows its
word, but the others see no cursor, no tint and no clue in its Joueurs row
until the player moves. A player thinking over a clue stays invisible.

Fix strategy (S): when a snapshot replaces an earlier one and a selection is
kept (checked against the new words), send `select_cell` for it before the
resend. Spec: `social/presence.md` or `platform/realtime.md` rule 22 says a
reconnection sends the kept selection again; a test.

#### M4. The grid's focus ring is painted under the letter cells

`.grid:focus-visible` has `outline-offset: -3px`
(`web/src/lib/GridViewport.svelte:1195`), so the ring lies over the edge cells;
the letter cells are positioned stacking contexts with an opaque background
(`:896`), which Chromium and WebKit paint after the grid's outline.

Checked on screenshots of a 14 by 9 grid focused from the keyboard: in both
Chromium and WebKit the ring shows only where a clue cell touches the edge
(their top and left edges, the right edge of « Prend sur lui ») and is hidden
along every letter cell. `product.md` rule 14 asks for a visible 2 px ring on
every focusable element. `tests/test_spec_041_ac07_ac08_focus_ring.py` reads the
computed style only, so the gate cannot see it. The comment at `:987` already
records the same painting order for the cell outline.

Fix strategy (M): draw the ring on an `aria-hidden` overlay painted after the
cells (a positioned sibling with `inset: 0`, `pointer-events: none`, outlined
while the grid has `:focus-visible`), keep the grid's own outline for the style
check, and add a pixel check along the right and bottom edges in Chromium and
WebKit. Spec: none for rule 14; `_design/foundation.md` « Focus » if the ring
is no longer the element's own outline.

#### M5. Every frame re-runs the template of every letter cell

`receiveFrame` assigns `session.cursors = nextCursors(...)`
(`web/src/lib/roomSession.ts:1197`), a new array of new objects on every frame,
the 2-second pong included. `remoteSelections` (`RoomPage.svelte:354`) derives
from it, and each letter cell calls `cursorsOn` and `tintsOn`
(`GridViewport.svelte:171`), which return a fresh array, empty or not, so no
derived value stops the update. The compiled component reads them inside each
cell's template effect.

Failure: with 8 players at 2 letters a second (rule 24), about 16 full-grid
passes a second on FX-02: per cell, attribute compares, a class and a style
diff and a keyed each. On the 4x-throttled phone this competes with the 50 ms
local echo of rule 23. Not measured; the gate has no 8-player client profile.

Fix strategy (S): at the source, `nextCursors` returns `before` when nothing
moved; in the grid, one derived `Map` from cell to `{cursors, tint}` built per
change, with shared empty constants, so unchanged cells stop at their derived;
the same for flashes and caught-up cells. Spec: none.

#### M6. A zoomed grid never scrolls to keep the selection in view

The selection moves by `onSelect` only; `aria-activedescendant` changes, and no
engine scrolls an active descendant into view. Outside the pinch and pan code
(`GridViewport.svelte:544`, `:577`) nothing sets the viewport's scroll.

Failure: on a 360 px phone the player pinches to read a clue
(`gameplay/board.md` rule 3) and types a 7-letter word with the in-app keyboard:
letters 6 and 7 land off-screen. Tab and the arrows can select a word that is
wholly off-screen.

Fix strategy (S-M): an effect on the selected cell and the cell size, active
while zoomed, that scrolls the viewport the least amount that shows the cell
with a margin; a tap changes nothing since the cell is in view. Spec:
`gameplay/board.md` rule 3, « while zoomed, a change of selection scrolls the
grid the least needed to show the selected cell ».

#### M7. In the sheet layout, focus can move under the Salon sheet and the scrim

The Salon sheet is fixed, opaque and 62 % of the window
(`web/src/lib/Salon.svelte:120`, `:209`); the play area comes before it in
document order, and neither the sheet nor an open menu contains the focus or
closes when it leaves (`RoomPopover.svelte:115`).

Failure: in the sheet, Shift+Tab from « Discussion » goes to the clue bar's
buttons hidden under the sheet, so the focus ring is not visible (rule 14).
From the last item of an open Aide menu, Tab goes to the grid under the scrim
while the menu stays open, and the player types into a covered grid.

Fix strategy (S-M): decide in the spec, then either close the overlay when the
focus leaves it (`focusout` with a `relatedTarget` outside, closing without
moving the focus) or wrap Tab inside it. Spec: `client/hud.md` rule 12.

#### M8. The four room sheets each reimplement the dialog, and the copies differ

`HostSettings.svelte`, `AccountDialog.svelte`, `RecapDialog.svelte` and
`RoomGoneDialog.svelte` each open a native `<dialog>`, handle the backdrop and
trap Tab by hand. The traps differ: AccountDialog counts `input:not(:disabled)`,
RecapDialog does not, and HostSettings has no trap at all, though the others say
the focus must not leave for the browser's own controls.

Failure: in the host sheet, Tab from « Enregistrer » leaves for the address
bar; the recap and account sheets wrap. Each fix has to be made in four places.

Fix strategy (M): one `RoomSheet.svelte` (layout, `labelledBy`, backdrop and
cancel policy, `onClosed`, `open()` and `close()`) with one Tab trap on a full
tabbable selector; the four sheets use it. It is also where L8 and L17 are
fixed once. Spec: optional, `client/hud.md` rule 13 states Tab containment for
every room sheet.

#### M9. Status messages are inserted already holding their text

The connection band, the grid status, the undo note, the Joueurs status and the
recap status are polite live regions that appear with their text already in
them (`RoomPage.svelte:2131`, `:2304`; `RoomNote.svelte:75`;
`PlayersPanel.svelte:155`; `RecapDialog.svelte:220`). Screen readers often stay
silent for a region that is created full. The vote announcement does it right:
it is always in the page and only its text changes (`RoomPage.svelte:2173`).

Failure (plausible, depends on the screen reader): NVDA or JAWS with Chromium
do not say « Hors ligne », « Grille terminée » or « Rien à annuler », although
`platform/realtime.md` rule 20 says the band is announced as a status.

Fix strategy (M): one persistent, visually hidden `role="status"` region in the
room page with an `announce(text)` function passed down; the visible elements
lose their role. Spec: none.

#### M10. No caching headers for the client: a deploy can leave a blank page

`_index_response` (`src/nock/server.py:711`) and `serve_asset` (`:1408`) answer
with a bare `FileResponse`: no `Cache-Control` on `index.html` nor on the hashed
files of `/assets/`, and the `Caddyfile` adds none. Browsers then apply
heuristic freshness (a share of the time since `Last-Modified`).

Failure: a browser keeps a days-old `index.html` fresh after a deploy; it asks
for `/assets/index-<old hash>.js`, which the new build no longer has: 404 and a
blank page until the cache expires. Conversely, the hashed assets, which never
change, are revalidated on repeat visits.

Fix strategy (S): `Cache-Control: no-cache` on every page route's `index.html`;
`public, max-age=31536000, immutable` on `/assets/*`. It belongs with the
headers of B-034 (HTTP edge), which can take it. Spec: `platform/server.md`
« Serving the client ».

#### M11. The connection state machine lives inside a 2,720-line component

`RoomPage.svelte` holds five concerns: the transport (socket, heartbeat,
back-off, edit queue, join plan, about 330 lines), the game commands, the view
state (overlays, notes, vote banner, focus), the layout arithmetic and the
device storage. `session` has two writers, the `roomSession.ts` functions and
the page. M1, M2, M3, L1, L2, L6 and L11 all come from the transport part, which
no test can reach but a browser test.

Fix strategy (L, a pure refactor in safe steps, see « Structure » below): first
a `roomConnection.ts` with an injected socket factory and clock, the only writer
of `session.status`, exposing `edit()`, `command(message, {afterEdits})` and
`dispose()`; then the leaf components. Spec: none; its own item.

### Low

Session and connection:

- **L1. After a final close the grid still takes letters.** After a 4001, a
  removal or a lock, `onLetter` (`RoomPage.svelte:813`) still records pending
  edits that are never sent. Fix (S): the grid is read-only while the status is
  final. Spec: `client/hud.md` (final states are out of scope today).
- **L2. Reactions and flags sent offline are lost, and still count for the
  pacing.** `sendReaction` (`RoomPage.svelte:1171`) records the send time even
  when `send` dropped it; « Réagir » and « Je bloque » stay enabled while not
  joined, unlike « Envoyer ». Fix (S): disable them while not joined, count only
  a send that went out. Spec: `social/chat.md` rules 5 and 13.
- **L3. Errors are matched to edits by their code alone.** Five codes remove the
  oldest pending edit (`roomSession.ts:1288`), but `grid_solved` and
  `not_a_letter_cell` also answer undo, check, reveal and `select_cell`
  (`room.py:1736`, `:2215`, `:2369`). Harmless today by analysis, since every
  later edit is refused too, but unwritten. B-028 met the same coupling for
  `rate_limited` (B-031). Fix (S now): write the invariant into
  `gameplay/co-op.md` rule 12 and a server test; (later) a client reference
  echoed in errors, an architecture decision.
- **L4. Some unvalidated server data can throw mid-event.** `applyCheckResult`
  casts `wrong` (`roomSession.ts:991`), `clueText` reads a possibly undefined
  ref (`activityFeed.ts:138`), and dates are formatted without a shape check
  (`ops.ts:499`, `catalogue.ts:96`); `Intl.DateTimeFormat.format` throws on an
  invalid date, after `session.seq` has moved. The server validates all of it
  today: hardening. Fix (S): validate in the parsers. Spec: none.
- **L5. The heartbeat runs on page timers** (`RoomPage.svelte:1751`, a ping
  every 2 s against a 6 s silence limit). Browsers that throttle timers in
  hidden tabs may drop and rejoin the player about once a minute (plausible;
  depends on the engine's policy). Fix (M): measure first; then pings sent by
  the server, or a check on `visibilitychange`. Spec: `platform/realtime.md`
  rules 16 and 18.
- **L6. A socket stuck connecting has no timeout** (the timers start in
  `onopen`, `RoomPage.svelte:1896`): on a network that drops packets the page
  waits for the system's TCP timeout before the next try. Fix (S): a connect
  timer in `openSocket`. Spec: `platform/realtime.md` rule 18.
- **L7. Reconnection delays have no jitter** (`roomSession.ts:1359`): after a
  server restart every page retries at exactly 1, 2, 4 and 8 s. Fix (S): ±20 %.
  Spec: `platform/realtime.md` rule 21 fixes the exact delays.

Room page:

- **L8. Focus falls to the page when a remote event removes what holds it.**
  The host sheet is unmounted when `isHost` turns false
  (`RoomPage.svelte:2365`), so its `onClosed` never focuses « Menu »; « Oui »
  of the vote is disabled under the focus when the connection drops. Fix (S):
  close the sheet through its API; an `$effect.pre` for the vote buttons, as
  ChatPanel does for a mute. Spec: `lobby/host.md` rule 8,
  `gameplay/hints.md` rule 19.
- **L9. An invalid count in the host settings fails silently or in the
  browser's language** (`HostSettings.svelte:65`, no `novalidate`). Fix (S):
  `novalidate`, an error line from `fr.json`, `aria-invalid` and
  `aria-describedby`. Spec: `lobby/host.md` rule 8.
- **L10. Any `settings_changed` resets the unsaved settings form.** An
  `$effect` copies the snapshot into the inputs (`RoomPage.svelte:588`), so a
  lock toggled in the same sheet overwrites a typed count. Fix (S): a writable
  `$derived`, or resync only the fields that changed. Spec: `lobby/host.md`
  rule 8 (decide whether a lock-only change resets the fields).
- **L11. « Rejoindre » does nothing during the retry delay** while the kept
  form waits for a reconnection (`RoomPage.svelte:633`, `:2011`). Fix (S):
  disabled unless the status is `nickname`. Spec: `lobby/joining.md` rule 9.
- **L12. An open menu keeps its old place when the top bar changes form without
  a layout change** (`RoomPopover.svelte:50`; plausible). Fix (S): place it
  again after `tick()` when the form changes. Spec: none.
- **L13. Whole-grid work on every keystroke.** `filledWords` copies every cell
  through `shownGrid` even with the Salon closed (`RoomPage.svelte:1494`);
  `letterCellAt` scans the grid once per cell of a word (`:690`); `shownCell`
  walks the pending edits per cell. Small on a 13 by 17 grid, but on the path
  of rule 23. Fix (S): a cell index per snapshot and a latest-pending-edit map.
- **L14. The scrolling lists re-observe every item on each new line**, with two
  ResizeObservers on the chat stream (`scrollingLists.ts:16`, `:203`). Fix (S):
  one watcher per list that observes added nodes and drops removed ones.

Grid and pages:

- **L15. A pinch that gains a third finger and loses one makes the zoom jump**
  (`GridViewport.svelte:526`: the baseline is not reset when back to two
  fingers), and without pointer capture a lost `pointerup` can leave a ghost
  finger (plausible). Fix (S): re-baseline at two fingers, capture the pointer,
  treat `lostpointercapture` as an end.
- **L16. A pinch costs more than it needs:** `--triangle` is set on every letter
  cell (`:674`) though it is one value per grid, each move forces `flushSync`
  and a relayout, and every arrow has two `drop-shadow` filters (`:1143`).
  Fix (S): `--triangle` on `.grid`; the arrows' white halo as an SVG stroke.
- **L17. The account dialog closes when a drag that started inside it ends on
  the backdrop** (`AccountDialog.svelte:50`), losing the typed address. Fix (S):
  close only when both the press and the release were on the backdrop (in the
  shared sheet of M8).
- **L18. Overlapping ops requests are not sequenced**: « 1 jour » then « 30
  jours » can end on 1 day when the answers cross (`OpsPage.svelte:83`); the
  replay has the same race (`OpsReplay.svelte:70`). Fix (S): a request counter
  per kind. Spec: maybe `admin/operations.md` rules 18 and 19.
- **L19. An operator token that cannot be a header value sticks**: a « € » in
  it makes `Headers.set` throw, the page shows `error`, and a reload reads the
  same token from `sessionStorage` again (`OpsPage.svelte:95`, `ops.ts:176`).
  Fix (S): check the token's shape before storing it; clear the field on lock;
  focus it when the form comes back. Spec: maybe `admin/operations.md` rule 16.

Accessibility and text:

- **L20. Two interface strings outside `fr.json`** (`product.md` rule 20): the
  list separator `', '` (`history.ts:224`, `clueFlags.ts:112`,
  `MyRooms.svelte:87`, `SharePage.svelte:58`) and the units « h » and « min »
  (`OpsSettings.svelte:52`). Fix (S): `Intl.ListFormat('fr')` or a key; two
  unit keys.
- **L21. On the plain pages the top bar is inside `<main>`**, so there is no
  banner landmark and jumping to the main content lands on the brand link
  (`CatalogueFrame.svelte:34`, `EntryFrame.svelte:24`). Fix (M): the two frames
  own `<main>` after the top bar; check the tests that locate `main`.
- **L22. Names and references.** The catalogue's « Jouer » buttons cannot be
  told apart (`CatalogueItem.svelte:143`; the sibling lists name theirs);
  `aria-controls="reaction-picker"` points to an element that exists only while
  open (`ClueBar.svelte:80`); the nickname field is `aria-invalid` without
  `aria-describedby` (`RoomPage.svelte:1995`). Fix (S): `aria-describedby` to
  the card's title; set the references only while their target exists.

Delivery and structure:

- **L23. One bundle serves every route, and the fonts are neither subset nor
  preloaded.** `App.svelte` imports every page statically, so `/r/<code>` parses
  the ops, account and catalogue code; the fontsource CSS declares 50 faces
  (cyrillic, greek, vietnamese, and WOFF fallbacks: 98 files in `dist`, though
  `unicode-range` keeps the download to the faces used); nothing preloads the
  grid's faces. Fix (M): `import()` per page in `App.svelte` (no config change),
  the `latin` and `latin-ext` subset imports, a preload of the grid's two faces.
  Measure against rule 22 before and after.
- **L24. Duplicated logic.** The « one overlay at a time » rule is applied by
  hand in eight places of `RoomPage.svelte` (`:231` to `:1810`); the expiry
  timers of flashes, caught-up cells and reactions are three copies of one
  pattern (`:430`, `:462`, `:1188`); the window-width tracking of the two page
  frames, the play state machine of `CatalogueItem` and `HistoryItem`, and the
  WebKit `tabindex` link workaround (11 copies) are repeated. Fix (M): an
  overlays class, a `trackExpiries` helper, a `PlayButton` and a link component.
- **L25. Leftovers and comments that lie.** `'closed'` in `RoomStatus` is never
  set (`roomSession.ts:24`); the template's global `main` rule is undone in
  three places (`app.css:89`); « Nothing uses them yet » about inks that two
  components use (`app.css:50`); TypeScript constants repeat CSS sizes
  (`CLUE_BAR_HEIGHT_PX`, the scrim's `top: 54px`) and one comment puts the scrim
  on the wrong layer (`RoomPage.svelte:2562`); two one-shot loads run in
  `$effect` instead of `onMount` (`CataloguePage.svelte:95`,
  `GridPage.svelte:46`). Fix (S).
- **L26. The routes table of `product.md` omits `GET /api/account/progress`**,
  which `catalogue.ts:18` calls and `account/account.md` rule 24 defines. Fix
  (S): one row. Spec: `product.md` « Stable routes ».
- **L27. Dependencies.** `npm audit`: two low advisories (deepmerge, through
  `@sveltejs/vite-plugin-svelte`), build-time only, no fix published; patch
  releases are out for svelte, svelte-check and vite. Fix (S, tooling, the
  human's call): take the patches with the next tooling item; nothing ships to
  the browser.

## Structure

`roomSession.ts` is sound; the risk sits in `RoomPage.svelte`, and to a lesser
degree in `GridViewport.svelte` (gestures, key mapping, legend arithmetic,
announcements and cell drawing in 1,321 lines). A split of `RoomPage.svelte`
that keeps behaviour identical, one commit per step, every `data-testid`, id
and the document order of `client/hud.md` rule 3, with no added wrapper
elements:

1. `roomConnection.ts`: socket, heartbeat, silence and reconnection timers,
   `isSynced`, the edit queue and its resend, the join on open, the `online`
   listener, `dispose()`; callbacks to the page. M1, M2, M3 and L6 are then
   small changes in one module.
2. `expiry.svelte.ts`: the three expiry timers (L24).
3. `VoteBanner.svelte`: the countdown, the vote buttons, the live region, its
   CSS.
4. `GridStatus.svelte`: the status, both placements, « Voir le bilan ».
5. `EntryPage.svelte`: the nickname form and the entry cards.
6. `NoteSlot.svelte`: the 3-second notes and the undo refusals.
7. `roomOverlays.svelte.ts`: the overlay state and the rule of one at a time.
8. `playFit.svelte.ts`: the play area's measurements, last because it is about
   pixels (Opus, per `CLAUDE.md`).
9. Optionally, pure `roomCommands.ts` for letter, erase, reveal, check and flag.

Steps 1 and 2 are logic with the strongest browser coverage; 3 to 5 are leaf
components; 6 and 7 move state whose timing is subtle; 8 is pixel-sensitive.
Each step is checked with the quick gate on its families, then the full gate in
the three engines. At the same time, the props drilled through `Salon` (22) and
`RoomTopBar` (26) can be grouped into a few objects. `GridViewport.svelte`
splits the same way: `LetterCell.svelte` and `ClueCell.svelte` with primitive
props (which also gives M5 its natural boundary), a `use:pinchPan` action, a
pure `gridKeys.ts` and a `legendLayout.ts`.

**Tests of the client logic.** The pure modules (`roomSession`, `activityFeed`,
`catchUp`, `remoteSelections`, `joinRules`, `navigation`, `history`,
`wordSelection`, `gridLayout`, `ops.cellStatesAtStep`) are tested only through
Playwright, which is slow for permutations (sequence gaps, errors interleaved
with a resend, a snapshot over pending edits). Two ways, both tooling and the
human's decision: Node's own `node:test` running the TypeScript directly (no new
dependency; `svelte/reactivity` and the JSON import need a small shim), or
Vitest (a new dev dependency). Either makes the refactor above safer, so it
comes before it.

## What is well done

- **Security.** No `{@html}` or `innerHTML`; nicknames, chat and clues render as
  text; `style:` values go through the CSSOM; every link is a same-origin path;
  `t()` fills placeholders with a callback, so user text cannot inject `$&`;
  the ops token stays in `sessionStorage` and a header; the link token leaves
  the URL before use; resume tokens travel only in request bodies.
- **Parsing.** `roomSession.ts` checks every field (`toGrid` with each position
  once, colour ranges, integer refs) and ignores unknown types and codes, which
  keeps the client forward-compatible.
- **Ordering.** The sequence buffer, its drain and the pruning of pending edits
  on a snapshot match `client/shell.md` rule 4; resent edits keep their
  `base_seq` and kind and are paced.
- **Socket lifecycle.** A dropped socket's handlers are detached and every
  handler checks it is still the current socket; 4001 is final, so two tabs do
  not ping-pong; `online` replaces a socket still connecting; a catch-up answer
  applies only if no newer snapshot came.
- **Accessibility.** The grid's roles, ids, `aria-selected`,
  `aria-activedescendant` and polite announcement follow rule 17; Escape
  release and Tab between words are careful; `$effect.pre` moves the focus
  before an element is disabled or removed; forms use `novalidate`,
  `aria-invalid`, `aria-describedby` and `role="alert"`.
- **Letter entry.** `letterEntry.ts` is pure and maps exactly to
  `gameplay/board.md` rule 9: NFD folding, dead keys and composition left to
  the browser, modifiers respected.
- **Rendering.** A local keystroke changes the DOM of the edited cell and the
  cells whose selection changed; the structural derivations do not re-run on
  letters.
- **CSS.** One block of colour tokens; components use `var()` only; every
  engine workaround is explained where it is made.

## Proposed items

The fixes regroup into coherent items. They are not claimed yet: each gets its
number from `scripts/claim_item.py` when the human keeps it, and a brief in
`Backlog.md`. Proposed order:

| # | Item | Findings | Spec change | Size |
| --- | --- | --- | --- | --- |
| 1 | Sign-out forgets the account's seats on the device | H1 | `account/account.md` 13, 17; `client/hud.md` | M |
| 2 | Reconnection keeps order and presence: commands after the resent edits, rejoin from memory, selection sent again, the form's button | M1, M2, M3, L11 | `gameplay/hints.md`, `lobby/joining.md` 8, 9, `platform/realtime.md` 22 | M |
| 3 | The grid's focus ring above the cells, with a pixel check (Opus) | M4 | `_design/foundation.md` « Focus » if the ring moves | S-M |
| 4 | Caching headers for the client, folded into B-034 | M10 | `platform/server.md` « Serving the client » | S |
| 5 | Remote updates in proportion to what changed (Opus: timing) | M5, L13, L16 | none | M |
| 6 | A zoomed grid follows the selection (Opus: layout) | M6 | `gameplay/board.md` 3 | S-M |
| 7 | One room sheet, focus kept in overlays, focus after a remote removal | M7, M8, L8, L9, L17 | `client/hud.md` 12, 13; `lobby/host.md` 8 | M |
| 8 | One live status region, and the names and references | M9, L22 | none | S-M |
| 9 | Connection hardening: final states read-only, offline reactions, connect timeout, jitter, error coupling, parser checks, the heartbeat in hidden tabs | L1 to L7 | `platform/realtime.md` 16, 18, 21; `social/chat.md`; `gameplay/co-op.md` 12 | M |
| 10 | Unit tests for the client's pure modules (tooling, the human's call) | Structure | none | M |
| 11 | Split `RoomPage.svelte` and `GridViewport.svelte`, remove duplication and leftovers | M11, L24, L25 | none | L |
| 12 | Small fixes: ops requests and token, text outside `fr.json`, landmarks, settings form, menu placement, pinch, lists, bundle and fonts, the routes table, dependency patches | L10, L12, L14, L15, L18 to L21, L23, L26, L27 | a line each in `admin/operations.md`, `lobby/host.md`, `product.md` | S each |

Items 1, 2 and 4 come before the first public test: one closes a leak of seats
on shared devices, one stops letters vanishing after a network drop, and the
third keeps a deploy from blanking pages. Item 3 fixes a baseline the product
breaks today. Items 2 and 7 come before item 11, so their new browser tests pin
the behaviour the refactor must keep, and item 10 before it if the human takes
it.

## Appendix: method and checks

- Reading: every file of `web/src`, `web/index.html` and the Vite, Svelte and
  TypeScript config, in three parts read in parallel; the wire contract against
  `src/nock/protocol.py` and the handlers it names; the specs a finding cites.
  `GridViewport.svelte` was compiled with the installed Svelte 5.57.2 to see how
  the cells' template effects are memoised (M5).
- `npm --prefix web ci`, `npm --prefix web run check` (170 files, 0 errors,
  0 warnings), `npm --prefix web run build` (one script of 238.5 KB, 74.7 KB
  gzipped; CSS 71 KB, 16 KB gzipped), `npm --prefix web audit` (2 low,
  build-time), `npm --prefix web outdated` (patches for svelte, svelte-check,
  vite).
- M4: the app served with the main checkout's grids (the worktree has no
  `grids/`), grid 3 opened from the catalogue in Chromium and WebKit through
  Playwright, the grid focused with Tab (computed outline: solid, 2 px,
  `rgb(27, 47, 85)`, offset -3 px), then a screenshot of the grid.
- Gate: `uv run python scripts/gate.py --browsers chromium` on the branch,
  every static check green (ruff, black, screens sheet, traceability, pyrefly,
  svelte-check, grids, vite build), 142 serial tests passed, and 8,256 of 8,257
  parallel tests passed. The one failure,
  `test_spec_041_ac16_ac17_flash.py::test_ac16_cell_flash_has_the_replacers_roster_colour`,
  read both the flash overlay and the roster swatch as transparent while the
  screenshots of M4 ran beside the gate; the file then passed alone three times
  out of three (28 tests each). It is a test that flakes under load, not a
  client defect: under `CLAUDE.md`'s rule it either waits for the flash and the
  swatch to be painted before reading them, or joins `SERIAL_TEST_FILES`.
- Not measured: timings (M5, L13, L16, L23) and screen-reader output (M9). A
  CPU profile of an 8-player stream on the reference phone and an NVDA pass on
  the room page would settle them.
