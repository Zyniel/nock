---
area: gameplay
file: results
status: done
---

# gameplay/results - End of game, recap and shared recap

## Purpose

Once a grid is solved, its players open « Bilan de la partie »: the time, the
help used and what each one brought, with no ranking, and a link that shows the
time and the team to anyone.

## Depends on

- `gameplay/rules.md`: solved rooms, `grid_solved`, the timer's text, the band.
- `gameplay/hints.md`: the check and reveal entries the recap counts.
- `lobby/joining.md`: nicknames and their display; a room's deletion:
  `lobby/lifetime.md`.

## Rules

### The recap

1. A solved room's recap is computed on the server from its state and its log,
   seq 1 to the room's seq: `elapsed_ms` of its `grid_solved`; `grid_number`;
   `checks`, the `check_result` entries (a check a vote passed counts once);
   `letter_reveals` and `word_reveals`, the `reveal_result` entries by scope;
   `revealed_letters`, credited to nobody; `letter_cells`; `word_count` (the
   clues); `share_path`, `/recap/<share token>` or null; and `players`: each id
   with a `player_joined`, at its first one, with its last nickname, `removed`
   when the host removed it, then each other credited id, nickname null. A
   player's `letters` are the cells it authors in the solved grid
   (`social/authorship.md` rule 1), so they and `revealed_letters` add up to
   `letter_cells`.
2. A player's `words`: walking the log from an empty grid, an entry that makes a
   word full (a letter, pencil or not, or a reveal's lock) makes its player the
   completer, nobody for a reveal; an entry that empties a cell of a full word
   takes it away. The completer at the end counts, right letter or wrong; one
   letter can complete two words.
3. There is no recap while unsolved, nor when those entries are not exactly seq
   1 to the room's seq with one `grid_solved` (a room added in a later state),
   nor when a clue has no word (untested).
4. The public recap is `grid_number`, `elapsed_ms` and `team`: the non-null
   nicknames of the players not removed, in order, each once. No recap holds a
   letter, a cell, a clue or a room code.
5. Each room the server creates gets a share token, `secrets.token_urlsafe(16)`
   matching `^[A-Za-z0-9_-]{16,64}$`, not its code, kept with the room across
   restarts and deleted with it. No snapshot or event (untested) holds it; a
   browser gets it only in `share_path`, which lets nobody join the room or
   read its chat.

### Routes

6. `GET /api/rooms/<code>/recap`, the first that applies: an address held by the
   wrong-code throttle (`lobby/rooms.md` rule 9) gets 429 `{"detail": "Too Many
   Requests"}`, nothing recorded; no room, 404 `{"detail": "Not Found"}` and one
   failure recorded, requests at once counted one after another; no recap, 404,
   nothing recorded; else 200, the recap.
7. While a room with a recap has the token, `GET /api/recaps/<token>` answers
   200 with exactly the public recap and `GET /recap/<token>` the client's
   `index.html` (503 unbuilt); otherwise both answer 404 `{"detail": "Not
   Found"}`. The throttle neither counts nor refuses them; a trailing `/` is
   404, no redirect. Nicknames go as stored, in capitals.

### The band and the recap dialog

8. While the page is solved, the end band (`gameplay/rules.md` rule 7) holds,
   after its text, the button « Voir le bilan » (`recap.open`); unsolved, it has
   none. The dialog never opens by itself.
9. The button opens a modal dialog named by its heading `recap.heading`
   (« Bilan de la partie »), the focus inside, after the room's other parts in
   document order, and asks for the recap once per opening. Waiting, it holds
   the heading, the line `recap.loading`, announced by the recap's status
   region (`client/hud.md` rule 18), and `recap.close` (« Fermer »); on a
   failed request, a status other than 200 or a body that is not a recap
   (untested), the alert `recap.error` in the status's place. Escape and
   « Fermer » close it, the focus back on the button; Tab and Shift+Tab stay
   inside.
10. Loaded: the heading; `recap.time`, the time as the timer writes it
    (`gameplay/rules.md` rule 12); `recap.checks`; `recap.reveals`;
    `recap.revealed_letters`; the heading `recap.players_heading`, naming the
    rows' list; while `share_path` is not null, the heading `recap.share_label`
    and the share row; `recap.close`. Numbers go as they are (« 1 lettres »).
11. A row per recap player, in order, but none for a removed player with no
    letter and no word: a dot, the nickname displayed as text
    (`lobby/joining.md` rule 3; `feed.someone` when null), `roster.you` on
    one's own, `recap.player_letters`, `recap.player_words`. The dot has the
    colour of the page's roster for that id, else draws nothing; with
    « Accessibilité » on (`social/presence.md`), a player the roster knows gets
    their icon instead, and any other dot still draws nothing.
12. The share row: the link `<origin>` + `share_path`, as target and text,
    described by `recap.share_label`, then `room.share.copy` (« Copier le
    lien »). A copy writes it to the clipboard and shows `room.share.copied`
    under the row for 2 seconds, announced as in rule 9, the button
    unchanged; without a usable clipboard, nothing. Neither this line nor
    `recap.loading` has a live role.

### The shared recap page

13. `/recap/<token>`, the token matching rule 5's pattern, opens no socket,
    stores nothing, keeps the title `app.title` and asks
    `GET /api/recaps/<token>` once. One card: the status `recap.loading` alone
    while waiting; then the `h1` `share.heading`, `catalogue.item.number` when
    there is a number, `recap.time`, `share.team` (the names displayed, joined
    by « , ») and the link `share.home` to `/`. On a failed request, a status
    other than 200 or a bad body (untested), its title, the page's only `h1`,
    is `share.error`, then `share.home`.

### Baselines

20. The band, dialog and share page keep `product.md`'s baselines at its
    windows; the dialog stays inside the window, scrolls when taller, and Tab
    reaches each control in it.

### Reading and keeping the recap

21. The recap routes (rules 6, 7) read the room without making it live and
    log nothing (`platform/server.md` rule 6). A solved room's recap, once
    built, is kept in memory with the room's seq and reused while the seq is
    the same. A new log entry, or a member's nickname erased
    (`account/erasure.md` rules 1, 5), has it built again at the next request;
    the room's deletion drops it.

### Look

The band: `_design/overlays.md`, « End of grid ». The dialog:
`_design/overlays.md`, « Recap ». The share page: `_design/pages.md`, « Plain
pages: account, shared recap, operator » and « States: opening, loading, empty,
error ».

## Acceptance criteria

- **AC-1** A FX-01 room solved at 754 s after a word check, a grid check and
  reveals of (0, 1) and LEST gives 754000 ms, 2 checks, 1 and 1 reveals, grid 1,
  18 letter cells, 8 words; a grid check a vote passed counts once, a vote
  only opened nothing; over HTTP a game with one check answers 200, 1 check
  and the players' `grid_solved` time. (← 028 AC-1)
- **AC-2** There Ana has 8 letters, Bob 5, 5 are revealed (8 + 5 + 5 = 18), none
  credited; a letter Ana typed, then Bob revealed, is credited to nobody. Bob's
  `X` over Ana's `A`, undone, credits the cell to Bob; a check's lock keeps the
  author; a confirmation credits the confirmer. A socket game with (0, 1)
  revealed gives 17 player letters and 1 revealed. (← 028 AC-2, 028 AC-4)
- **AC-3** Bob's `S` at (1, 4) completes TAMIS and SENT for him; Ana completes
  AMEN, erases (3, 3), Bob's `E` there makes it his; an undo emptying a full
  word takes it away; a wrong last letter counts; a confirmation changes no
  completer. In AC-1's game Ana has 4 words, Bob 3, LEST nobody. (← 028 AC-3)
- **AC-4** Ana, Bob, Cy join, Ana removes Cy, they solve: players `ANA`, `BOB`,
  `CY`, Cy removed with 0 and 0, team `ANA`, `BOB`. A player seated back has one
  row at their first join with their last nickname; one back under a new id,
  two rows and one team name; an author who never joined comes last, unnamed; a
  late joiner has 0 and 0 and is in the team. (← 028 AC-2, 028 AC-5, 028 AC-7,
  028 AC-8)
- **AC-5** No recap one step before the solve, nor with seq 12 missing, out of
  order, or zero or two `grid_solved`; later entries are left out; a solved room
  added without its log answers 404 at both APIs. (← 028 AC-8)
- **AC-6** From one address, ten recap requests for `ZZZZZZ` answer 404; the
  eleventh, for a solved room, 429 `{"detail": "Too Many Requests"}`, a socket
  then 4429; still 429 at 30 s, 200 at 60 s. Nine wrong codes, or twelve
  requests for an unsolved room, hold nothing; forty at once get ten 404 and
  thirty 429. (← 028 AC-8)
- **AC-7** An unsolved room's token, `tok_unknown_0123456789` and `a b` get 404
  `{"detail": "Not Found"}` at both share routes, uncounted; a solved one with
  a `/` added is 404, no redirect. Solved, the API answers exactly
  `grid_number`, `elapsed_ms`, `team`, the page `index.html` (503 unbuilt, the
  API 200), and both recaps hold no answer. (← 028 AC-5, 028 AC-6, 028 AC-8)
- **AC-8** Created rooms get distinct tokens of the pattern, none their code,
  in no snapshot; `tok_ABCDEFGHIJKLMNOP`, stored, finds its solved room after a
  restart with the same recaps; an added room keeps its token; none gives
  `share_path` null; a token off the pattern is refused. (← 028 AC-9)
- **AC-9** Unsolved, no « Voir le bilan »; after `grid_solved` the band shows
  ✓ « Grille terminée, bravo ! » then « Voir le bilan », the dialog closed,
  nothing asked, a tap still selecting (1, 0); a solved first snapshot too;
  full but wrong, none. At 1280 by 720 and 320 by 568 the band follows its
  design, the button whole on one line. (← 028 AC-7, 047 AC-6)
- **AC-10** « Voir le bilan », hit at its centre, asks once and opens the modal
  dialog named « Bilan de la partie », focused, after the top bar, band and
  Salon; Escape closes it onto the button; reopened it asks again, « Fermer »
  closing alike. Waiting: heading, « Chargement du bilan… » with no live role,
  « Fermer », and the recap's status region, empty at the opening, then
  reading « Chargement du bilan… »; on a 404 or a failure, the alert « Le
  bilan n'est pas disponible. ».
  (← 028 AC-1, 028 AC-7, 028 AC-10, 047 AC-11)
- **AC-11** 754000 ms, 2 checks, 1 and 1 reveals, 5 revealed read « Temps :
  12:34 », « Vérifications : 2 », « Révélations : 1 lettres et 1 mots »,
  « Lettres révélées : 5 », « Qui a fait quoi », in rule 10's order and the
  design's type; 3,725,000 ms reads « Temps : 1:02:05 ». (← 028 AC-1, 047 AC-8)
- **AC-12** With Ana (me, colour 0; 8 letters, 4 words) then Bob (colour 1; 5,
  3), rows read Ana, « (vous) », « 8 lettres », « 4 mots complétés », then Bob,
  « 5 lettres », « 3 mots complétés », dots in roster colours. Bob gone, or an
  unknown id, has a dot drawing nothing, names aligned; a null nickname reads
  « Quelqu'un »; a removed player shows only with a letter or word;
  Accessibilité on, my dot is my icon. (← 028 AC-2, 028 AC-7, 047 AC-9)
- **AC-13** The share link reads and targets `<origin>/recap/<token>`, described
  by « Lien à partager »; in Chromium « Copier le lien » copies it, « Lien
  copié » shows under the row with no live role, gone at 2.5 s, the recap's
  status region reading it, the button unchanged; a missing or
  refusing clipboard shows nothing; `share_path` null, no share heading or row.
  (← 028 AC-5, 047 AC-10)
- **AC-14** At every window, computer or touch, the open dialog lies inside and
  Tab reaches the link, « Copier le lien », « Fermer », ten Tabs staying in it;
  they and « Voir le bilan » show the focus ring, Enter opens, Escape closes. A
  dialog in the column layout, a bottom sheet in the sheet layout, its scrim
  over the top bar. Band, loaded, waiting and unavailable pass the scans;
  `<b>Eve</b>` shows as the text `<b>eve</b>`. (← 028 AC-10, 047 AC-7,
  047 AC-13, 047 AC-14)
- **AC-15** Ana and Bob solve; her recap links to `<base>/recap/<token>`; a
  third browser there reads « Équipe : Ana, Bob », « Temps : » with the API's
  time, « Grille n° 1 », « Voir les grilles » to `/`, title `app.title`, with no
  room page, form or socket, empty `localStorage`, no other API request; no
  grid number, no grid line; an unknown token loads as a 404. (← 028 AC-5,
  028 AC-6)
- **AC-16** Waiting, the card holds only « Chargement du bilan… » as a status;
  on a 404 or 500 its `h1` reads « Ce bilan n'est pas disponible. », then
  « Voir les grilles »; the card follows its design in each state, the page
  passes the scans, and `<img src=x>` shows as text. (← 028 AC-5, 028 AC-10,
  048 AC-1, 048 AC-2)
- **AC-21** A solved FX-01 room only in the store, saved with Ana still
  connected, answers its recap route and both share routes 200 as before;
  after them it is not live and its log has no new entry.
- **AC-22** In a solved room, the recap route, then `GET /recap/<token>` and
  `GET /api/recaps/<token>` twice each, build its recap once. Once Dan joins,
  the next request builds it again, and its team ends with `DAN`.
- **AC-23** Once Zoé, a player of a solved room whose recap was built,
  erases her account, the next recap names her `--`; once the room is
  deleted, its token answers 404 at both share routes.

## Edge cases

- A removed player with no letter and no word has no row (AC-12).

## Out of scope

- Leaderboards, ranking, sounds, a recap of an unsolved room, social images or
  Web Share, deleting a share link.
- Finished grids and « Grilles terminées »: `gameplay/history.md`. The page
  frame: `client/shell.md`; state lines: `client/foundation.md`.

## Code

- `src/nock/recap.py`: `build_recap`, `public_recap`; `hub.py`: `room_recap`,
  `shared_recap`, the kept recaps, share tokens; `store.py`:
  `code_for_share_token`; `server.py`: the recap routes.
- `web/src/App.svelte`: the `/recap/<token>` route. `web/src/lib/`:
  `RoomPage.svelte` (the button), `RecapDialog.svelte`, `recap.ts`,
  `copyLink.ts`, `SharePage.svelte`, `FocusableLink.svelte` (their links).
- Tests: `tests/test_spec_028_*`, `test_spec_047_ac06_*` to `..._ac11_*`,
  `..._ac13_*`, `..._ac14_*`, `test_spec_048_ac01_ac02_*`;
  `tests/test_results_*` for AC-21 to AC-23.
