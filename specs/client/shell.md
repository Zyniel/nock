---
area: client
file: shell
status: done
---

# client/shell - Pages, connection states, texts and the brand

## Purpose

The browser client as a whole: which page a path shows, how the room page keeps
the room in seq order, what it shows before the room, every text in one French
file, and the brand on the top bars.

## Depends on

- `product.md`: stable routes, supported windows, accessibility baselines.
- `platform/realtime.md`: the socket and its messages; `platform/reconnection.md`:
  losses, final closes, the band.
- `lobby/joining.md`: the join on open, the nickname card, the refusal card.

## Rules

### Pages and texts

1. The client picks the page from the path: `/` the catalogue
   (`content/library.md`), `/r/<code>` (6 capitals or digits) the room page,
   `/g/<number>`, `/recap/<token>`, `/account` and `/ops` their domains' pages;
   any other path the client is loaded on shows the page not found. The server
   serves the client only on page routes (`platform/serving.md` rule 3). Every
   page sets the document title to `app.title` (« Nock »).
2. Every string a user reads (text, `alt`, `title`, `placeholder`, `aria-*`
   names, the title) comes from `web/src/i18n/fr.json` through `t()`, which
   fills `{name}` and leaves a placeholder with no value as written; data are
   the only exceptions (`product.md` rule 20). `fr.json` is one flat object of
   non-empty strings whose keys match `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$`.
   Markup holds no literal text and no literal value of a text attribute
   (`alt`, `title`, `placeholder`, `label`, `aria-label`, `aria-description`,
   `aria-placeholder`, `aria-roledescription`, `aria-valuetext`); an empty
   `alt` is allowed. `web/index.html` is `lang="fr"`, with an empty title and
   no text in its body. French only. A list of names shown is joined with
   `list.separator`; a unit the client adds after a shown number, outside a
   text's template, is `unit.hours` or `unit.minutes` (the settings card's
   bounds, `admin/overrides.md` rule 11).
20. The code that only one page uses is fetched only on that page's route.

### The room page's connection

3. At load the page opens one socket (`wss` under https) and is `connecting`.
   Before the first snapshot, on open it is `nickname` or `joining`
   (`lobby/joining.md` rule 8); after one, a new socket stays `reconnecting`
   until its snapshot. A text frame that is not a JSON object with a string
   `type` is ignored, and so is every binary frame.
4. A snapshot that does not parse (its grid, seq, players, `you` or token) is
   ignored. Else it becomes the room: state `joined`, seq its seq; buffered
   events at or below it are dropped, then the buffer drains. An event is any
   other message with an integer `seq`. Before the first snapshot it is dropped;
   after, one at or below seq is ignored, seq + 1 is applied and the buffer
   drains (while it holds seq + 1, that event is applied), and a later one is
   buffered, once per seq. A gap that never fills stays buffered and the page
   asks for nothing. What an event changes belongs to its domain. An event
   applies whole: a part of it of the wrong shape is skipped as if absent (a
   struck cell of a `check_result` that is not two integers strikes nothing),
   and the event still takes its seq.
5. `selection_moved` and `reaction` are dropped before the first snapshot and
   apply at once after it; `error` applies at once at any time. None of them
   touches the seq or the buffer; any other message without an integer `seq`
   is ignored.
6. A final close (`platform/reconnection.md` rule 4) ends the tries: 4404
   `not_found`, 4429 `throttled`, 4001 `replaced`; after a refusal, the state
   the `error` set (`full`, `locked`, `removed`). Any other close is a loss:
   `reconnecting` once joined (the band shows, `platform/reconnection.md` rule
   5); before, `connecting` with no band.

### Before the room shows

7. Before the first snapshot the page shows one of:
   - the nickname card (`lobby/joining.md`), while the form shows;
   - a final state's card: the room code line `room.heading` (« Salon
     <code> »), then a card titled `room.status.<state>` with the link
     `share.home` (« Voir les grilles ») to `/`. For `not_found` the card adds
     `room.status.not_found_detail` and the link is the primary way on; an
     expired room is deleted and closed with 4404 (`lobby/lifetime.md`), so it
     gives this card (once the room has shown, a 4404 gives the room-gone dialog,
     `client/hud.md` rule 16);
   - else the opening: the room's top bar for the window (`client/hud.md`),
     inert and without timer, so a press on it, the brand included, opens
     nothing, loads nothing and sends nothing; the heading read but not seen;
     and where the grid will be, only the status line (`client/foundation.md`
     rule 1) `room.status.connecting` (« Connexion… ») or
     `room.status.joining` (« Entrée dans le salon… »), seen. No grid, clue
     bar, keyboard or Salon.
8. The first snapshot turns the opening into the room within 300 ms; a refusal
   turns it into its card, `invalid_nickname` into the nickname card. A loss
   keeps it. Once the room has shown, the status follows `client/hud.md` rule 7.
9. The nickname card, the status cards, the page not found, the shared recap
   and the account page share one frame: a top bar holding only the brand
   (rule 17), then one column of cards. Only room pages put the room code
   line above the card. The frame takes its phone or computer form from the
   window and follows a resize within 300 ms.
10. The page not found is one card titled `not_found.heading` (« Page
    introuvable »), with `share.home` to `/` as its primary way on.
19. On the pages of rule 9, the catalogue, a grid page and the operator page,
    the top bar is the page's banner, outside `main`, and everything under it
    is in the page's one `main`.

### The brand

17. The brand, the Nock mark (hidden from assistive technology) then
    `app.title`, is a link to `/` named `topbar.home` (« Accueil ») on every top
    bar that shows it but the catalogue's: the grid page's
    (`content/library.md`), the frame's (rule 9), the operator page's and the
    room's computer top bar (`client/hud.md`). Following it loads the page `/`,
    as any link does. On `/` it is plain text, read « Nock »: no link, no Tab
    stop, no `aria-current`. The room's phone top bar has no brand.

### Look

- The brand link: `_design/foundation.md`, « Components ».
- Entry frame, cards and page not found: `_design/pages.md`, « Entry and
  not-found pages »; the opening: « States: opening, loading, empty, error »;
  the plain pages: « Plain pages: account, shared recap, operator ».

## Acceptance criteria

- **AC-1** `/` with no grid shows the catalogue page with « Grilles » and
  « Aucune grille pour le moment. », and no room page; with the client loaded
  at `/nowhere`, it shows the page not found, in the entry frame with no room
  code line, whose « Voir les grilles » Tab reaches with the ring and Enter
  follows to the catalogue. (← 040 AC-14, 046 AC-19)
- **AC-2** On `/` and `/r/ABC123` the document title is « Nock » and `<html>`
  has `lang="fr"`; `web/index.html` has an empty title and no body text.
  (← 040 AC-15, 040 AC-25)
- **AC-3** `fr.json` is flat, its keys and values follow rule 2, and it holds
  `app.title`, `catalogue.heading`, `catalogue.empty`, `room.heading`,
  `room.default_nickname`, `room.status.connecting`, `room.status.joined`,
  `room.status.not_found`, `not_found.heading`, and no `room.status.closed`; every
  key a `t("…")` call names exists; markup with `<p>Bonjour</p>` is refused,
  `<p>{t("a.b")}</p>` passes, and no `.svelte` file is refused.
  (← 040 AC-22, 040 AC-23, 040 AC-24)
- **AC-4** Entering a fresh FX-01 room through the nickname form, the page is
  joined at seq 1 on a 5 × 5 grid, its status reads « Connecté » and its
  heading « Salon <code> ». (← 040 AC-16)
- **AC-5** With nothing stored, the page waits on the form and sends nothing;
  after `Ana` is submitted its one socket sends `join` as `ANA` and, until a
  snapshot, it is joining with no seq, no grid and nothing buffered, its
  status « Entrée dans le salon… ». (← 040 AC-18)
- **AC-6** After a snapshot at seq 5, events 4, 5 and 7 leave seq 5 with one
  buffered; event 6 then gives seq 7 with none. (← 040 AC-19)
- **AC-7** After a snapshot at seq 5, a `selection_moved`, a `reaction`, an
  `error` and the frames `not json`, `[1, 2]`, `{"seq": 6}` and `null` change
  neither seq, buffer nor state; an event 6 then gives seq 6. (← 040 AC-19,
  040 AC-20)
- **AC-8** A close 1011 after a snapshot makes the page reconnecting, its status
  « Reconnexion… » and the band shown; before any snapshot it stays
  connecting with no seq and no band; a close 4404 makes it not found with no
  seq. (← 040 AC-21)
- **AC-9** `/r/ZZZZZZ`, unknown, shows the card « Ce salon n'existe pas. »,
  then « Un salon est effacé après un certain temps sans modification. », then
  « Voir les grilles », primary, which loads the catalogue. (← 040 AC-17,
  046 AC-18)
- **AC-10** On `/r/ZZZZZZ` the entry frame has the brand bar, then « Salon
  ZZZZZZ » and the card, and no room top bar; it follows the entry pages design
  at a computer and a phone window, and takes the other form within 300 ms of a
  resize. On `/r/ZZZZZZ`, on the shared recap loaded and on `/account` signed
  out, at both windows, the bar's Nock mark and « Nock » are the link
  « Accueil » to `/` with no `aria-current`. (← 046 AC-1)
- **AC-11** With an identity stored and the join unanswered, the page shows the
  inert room top bar of its window with no timer, and one seen line « Entrée
  dans le salon… » where the grid will be, with no grid, clue bar or progress
  bar; a click on « Menu », or on a computer on the brand, opens nothing,
  loads nothing and sends nothing; a snapshot brings the timer, clue bar and
  grid within 300 ms. (← 046 AC-20)
- **AC-12** From the opening of a room created on this device, `room_full`
  gives the card « Ce salon est complet (8 joueurs). » within 300 ms with no
  room top bar; `invalid_nickname` the nickname card with
  `join.error.characters`; a close 1011 keeps the opening, reading
  « Connexion… », with no band. (← 046 AC-21)
- **AC-14** The catalogue in its states, the grid page, the nickname card in
  error, each status card, the room not found, the page not found, the
  opening, the shared recap, account and operator pages in theirs pass the
  contrast and language scans of `product.md` on a computer and a phone;
  `fr.json` holds `share.home` and `room.status.not_found_detail` as AC-9
  reads them; Tab reaches the plain pages' controls with the ring.
  (← 046 AC-23, 048 AC-14)
- **AC-15** At every window of `product.md`, none of these scrolls sideways:
  the catalogue whose rows name 8 players or 7 team-mates of 20 characters,
  the grid page, the nickname card in error, the full and not-found cards, the
  opening, the shared recap, the account page asking for deletion and the
  operator page with the FX-02 replay; on the first six, the top bar, each
  row and card, and each of their buttons lie inside their box.
  (← 046 AC-22, 048 AC-14)
- **AC-29** `fr.json` holds `list.separator` « , » then a space, `unit.hours`
  « h » and `unit.minutes` « min »; the shared recap's team reads « Ana, Bob,
  Cy » and the settings card's out-of-bounds line for a room life « Valeur
  hors limites (24 à 8760 h). », and no client module joins shown names with
  a literal separator or adds a literal unit a user reads after a shown
  number.
- **AC-30** On `/`, `/g/1`, `/r/ABC123` showing the nickname form, `/xyz`, a
  shared recap, `/account` and `/ops` locked, the page has one banner, the top
  bar, followed by one `main` holding the page's heading, and no banner inside
  `main`.
- **AC-31** `/` fetches none of the code that only the room page or the
  operator page uses, and `/r/ABC123` none of the code that only the catalogue
  or the operator page uses.
- **AC-34** On FX-01 with `X` at (1, 0) and `Y` at (1, 1), after a snapshot at
  seq 5, a `check_result` 6 whose `wrong` is `[null, {"row": 1, "column": 0},
  {"row": "1", "column": 1}]` gives seq 6, strikes (1, 0) and not (1, 1), and
  adds its stream line; event 7 then gives seq 7.

## Edge cases

- Snapshot 5, event 8 buffered, then snapshot 7: seq 8, nothing buffered; event
  1 then snapshot 0: seq 0 (AC-6).

## Out of scope

- Other languages and a language switch.
- The tokens, fonts, icons, shared components, focus ring, state lines, motion
  and what a frame redraws: `client/foundation.md`.
- The band, retries and resent edits: `platform/reconnection.md`. The join, the
  nickname card and refusals: `lobby/joining.md`, `lobby/host.md`,
  `lobby/rooms.md`. The room's frame once shown: `client/hud.md`. The
  catalogue and its states: `content/library.md`. The plain pages' content:
  `account/my-account.md`, `gameplay/results.md`, `admin/ops-page.md`.

## Code

- `web/src/App.svelte` (routing, title, code per page), `web/index.html`,
  `web/src/lib/i18n.ts`, `web/src/i18n/fr.json`.
- `web/src/lib/roomSession.ts` (frames, seq, final closes, cursors),
  `roomConnection.ts` (the socket), `RoomPage.svelte` (opening),
  `EntryPage.svelte` (the entry page, its cards), `EntryFrame.svelte`,
  `CatalogueFrame.svelte` (the frames and their `main`), `NotFoundPage.svelte`,
  `PageTopBar.svelte`, `TopBarBrand.svelte`.
- Tests: `tests/test_shell_*` and the `tests/test_spec_040_*`,
  `test_spec_046_*` and `test_spec_048_*` files of the cited criteria.
