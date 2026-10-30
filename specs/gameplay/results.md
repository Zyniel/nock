---
area: gameplay
file: results
status: approved
---

# gameplay/results - End of game, recap, shared recap and history

## Purpose

Once a grid is solved, its players open « Bilan de la partie »: the time, the
help used and what each one brought, with no ranking, and a link that shows the
time and the team to anyone. Each device, and each account, lists its finished
grids in « Grilles terminées », where a grid can be played again.

## Depends on

- `gameplay/rules.md`: solved rooms, `grid_solved`, the timer's text, the band.
- `gameplay/hints.md`: the check and reveal entries the recap counts.
- `lobby/joining.md`: nicknames and their display, summaries; a room's
  deletion is `lobby/lifetime.md`.

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
   (`social/presence.md` rule 12), so they and `revealed_letters` add up to
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
   the heading, the status `recap.loading` and `recap.close` (« Fermer »); on a
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
    lien »). A copy writes it to the clipboard and shows the status
    `room.share.copied` under the row for 2 seconds, the button unchanged;
    without a usable clipboard, nothing.

### The shared recap page

13. `/recap/<token>`, the token matching rule 5's pattern, opens no socket,
    stores nothing, keeps the title `app.title` and asks
    `GET /api/recaps/<token>` once. One card: the status `recap.loading` alone
    while waiting; then the `h1` `share.heading`, `catalogue.item.number` when
    there is a number, `recap.time`, `share.team` (the names displayed, joined
    by « , ») and the link `share.home` to `/`. On a failed request, a status
    other than 200 or a bad body (untested), its title, the page's only `h1`,
    is `share.error`, then `share.home`.

### Finished grids

14. A room keeps its `grid_solved`'s time and `elapsed_ms`, by `replay` too. A
    summary (`lobby/joining.md` rule 16) adds `finished_at` (that time, UTC) and
    `elapsed_ms`, null unless solved; a room stored without them takes them from
    its log.
15. `nock.history` holds the device's records, a JSON array of `{"code",
    "grid", "width", "height", "finished_at", "elapsed_ms", "teammates"}`,
    newest first then by code, at most 100. Not an array reads as none; an item
    of other field types is ignored. A room's deletion removes no record; only
    the cap and a newer record of the same code do.
16. A solved summary writes its room's record, replacing that code's; the
    team-mates are its players but names exactly equal to this device's
    identity nickname for the room. The catalogue page writes one per summary
    of « Mes salons »; the room page, once solved (once per load, untested),
    asks its own summary and writes it. A failed request writes nothing.
17. Signed in (`account/account.md`), the catalogue page adds the records of
    `GET /api/account/history`, one per code, the account's winning, in rule
    15's order, never stored on the device; a failed or malformed answer adds
    none.
18. While there is a record, `history.heading` (« Grilles terminées ») ends
    the catalogue column (`content/library.md` rule 9): a row per record with
    the grid label (`catalogue.item.number` or `my_rooms.unnumbered`) and
    `catalogue.item.size`; a line holding `history.finished` (the date as « Mes
    salons » writes it), `history.time` (the duration as `admin/operations.md`
    writes it) and `history.teammates` (names displayed, `--` as « Ancien
    joueur ») or `history.alone`; with a grid number only, `history.replay`
    (« Rejouer »), named `history.replay_label`.
19. « Rejouer » runs « Jouer »'s steps (`lobby/rooms.md` rule 2) for its grid,
    `finished` progress kept; disabled while it runs; a failure shows the alert
    `catalogue.play_failed` in the row and enables it again.
20. The band, dialog, share page and section keep `product.md`'s baselines at
    its windows; the dialog stays inside the window, scrolls when taller, and
    Tab reaches each control in it.

### Reading and keeping the recap

21. The recap routes (rules 6, 7) read the room without making it live and
    log nothing (`platform/server.md` rule 6). A solved room's recap, once
    built, is kept in memory with the room's seq and reused while the seq is
    the same. A new log entry, or a member's nickname erased
    (`account/account.md` rule 18), has it built again at the next request;
    the room's deletion drops it.

### Look

The band: `_design/overlays.md`, « End of grid ». The dialog:
`_design/overlays.md`, « Recap ». The share page: `_design/pages.md`, « Plain
pages: account, shared recap, operator » and « States: opening, loading, empty,
error ». « Grilles terminées »: `_design/pages.md`, « Catalogue ».

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
  closing alike. Waiting: heading, « Chargement du bilan… », « Fermer »; on a
  404 or a failure, the alert « Le bilan n'est pas disponible. ».
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
  copié » shows under the row, gone at 2.5 s, the button unchanged; a missing or
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
- **AC-17** FX-01 solved by `T` at (4, 4) at t0 + 754 keeps t0 + 754 and 754000,
  as its replay does; its summary has `finished_at` t0 + 754 UTC and
  `elapsed_ms` 754000, an unsolved one's null; a room stored solved without them
  takes its `grid_solved`'s. (← 029 AC-1)
- **AC-18** With identities for `XYZ789` and `ABC234` as `Ana`, and summaries of
  `XYZ789` solved (grid 2, 5 × 5, `Bob`, `Ana`, `Cy`, 2026-10-14T08:30:00Z,
  754000) and `ABC234` not, `nock.history` becomes that one record with `Bob`,
  `Cy`, its row « Grille n° 2 », « 5 × 5 », then, on one line on a computer,
  « Terminée le 14 octobre 2026 », « en 12 min 34 s », « Avec Bob, Cy », and
  « Rejouer » named « Rejouer la grille n° 2 », in the catalogue design. An
  older bare record follows: « Grille hors catalogue », « en 1 h 02 min 05 s »,
  « En solo », no « Rejouer ». A 101st drops the oldest; `not json` reads as
  none; an `elapsed_ms` of `"754000"` drops its item; no record and no
  account, no section. (← 029 AC-2, 046 AC-13)
- **AC-19** A room page applying `grid_solved` or a solved first snapshot asks
  its summary with its token and writes the record; after Ana and Bob solve,
  Ana's catalogue lists grid 1 « Avec Bob » with its time and date. Signed in,
  the account's records join, winning a shared code, unstored; Ana's second
  device lists her room « Avec Bob »; once Zélie erases her account, Ana's row
  reads « Avec Ancien joueur, Bob ». (← 029 AC-2, 029 AC-3, 029 AC-6)
- **AC-20** With grid 1 `finished`, « Rejouer » loads a new code, joined without
  the form, unsolved and empty, progress kept, the button disabled meanwhile; a
  500 or 404 stays on `/`, « Impossible de lancer la partie. Réessayez. » in the
  row, the button enabled. The section passes the scans, Tab reaches « Rejouer »
  with the ring, Enter sends, and 7 team-mates of 20 characters scroll no window
  sideways. (← 029 AC-4, 029 AC-5)
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

- A removed player gets no summary, so no record (`lobby/joining.md` AC-17).
- A team-mate with this device's nickname is left out too (AC-18).
- One grid finished in two rooms gives two records (AC-18).
- A room finished while away is recorded when the device next sees it solved,
  while it exists (AC-19).

## Out of scope

- Leaderboards, ranking, sounds, a recap of an unsolved room, social images or
  Web Share, deleting a share link.
- Deleting, sorting or filtering records; moving them to an account; a link
  from a record to its recap.
- How an account saves and erases records, its history route:
  `account/account.md`. The page frame and state lines: `client/shell.md`.

## Code

- `src/nock/recap.py`: `build_recap`, `public_recap`; `hub.py`: `room_recap`,
  `shared_recap`, the kept recaps, share tokens; `store.py`: `code_for_share_token`; `room.py`:
  `solved_at`, `room_summary`; `server.py`: the recap routes.
- `web/src/App.svelte`: the `/recap/<token>` route. `web/src/lib/`:
  `RoomPage.svelte` (the button), `RecapDialog.svelte`, `recap.ts`,
  `copyLink.ts`, `SharePage.svelte`, `history.ts`, `HistoryList.svelte`,
  `HistoryItem.svelte`, `playGrid.ts`, `CataloguePage.svelte` (the merge and
  the account history).
- Tests: `tests/test_spec_028_*`, `test_spec_029_*`, AC-13 of
  `test_spec_046_ac11_ac13_*`, `test_spec_047_ac06_*` to `..._ac11_*`,
  `..._ac13_*`, `..._ac14_*`, `test_spec_048_ac01_ac02_*`;
  `tests/test_results_*` for AC-21 to AC-23.
