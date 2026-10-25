---
area: client
file: shell
status: done
---

# client/shell - Pages, connection states, texts and the visual foundation

## Purpose

The browser client as a whole: which page a path shows, how the room page keeps
the room in seq order and what it shows before the room, every text in one
French file, and the foundation every screen is built from (colour tokens,
fonts, focus ring, shared components, state lines).

## Depends on

- `product.md`: stable routes, supported windows, accessibility baselines.
- `platform/realtime.md`: the socket, losses, final closes, the band.
- `lobby/joining.md`: the join on open, the nickname card, the refusal card.

## Rules

### Pages and texts

1. The client picks the page from the path: `/` the catalogue
   (`content/library.md`), `/r/<code>` (6 capitals or digits) the room page,
   `/g/<number>`, `/recap/<token>`, `/account` and `/ops` their domains' pages;
   any other path the client is loaded on shows the page not found. The server
   serves the client only on page routes (`platform/server.md` rule 12). Every
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
   no text in its body. French only.

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
   asks for nothing. What an event changes belongs to its domain.
5. `selection_moved` and `reaction` are dropped before the first snapshot and
   apply at once after it; `error` applies at once at any time. None of them
   touches the seq or the buffer; any other message without an integer `seq`
   is ignored.
6. A final close (`platform/realtime.md` rule 19) ends the tries: 4404
   `not_found`, 4429 `throttled`, 4001 `replaced`; after a refusal, the state
   the `error` set (`full`, `locked`, `removed`). Any other close is a loss:
   `reconnecting` once joined (the band shows, `platform/realtime.md` rule
   20); before, `connecting` with no band.

### Before the room shows

7. Before the first snapshot the page shows one of:
   - the nickname card (`lobby/joining.md`), while the form shows;
   - a final state's card: the room code line `room.heading` (« Salon
     <code> »), then a card titled `room.status.<state>` with the link
     `share.home` (« Voir les grilles ») to `/`. For `not_found` the card adds
     `room.status.not_found_detail` and the link is the primary way on; an
     expired room is deleted and closed with 4404, so it gives this card;
   - else the opening: the room's top bar for the window (`client/hud.md`),
     inert and without timer, so a press on it, the brand included, opens
     nothing, loads nothing and sends nothing; the heading read but not seen;
     and where the grid will be, only the status line
     `room.status.connecting` (« Connexion… ») or `room.status.joining`
     (« Entrée dans le salon… »), seen. No grid, clue bar, keyboard or Salon.
8. The first snapshot turns the opening into the room within 300 ms; a refusal
   turns it into its card, `invalid_nickname` into the nickname card. A loss
   keeps it. Once the room has shown, the status follows `client/hud.md` rule 8.
9. The nickname card, the status cards, the page not found, the shared recap
   and the account page share one frame: a top bar holding only the brand
   (rule 17), then one column of cards. Only room pages put the room code
   line above the card. The frame takes its phone or computer form from the
   window and follows a resize within 300 ms.
10. The page not found is one card titled `not_found.heading` (« Page
    introuvable »), with `share.home` to `/` as its primary way on.

### States and motion

11. A page's state (waiting, empty, failed, done) is one line of text where its
    content will be: muted while waiting or empty, an error line when failed, a
    confirmation line when done. No spinner, no skeleton: no `<progress>`, no
    `role="progressbar"`, no CSS animation (`@keyframes` or an `animation`
    property, vendor prefixes included) in the sources or the built CSS.
12. The note's fade is a transition; under reduced motion it has none.

### Visual foundation

13. Colours come only from the tokens declared once in the token block of
    `web/src/app.css` (`--nock-*`, `--player-colour-N`, `--player-ink-N`).
    Outside a token declaration no CSS declaration, in `web/src` or in the
    built CSS, holds a colour literal: a hex colour, a colour function (not
    `color-mix()`), or a named or system colour; `transparent` and
    `currentColor` are allowed, and so is `#0000` (transparent). Scripts and
    markup hold no hex colour or colour function, and colour attributes of
    markup (`style`, `fill`, `stroke`, …) no named colour. Comments,
    `web/public/favicon.svg` and user content (emoji) are not colours of the
    client.
14. Nock serves its two font families itself, from the packages
    `@fontsource/source-sans-3` and `@fontsource/ibm-plex-sans-condensed`,
    importing only the eight faces the design uses; no request goes to
    another host. `README.md` credits both under the SIL Open Font License 1.1.
    A face that fails to load falls back to the next family. Form controls
    take their parent's font, never the system's.
15. `web/src/lib/icons.ts` holds the design's icon shapes, the eight player
    icons and the Nock mark as data.
16. The shared components (buttons in their variants and disabled, menus and
    their items, details, headings and separators, the badge, the note) and the
    focus ring, including its form on a navy surface, are global styles, their
    colours those of « Components »; a hidden note lets pointers through.
    Nothing of the Vite template's demo is left.

### The brand

17. The brand, the Nock mark (hidden from assistive technology) then
    `app.title`, is a link to `/` named `topbar.home` (« Accueil ») on every top
    bar that shows it but the catalogue's: the grid page's
    (`content/library.md`), the frame's (rule 9), the operator page's and the
    room's computer top bar (`client/hud.md`). Following it loads the page `/`,
    as any link does. On `/` it is plain text, read « Nock »: no link, no Tab
    stop, no `aria-current`. The room's phone top bar has no brand.

### Look

- Tokens, player colours and inks: `_design/foundation.md`, « Colour tokens »,
  « Player colours ». Fonts: « Typography ». Icons: « Icons ». Components and
  focus ring, brand link: « Components ». The scans: « How conformance is
  checked ».
- Grid cells in token colours and the flash: `_design/cells.md`, « Letter cell
  backgrounds », « Letter marks », « Clue cells », « Direction arrows ».
- Entry frame, cards and page not found: `_design/pages.md`, « Entry and
  not-found pages »; the opening and state lines: « States: opening, loading,
  empty, error »; the plain pages: « Plain pages: account, shared recap,
  operator ».

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
  `room.status.not_found`, `room.status.closed`, `not_found.heading`; every
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
  then « Un salon est effacé 30 jours après sa dernière modification. », then
  « Voir les grilles », primary, which loads the catalogue. (← 040 AC-17,
  046 AC-18)
- **AC-10** On `/r/ZZZZZZ` the entry frame has the brand bar, whose Nock mark
  and « Nock » are the link « Accueil » to `/` with no `aria-current`, then
  « Salon ZZZZZZ » and the card, and no room top bar; it follows the entry
  pages design at a computer and a phone window, and takes the other form
  within 300 ms of a resize. (← 046 AC-1)
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
- **AC-13** The client's sources and built CSS hold no `@keyframes`, no
  `animation` property (prefixed or not), no `<progress` and no
  `role="progressbar"`: `a{-webkit-animation:spin 1s}` is refused and
  `a{transition:opacity .25s}` passes. (← 048 AC-13)
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
- **AC-16** Each colour token, translucent token, player colour and ink
  resolves to its value in « Colour tokens » and « Player colours », the
  roster swatch of colour N shows player colour N, the page base takes the
  tokens' white and ink, the page and every form control use the UI font
  stack of « Typography », a control at its parent's size, and the clue font
  token gives the clue stack of « Typography ».
  (← 041 AC-1, 041 AC-2, 041 AC-3, 041 AC-4, 041 AC-21)
- **AC-17** The eight faces load from Nock's origin with status 200 and no
  request leaves it; `web/package.json` lists the two font packages, the
  client imports exactly the eight faces, and `README.md` credits both
  families under the SIL Open Font License 1.1. (← 041 AC-5, 041 AC-6)
- **AC-18** The focus ring on a force chip, the grid and an in-app key, the
  ring on a navy surface, the four button looks (disabled text at 4.5:1 at
  least), the menu, its item (hovered too), detail, heading and separator, the
  badge and the note (hidden, and with reduced motion) each follow
  « Components ». (← 041 AC-7, 041 AC-8, 041 AC-9, 041 AC-10, 041 AC-11,
  041 AC-12, 041 AC-13, 041 AC-14)
- **AC-19** On FX-01 with a locked `T`, a wrong `X`, a pencil `D`, Bob's word
  and VIDE selected, every cell's colours, borders and arrows follow the cells
  design. When Bob replaces a letter, the cell flashes as that design draws
  it, until the flash ends, its letter in ink, a pencil one too, and for every
  player colour the letter keeps 4.5:1 at least. (← 041 AC-15, 041 AC-16,
  041 AC-17)
- **AC-20** The colour scan refuses `<rect fill="white"/>`, passes
  `:root{--nock-navy:#1b2f55}`, and finds nothing in `web/src` or the built
  CSS, which declares each token once; `icons.ts` holds every shape of the
  design once; no demo file or text is left. (← 041 AC-18, 041 AC-19, 041 AC-20,
  040 AC-26)

## Edge cases

- Snapshot 5, event 8 buffered, then snapshot 7: seq 8, nothing buffered; event
  1 then snapshot 0: seq 0 (AC-6).
- A minifier writing `transparent` as `#0000` passes the scan (AC-20).

## Out of scope

- Other languages and a language switch; a dark mode, forced colours, print
  styles; screenshot comparison with the sheets.
- The band, retries and resent edits: `platform/realtime.md`. The join, the
  nickname card and refusals: `lobby/joining.md`, `lobby/rooms.md`. The
  room's frame once shown: `client/hud.md`. The catalogue and its states:
  `content/library.md`. The plain pages' content: `account/account.md`,
  `gameplay/results.md`, `admin/operations.md`.

## Code

- `web/src/App.svelte` (routing, title), `web/index.html`,
  `web/src/lib/i18n.ts`, `web/src/i18n/fr.json`.
- `web/src/lib/roomSession.ts` (frames, seq, final closes), `RoomPage.svelte`
  (socket, cards, opening), `EntryFrame.svelte`, `NotFoundPage.svelte`,
  `PageTopBar.svelte`, `TopBarBrand.svelte`.
- `web/src/app.css` (tokens, page base, focus ring, components),
  `web/src/main.ts` (fonts), `web/src/lib/icons.ts`.
- Tests: `tests/test_spec_041_*` and the `tests/test_spec_040_*`,
  `test_spec_046_*` and `test_spec_048_*` files of the cited criteria.
