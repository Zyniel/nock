---
id: "028"
title: End-of-game recap
status: approved
---

# 028 - End-of-game recap

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

(Note from the lead, 2026-10-15: folded in. The answers are decisions 8 to 12, and
"Open questions" is empty.)

(Note from the lead, 2026-10-16: refined after the first review of spec 028 with
decision 13 below. AC-2 changed (a departed player's swatch is hatched, as in spec
019), so the test-writer updates its test before the implementer runs (first review
of spec 028).)

Epic E7 Completion and recap (US-7.2) · Release: V1 · Epic depends on: E6
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The rooms
engine (`nock.room`, `nock.hub`, `new_room`, `register_room`, the wrong-code
throttle, the test harness) is defined in spec 011, joining in spec 012, removals in
spec 014, edits in spec 015, the log, `replay` and the store in spec 018, who is
the author of a letter in spec 019, checks in spec 023, reveals and the room
toolbar in spec 024, completion and the solved banner in spec 026, the shared
timer and its time format in spec 027, the routes and the client shell in spec 040,
the accessibility rules and scans in spec 035, the traffic rules in spec 037, the
messages in spec 039. Built after specs 024, 025, 019, 020, 021, 022 and 027.

## Goal

As a player, I want to see what each of us brought, so that the win feels shared.

The recap credits contributions without turning a cooperative game into a ranking.

## Public interface

No new protocol message and no new `ErrorCode`: the recap is computed on the
server from the room's log and read over HTTP, since spec 039 keeps it out of the
snapshot (its "Out of scope"). This spec adds the module `nock.recap`, a share
token to each room, two API routes, one page route, the recap dialog in the room
page and the public recap page.

### What the recap counts

On a solved room (spec 026), from its log (every entry from seq 1 to the room's
`seq`) and its state:

- Total time: the `elapsed_ms` of the log's `grid_solved` entry, which is the
  shared timer's value at the solve (spec 027).
- Checks used: the number of `check_result` entries, whatever their scope (spec
  023). A check that a vote approved (spec 025) counts once, when its result is
  logged; a refused check or a vote that failed counts nothing.
- Reveals used: the number of `reveal_result` entries whose target's scope is
  `letter`, and the number whose scope is `word` (spec 024).
- Letters of a player: the letter cells whose `author` is that player in the
  solved state. The author of a letter is spec 019's ("Who is the author of a
  letter"): the player of its last `letter_changed`, so an undo credits the undoer
  and a pencil confirmation the confirmer; a cell locked by a check keeps its
  author; a revealed cell has none.
- Revealed letters: the letter cells whose `revealed` is True. They are credited
  to nobody.
- Words of a player: walking the log in seq order from an empty grid, a word (one
  clue) gets a completer each time an entry turns it from not full to full (spec
  026's "filled": a letter, pencil or not, locked or revealed): the `player_id` of
  a `letter_changed`, or nobody for a `cell_locked` (a reveal; a check's lock never
  fills a cell). An entry that empties a cell of a full word takes its completer
  away. The completer of each word at the end counts. One entry can complete two
  words, the across and the down word of its cell.
- Players: every player who joined the room (its `player_joined` entries), in join
  order, with the nickname of their join, those who left or were removed included,
  since their letters stay in the grid. An author whose id has no `player_joined`
  (only in a state built by hand) is listed after them, with no nickname.
  A player id with several `player_joined` entries (a player seated back after a
  time-out, spec 032 AC-7) is listed once, at the place of its first one, with the
  nickname of its last one. (Note from the lead, 2026-10-15: added, decision 12.)
- Team (share page): the nicknames of the players who were not removed by the host
  (no `player_left` with reason `removed`), in join order, each nickname once.
  Join order here is the order of "Players" above. (Note from the lead,
  2026-10-15: added, decision 12.)

### `nock.recap`

```python
# src/nock/recap.py
from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, StrictBool

from nock.protocol import Count, Nickname, PlayerId
from nock.room import LogEntry, RoomState

SHARE_PATH_PREFIX: str = "/recap/"


class RecapModel(BaseModel):
    """Base of the recap models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RecapPlayer(RecapModel):
    player_id: PlayerId
    nickname: Nickname | None        # None: an author with no player_joined
    letters: Count                   # letters authored in the solved grid
    words: Count                     # words whose last missing letter they wrote
    removed: StrictBool              # removed by the host (spec 014)


class Recap(RecapModel):
    grid_number: int | None          # RoomState.grid_number
    elapsed_ms: Count                # the grid_solved entry's elapsed_ms
    checks: Count
    letter_reveals: Count
    word_reveals: Count
    revealed_letters: Count          # letter cells revealed, credited to nobody
    letter_cells: Count              # 18 on FX-01
    word_count: Count                # clues of the grid, 8 on FX-01
    players: tuple[RecapPlayer, ...] # join order, then authors with no join
    share_path: str | None           # SHARE_PATH_PREFIX + share_token, None without a token


class PublicRecap(RecapModel):
    grid_number: int | None
    elapsed_ms: Count
    team: tuple[Nickname, ...]


def build_recap(state: RoomState, log: Sequence[LogEntry]) -> Recap:
    """Return the recap of a solved room, as "What the recap counts" says.

    Only the entries of `log` with seq <= state.seq are used.

    Raises:
        ValueError: `state.solved` is False, or those entries are not exactly
            seq 1 to state.seq, in order, with one `grid_solved` among them.
    """


def public_recap(recap: Recap) -> PublicRecap:
    """Return what the share page shows: grid number, time and team."""
```

`sum(player.letters for player in recap.players) + recap.revealed_letters ==
recap.letter_cells` holds for every recap (AC-4), and so does
`sum(player.words for player in recap.players) <= recap.word_count` (a word
completed by a reveal counts for nobody).

### Share token (`nock.room`, `nock.store`, `nock.hub`)

```python
# src/nock/room.py (additions; fields and arguments with defaults, as spec 011 requires)
ShareToken = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")]


class RoomState(RoomModel):
    # ... fields of specs 011 to 037, 021, 022 and 027
    share_token: ShareToken | None = None   # spec 028: names the public recap


def new_room(
    code: str,
    grid: Grid,
    now: float,
    grid_number: int | None = None,
    share_token: str | None = None,
) -> RoomState: ...


# src/nock/store.py (addition)
class RoomStore:
    def code_for_share_token(self, token: str) -> str | None:
        """Return the code of the room created (create_room) with this share
        token, or None. How the store finds it is the implementer's choice."""


# src/nock/hub.py (additions)
class RoomRegistry:
    def room_recap(self, code: str) -> Recap | None:
        """The recap of room `code`: build_recap(room_state(code), store log).

        None when there is no such room, when it is not solved, or when
        build_recap raises ValueError.
        """

    def shared_recap(self, token: str) -> PublicRecap | None:
        """public_recap of the room whose share token is `token`, live or only
        in the store (loaded as spec 018 says); None when there is none or
        room_recap gives None."""
```

`register_room` (spec 011) creates every room with
`share_token=secrets.token_urlsafe(16)` (22 characters). A room added with
`add_room` keeps the token of the state it is given. The token is never sent in a
snapshot or an event; it reaches a browser only in a recap's `share_path`, once
the room is solved. It is not the room code, so a share link does not let anyone
join the room or read its chat.

### HTTP routes (`nock.server`)

| Method and path | Answer |
| --- | --- |
| `GET /api/rooms/{code}/recap`, the client's address throttled by spec 011's wrong-code throttle | 429, `{"detail": "Too Many Requests"}`; the request is not counted as a failure |
| `GET /api/rooms/{code}/recap`, no room `code` | 404, `{"detail": "Not Found"}`, and one wrong-code failure recorded for the address (spec 011) |
| `GET /api/rooms/{code}/recap`, `room_recap(code)` is None (not solved) | 404, `{"detail": "Not Found"}`, no failure recorded |
| `GET /api/rooms/{code}/recap`, otherwise | 200, the `Recap` as JSON (`model_dump(mode="json")`) |
| `GET /api/recaps/{token}`, `shared_recap(token)` is None (malformed, unknown, not solved) | 404, `{"detail": "Not Found"}` |
| `GET /api/recaps/{token}`, otherwise | 200, the `PublicRecap` as JSON |
| `GET /recap/{token}`, `shared_recap(token)` is None | 404, `{"detail": "Not Found"}` |
| `GET /recap/{token}`, otherwise | the app's `index.html` (spec 040; 503 when the client is not built) |

Spec 040's other rules hold for these routes: no redirect, a trailing `/` is 404,
no generated documentation. The throttle is the per-app one of spec 011, shared
with the room socket, and reads `rooms.clock`.

### Client: the recap button and dialog

- `data-testid="recap-open"`: a `<button type="button">` with the text
  `t("recap.open")`, in spec 024's `room-toolbar` right after `chat-toggle` (spec
  022), present only while the page is solved (`data-solved="true"`, spec 026).
  Spec 024's toolbar rules apply to it. It is before the grid in document order,
  so nothing focusable follows the grid (spec 035).
- The dialog never opens by itself: spec 026 AC-5 still taps the grid and the
  in-app keyboard of a solved page.
- A click on `recap-open` opens `data-testid="recap"`, a `<dialog>` opened with
  `showModal()`, placed after `room-toolbar` in document order, with
  `aria-labelledby` its `h2`. It fetches `GET /api/rooms/<code>/recap` each time it
  opens and shows `data-testid="recap-loading"` (`t("recap.loading")`) until the
  answer, or `data-testid="recap-error"` (`t("recap.error")`) when the request
  fails or answers anything but 200. It closes with `recap-close` and with
  `Escape` (the native dialog's); the focus then goes back to `recap-open`.
- Contents, once loaded, in this order:
  - an `h2` with `t("recap.heading")`;
  - `data-testid="recap-time"`: `t("recap.time", { time })`, `time` being
    `elapsed_ms` written as spec 027 writes the timer (`12:34`, `1:02:05`);
  - `data-testid="recap-checks"`: `t("recap.checks", { count })`;
  - `data-testid="recap-reveals"`: `t("recap.reveals", { letters, words })`, from
    `letter_reveals` and `word_reveals`;
  - an `h3` with `id="recap-players-heading"` and `t("recap.players_heading")`,
    then `data-testid="recap-players"`, a `ul` with `role="list"` and
    `aria-labelledby="recap-players-heading"`, holding one
    `data-testid="recap-player"` `li` per recap player, in the recap's order,
    except a removed player with no letter and no word. Each has
    `data-player-id`, `data-letters`, `data-words`, `data-you` (`true` for the
    page's `you`), and holds `data-testid="recap-colour"`, a swatch with
    `data-colour` set as spec 019 sets an author mark's (the player's colour index
    when the kept snapshot lists the player, else `""`) and drawn as "The swatch of
    a recap player" below says; `data-testid="recap-name"`, the nickname as text
    (`t("feed.someone")` when it is null); `t("roster.you")` in its own element on
    my row; `data-testid="recap-letters"` with `t("recap.player_letters", { count })`;
    and `data-testid="recap-words"` with `t("recap.player_words", { count })`;
  - `data-testid="recap-revealed"`: `t("recap.revealed_letters", { count })`;
  - when `share_path` is not null: `data-testid="recap-share-link"`, an `<a>` whose
    `href` and text are `location.origin + share_path`, described by a
    `t("recap.share_label")` label, and `data-testid="recap-copy"`, a button that
    behaves as spec 011's `copy-link` (text `t("room.share.copy")`, then
    `t("room.share.copied")` for 2 seconds after a successful copy; nothing changes
    without a usable clipboard);
  - `data-testid="recap-close"`: a button with `t("recap.close")`.
- The swatch of a recap player (`recap-colour`). With a colour index (`0` to `7`)
  its computed `background-image` is `none`. With `data-colour=""` it is hatched,
  never a plain colour, as spec 019 hatches a departed author's band ("The view,
  switch on"): its computed `background-image` is a `repeating-linear-gradient`
  whose line is diagonal (an angle that is not a whole multiple of 90 degrees, or
  a corner keyword such as `to top right`) and whose colour stops hold at least
  two different colours, and each colour of the swatch (its computed
  `background-color` and those stops; a colour with alpha 0 does not count) is a
  grey, its red, green and blue channels within 8 of each other, so none is a
  player colour. So a departed player's swatch differs from every player's by its
  pattern, not by its colour. (Note from the lead, 2026-10-16: added. The "Contents"
  item above used to say "else `""`, a neutral grey that is none of the eight
  player colours". A plain grey has almost the lightness of red, teal and olive,
  so colour-blind players read it as a player colour; spec 019 stopped using one
  on 2026-10-15 (its decision 10), and the swatch follows it, decision 13 (first
  review of spec 028).)
- The dialog lies inside the window at every window size; when its content is
  taller, the dialog scrolls, and every control in it stays reachable with `Tab`.
  Every text is inserted as text (spec 037 AC-4).

### Client: the public recap page

- `web/src/App.svelte` gains the route `/recap/<token>` (`<token>` matching
  `^[A-Za-z0-9_-]{16,64}$`), which shows `data-testid="recap-page"`. It opens no
  WebSocket and stores nothing in `localStorage`.
- It fetches `GET /api/recaps/<token>` and shows `recap-loading` until the answer,
  then: an `h1` with `t("share.heading")`; `data-testid="share-grid"` with
  `t("catalogue.item.number", { number })` when `grid_number` is not null;
  `data-testid="share-time"` with `t("recap.time", { time })`;
  `data-testid="share-team"` with `t("share.team", { names })`, the team joined by
  `, `; and `data-testid="share-home"`, a link to `/` with `t("share.home")`. A
  failed request shows `data-testid="share-error"` with `t("share.error")`.
- `document.title` stays `t("app.title")` (spec 040).

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `recap.open` | `Voir le bilan` |
| `recap.heading` | `Bilan de la partie` |
| `recap.loading` | `Chargement du bilan…` |
| `recap.error` | `Le bilan n'est pas disponible.` |
| `recap.time` | `Temps : {time}` |
| `recap.checks` | `Vérifications : {count}` |
| `recap.reveals` | `Révélations : {letters} lettres et {words} mots` |
| `recap.players_heading` | `Qui a fait quoi` |
| `recap.player_letters` | `{count} lettres` |
| `recap.player_words` | `{count} mots complétés` |
| `recap.revealed_letters` | `Lettres révélées : {count}` |
| `recap.share_label` | `Lien à partager` |
| `recap.close` | `Fermer` |
| `share.heading` | `Grille terminée` |
| `share.team` | `Équipe : {names}` |
| `share.home` | `Voir les grilles` |
| `share.error` | `Ce bilan n'est pas disponible.` |

Numbers are used as they are (`1 lettres`), as spec 013 does. Spec 035 AC-9's
checker reads every `fr.json` value as a pattern and must still flag `Loading…`,
`Salon` and `Check word`; none of these values matches them.

### Test harness

- Rule tests: `new_room("ABC123", fx01_grid, NOW, grid_number=1, share_token="tok_ABCDEFGHIJKLMNOP")`,
  players `p1` (`Ana`, host) and `p2` (`Bob`) added with `join_room` at `NOW`
  (seq 2), then the plays below with `handle_message`; `log` is every entry of
  every step, in order.
- `PLAY_R` (checks and reveals), from that room: `p1` writes `T`, `A`, `M`, `I`,
  `S` from (1, 0) to (1, 4) at `NOW`; `p1` checks TAMIS
  (`WordTarget(row=0, column=0, clue_index=0)`) at `NOW + 10.0`; `p2` reveals
  `CellTarget(row=0, column=1)` at `NOW + 20.0`; `p2` reveals LEST
  (`WordTarget(row=4, column=0, clue_index=0)`, four empty cells) at
  `NOW + 30.0`; `p2` writes `V`, `I`, `D`, `E` from (2, 1) to (2, 4) at
  `NOW + 100.0`; `p1` checks the grid at `NOW + 200.0`; `p1` writes `A`, `M`, `E`
  from (3, 1) to (3, 3) at `NOW + 300.0`; `p2` writes `N` at (3, 4) at
  `NOW + 754.0`, which solves the grid (seq 34).
- `PLAY_W` (word completions), from that room, every step at `NOW`: `p1` writes
  `T`, `A`, `M`, `I` from (1, 0) to (1, 3); `p2` writes `E` (2, 4), `N` (3, 4),
  `T` (4, 4); `p2` writes `S` at (1, 4), which completes TAMIS and SENT; `p1`
  writes `N` (0, 1), `V` (2, 1), `A` (3, 1), `L` (4, 1) (NAVAL); `p2` writes `I`
  (2, 2), `D` (2, 3) (VIDE); `p1` writes `M` (3, 2), `E` (3, 3) (AMEN); `p1` erases
  (3, 3); `p2` writes `E` at (3, 3) (AMEN again); `p2` writes `E` at (4, 2)
  (MIME); `p1` writes `S` at (4, 3), which completes IDES and LEST and solves the
  grid (seq 23).
- HTTP and WebSocket tests: spec 011's `TestClient` on
  `create_app(rooms=registry, dist_dir=tmp_path, catalogue=...)` with an
  `index.html` written in `tmp_path`; rooms made with
  `registry.register_room(fx01_grid, grid_number=1)` (so with a share token) and
  played by clients over the room socket with
  `RoomConfig(max_edits_per_second=1000)`; the throttle cases use spec 011's
  `FakeClock`.
- Browser with mocked socket: spec 040's mock on `/r/ABC123` with a solved FX-01
  snapshot (`solved` true, every letter right), players `p1` (`you`, `Ana`, colour
  0), `p2` (`Bob`, colour 1); the recap route is answered by
  `page.route("**/api/rooms/ABC123/recap", ...)` with a chosen `Recap` JSON.
- Browser with live server: spec 040's `live_server`, one browser context per
  player through `enter_room`; the solve as spec 026 AC-3 (Ana types the 17 letters
  other than (4, 4), Bob types `T` there).
- Traffic: spec 037's three rules and its checker (as spec 024 extends it).
- Clipboard (Chromium only): spec 011's harness (`clipboard-read` and
  `clipboard-write` permissions, `navigator.clipboard.readText()`), in a test
  marked `@pytest.mark.only_browser("chromium")`.
- Contexts, window sizes and scans: as spec 021 (desktop and touch contexts, spec
  006 AC-5's eight sizes, spec 035's scans and `tab_to`); the share URL and the
  nicknames are test data for the language scan.
- Engines: every browser criterion runs in Chromium, Firefox and WebKit, except
  the clipboard check of AC-5.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-7.2.1) (Python; HTTP; browser with mocked socket) The recap shows the total time, the checks used and the reveals used. Python: `build_recap(state, log)` after `PLAY_R` gives `elapsed_ms == 754000`, `checks == 2`, `letter_reveals == 1`, `word_reveals == 1`, `grid_number == 1`, `letter_cells == 18` and `word_count == 8`. HTTP: two clients, Ana and Bob, solve a FX-01 room over the room socket, Ana having sent one grid check after five letters; `GET /api/rooms/<code>/recap` answers 200 with a body that parses to `Recap` with `checks == 1`, `letter_reveals == 0`, `word_reveals == 0`, and `elapsed_ms` equal to that of the `grid_solved` both clients received. Browser: on the solved page, the route answering a `Recap` with `elapsed_ms` 754,000, `checks` 2, `letter_reveals` 1 and `word_reveals` 1, a click on `recap-open` opens `recap`, where `recap-time` reads `Temps : 12:34`, `recap-checks` reads `Vérifications : 2` and `recap-reveals` reads `Révélations : 1 lettres et 1 mots`.
- **AC-2** (AC-7.2.2) (Python; browser with mocked socket) For each player, the recap shows the final letters they authored. Python: after `PLAY_R`, `players` is `p1` (`Ana`, 8 letters) then `p2` (`Bob`, 5 letters), neither removed; after `PLAY_W`, `p1` has 10 letters and `p2` 8. In a variant of `PLAY_W` where, right after `p1`'s first four letters, `p2` writes `X` at (1, 1) and then undoes it (spec 018: the cell gets back `A`, authored by the undoer), `p1` has 9 letters and `p2` 9: (1, 1) counts for `p2`, as spec 019 says. Browser: with the route answering `players` `p1` (`Ana`, 8 letters, 4 words) and `p2` (`Bob`, 5 letters, 3 words), `recap-players` holds two `recap-player` in that order; `p1`'s row has `data-you="true"`, `recap-name` `Ana`, an element reading `fr.json["roster.you"]`, `recap-letters` `8 lettres` and `recap-words` `4 mots complétés`; `p2`'s row reads `Bob`, `5 lettres` and `3 mots complétés`; each `recap-colour` has the `data-colour` of the player's `roster-colour` (`0` and `1`); and after a `player_left` of `p2` (reason `timed_out`) applied before opening, `p2`'s swatch has `data-colour=""` and is hatched: its computed `background-image` is a diagonal `repeating-linear-gradient` whose colours, like all the swatch's colours, are greys ("The swatch of a recap player"). In both states (`p2` in the room, and after the `player_left`), the computed `background-image` of a swatch with a colour index is `none`. (Note from the lead, 2026-10-16: the browser part used to end at "`p2`'s swatch has `data-colour=""`", with no check of how a swatch looks. A departed player's swatch is now hatched as spec 019's band is, and the others have no pattern; decision 13 (first review of spec 028).)
- **AC-3** (AC-7.2.2) (Python) For each player, the recap counts the words they completed by writing the last missing letter. After `PLAY_W`: `p2` has 5 words (TAMIS and SENT with one letter at (1, 4), VIDE, AMEN after `p1`'s erase, MIME) and `p1` has 3 (NAVAL, then IDES and LEST with one letter at (4, 3)). After `PLAY_R`: `p1` has 4 words (TAMIS, NAVAL, MIME, IDES), `p2` has 3 (VIDE, AMEN, SENT), and LEST, filled by the word reveal, counts for nobody.
- **AC-4** (AC-7.2.3) (Python; HTTP) Revealed letters are credited to nobody, and the players' letters plus the revealed letters equal the grid's letter cells: 18 on FX-01. Python: after `PLAY_R`, `revealed_letters == 5`, no player's letters include a cell of (0, 1), (4, 1), (4, 2), (4, 3) or (4, 4), and `8 + 5 + 5 == 18 == letter_cells`; after `PLAY_W`, `revealed_letters == 0` and `10 + 8 == 18`. HTTP: in a game over the room socket where Bob reveals (0, 1) and Ana and Bob type the 17 other letters, the recap's player letters sum to 17 and `revealed_letters` is 1.
- **AC-5** (AC-7.2.4) (HTTP; browser with live server, its copy check Chromium only) A share link shows the time and the team. HTTP: in a FX-01 room where Ana (host), Bob and Cy join, Ana removes Cy (spec 014), and Ana and Bob solve the grid, the recap's `share_path` is `/recap/<token>` with the room's share token; `GET /api/recaps/<token>` answers 200 with a body that parses to `PublicRecap(grid_number=1, elapsed_ms=<the recap's>, team=("Ana", "Bob"))`, while the recap's `players` lists Cy with `removed` True, 0 letters and 0 words; `GET /recap/<token>` answers 200 with `index.html`. Browser: Ana and Bob solve a FX-01 room on the live server; on Ana's page `recap-open` opens the recap, whose `recap-share-link` has `href` and text `<base_url>/recap/<token>`; a third browser context opens that URL: `recap-page` shows `share-team` reading `Équipe : Ana, Bob` and `share-time` reading `fr.json["recap.time"]` with the time of `GET /api/recaps/<token>` written as spec 027 writes it; the page shows no `room-page` and no `nickname-form`, and opens no WebSocket (Playwright's `page.on("websocket")` records none). Chromium only: a click on `recap-copy` puts that URL in the clipboard and the button then reads `fr.json["room.share.copied"]`.
- **AC-6** (AC-7.2.4) (HTTP; browser with live server) The share link shows no letter of the solution. HTTP: in the room of AC-5, the body of `GET /api/recaps/<token>` is a JSON object with exactly the keys `grid_number`, `elapsed_ms` and `team`, and it and the body of `GET /api/rooms/<code>/recap` each pass spec 037's three rules (no key `answer` or `solution`, none of the eight FX-01 answers as a substring, no letter at a cell). Browser: every response body and WebSocket frame the share page of AC-5 receives passes the same rules.
- **AC-7** (new) (browser with mocked socket) The recap opens only on request and never blocks the grid. On an unsolved FX-01 page there is no `recap-open`. After the mock sends `grid_solved` (seq 6), `recap-open` shows in `room-toolbar` right after `chat-toggle`, no `recap` dialog is open, a click on the cell (1, 0) still selects it (`data-selected-row="1"`, spec 026 AC-5) and no request to `/api/rooms/ABC123/recap` was made. A click on `recap-open` makes one such request and opens `recap` with the focus inside it; `Escape` closes it and the focus is on `recap-open`; opened again, a click on `recap-close` closes it the same way. With the route answering 404, the dialog shows `recap-error` with `fr.json["recap.error"]`. A page whose first snapshot is already solved shows `recap-open` too.
- **AC-8** (new) (Python; HTTP with a fake clock) The recap exists only for a solved room, and wrong room codes count against spec 011's throttle. Python: `build_recap` raises `ValueError` for the room of `PLAY_R` one step before the solve, and for `PLAY_R`'s solved state with the entry of seq 12 left out of `log`; `public_recap(build_recap(...))` after `PLAY_R` has `team == ("Ana", "Bob")`. HTTP: `GET /api/rooms/<code>/recap` of a room that is not solved answers 404 and records no failure; `GET /api/rooms/ZZZZZZ/recap` answers 404 ten times; the eleventh recap request, for an existing solved room, answers 429 with `{"detail": "Too Many Requests"}`, and a socket to that room is then closed with 4429 (spec 011); after `advance(60)` the recap request answers 200. `GET /api/recaps/<token>` of an unsolved room's token, of `tok_unknown_0123456789` and of `a b` answers 404 with `{"detail": "Not Found"}`, and so does `GET /recap/<token>` of each; none of these is counted by the throttle.
- **AC-9** (new) (Python with a `RoomStore`) The share token and the recap survive a server restart. A `RoomStore` on a file holds a FX-01 room created with `create_room(new_room(..., share_token="tok_ABCDEFGHIJKLMNOP"))` and `PLAY_R`'s entries appended; `code_for_share_token("tok_ABCDEFGHIJKLMNOP")` returns its code and `code_for_share_token("tok_unknown_0123456789")` returns None. A new `RoomRegistry` on that store gives `room_recap(code) == build_recap(live_state, log)` of `PLAY_R`, and `shared_recap("tok_ABCDEFGHIJKLMNOP")` gives its `public_recap`, the room being loaded from the store. Rooms from `register_room` get distinct share tokens matching `^[A-Za-z0-9_-]{16,64}$`, different from their codes, and no `Snapshot` sent to a client holds the token.
- **AC-10** (new) (browser with mocked socket) The recap dialog and the share page are accessible and fit every window. With the route answering the recap of AC-2 plus a `share_path`: at each window size of spec 006 AC-5, in desktop and touch contexts, the open `recap` lies inside the window (1 px tolerance), and `recap-close`, `recap-copy` and `recap-share-link` can each get the focus with `Tab` inside it; on the solved page, every check of spec 013 AC-6 holds and spec 024 AC-8's toolbar checks hold with `recap-open` among the toolbar's buttons, and on the four small windows, with the toolbar's `scrollLeft` at 0, the left edge of `recap-open` lies inside the toolbar's client area, so the button shows at least in part before any sideways scroll. At 1280 by 720, `tab_to` reaches `recap-open` with spec 035 AC-2's outline, and `Enter` opens the dialog. At 1280 by 720 and 360 by 740, with the dialog open, and on the share page (its API route answered by `page.route`), spec 035's contrast scan finds no offending element and its language scan finds no text outside `fr.json` and the test's data (it accepts `Temps : 12:34`, `8 lettres`, `Équipe : Ana, Bob` and the share URL). Nicknames `<b>Eve</b>` and `<img src=x>` in the recap and the team show as text, with no `b` or `img` element.

## Edge cases and errors

- Wrong letters on the way (AC-2, AC-3): only the solved grid's authors count for
  letters; a word completed with a wrong letter counts for whoever wrote its last
  missing letter, until an erase takes the completion away. See decision 8. (Note
  from the lead, 2026-10-15: "See "Open questions"" became "See decision 8".)
- One edit, two words (AC-3): the letter at the crossing of two words completes
  both.
- Erase and undo (AC-3): an erase or an undo that empties a cell of a full word
  takes its completer away; the next entry that fills it gives the word its new
  completer. An undo that puts a letter back is a `letter_changed` like any other.
- Reveals (AC-3, AC-4): a revealed letter is credited to nobody, also when a player
  had typed the right letter there before (spec 024 decision 4); a word filled by a
  reveal is completed by nobody.
- Checks (AC-2): a check's lock keeps the author (spec 019), so it changes no
  credit.
- Pencil letters (AC-2, AC-3): a pencil letter fills its cell and has an author;
  a confirmation makes the confirmer the author (spec 019, spec 020).
- Departed players (AC-2, AC-5): a player who timed out or was removed keeps their
  row and their letters; on the page their swatch is hatched, as spec 019 hatches a
  departed author's band, never a plain colour, since their colour may now be
  someone else's. A removed player with no letter and no word gets no row, and the
  share page never names a removed player. (Note from the lead, 2026-10-16: "their
  swatch is hatched, as spec 019 hatches a departed author's band, never a plain
  colour" used to read "their swatch is the neutral grey of spec 019"; spec 019
  hatches that band since 2026-10-15, decision 13 (first review of spec 028).)
- Rejoined players (AC-2): a player who timed out and came back with their stored
  token is seated back with the same id (spec 032 AC-7), so the recap has one row
  for them, and their letters and words count once. For example, in a log where
  `p2` (`Bob`) joins, writes, times out, joins again with the same id and writes
  again, `players` holds one `p2` row, at the place of its first join, whose
  `letters` and `words` count every cell and word credited to `p2`, before and
  after the time-out. A player who comes back
  without their token (another device, cleared storage, or a past record dropped by
  spec 032's cap of 100) has a new id, so the recap has two rows, possibly with one
  nickname; the team names each nickname once. (Note from the lead, 2026-10-15: this
  item used to say that a player who timed out and joined again always had a new
  id; decision 12.)
- Late joiner (AC-7): a player who joins a solved room sees `recap-open` and the
  same recap; their own row shows 0 letters and 0 words.
- Time (AC-1): the timer's `elapsed_ms` (spec 027); a hidden timer does not change
  it.
- Rooms with no history (AC-8): a room added with `add_room` in a state whose log
  does not start at seq 1 has no recap: `room_recap` is None and the route answers
  404.
- Rooms made before this spec (AC-9): no share token, so `share_path` is null and
  the dialog shows no share link.
- Expiry (AC-5): the share page lives as long as the room's data; once spec 032
  deletes the room, its share link answers 404.
- Privacy (AC-5): the share page shows the team's nicknames to anyone who has the
  link; it shows no chat, no grid and no room code.
- Throttle (AC-8): `GET /api/rooms/<code>/recap` would otherwise let anyone test
  room codes at full speed, which spec 011's throttle prevents on the socket.
- Answers (AC-6): neither recap holds a letter, a grid or a clue.

## Out of scope

- Public leaderboards (epic E7).
- Shared timer: spec 027.
- Game history: spec 029, which may list `PublicRecap`s.
- A recap that opens by itself at the solve, animations or sounds.
- Images for social networks, the Web Share API, or a recap of an unsolved room.
- Ranking or comparing players beyond their counts.
- Deleting a share link before the room expires.

## Work packages

None.

## Decisions

Proposed in the Phase 6 refine (2026-10-14), for the human's re-approval with this
spec. Each one is already part of the spec above.

1. Where the recap comes from. Options: computed by each page from the events it
   saw, or by the server from the log. Pick: the server, from the log, since a
   page that joined late or reconnected did not see every event, and a departed
   player's nickname is only in the log. Read over HTTP, since spec 039 keeps the
   recap out of the protocol.
2. Authors follow spec 019's rule; the recap reads the cells' `author` in the
   solved state and adds no rule of its own.
3. Share link: a random token per room, made at creation, in a URL of its own
   (`/recap/<token>`), so that sharing the recap shares neither the room code nor
   the chat.
4. The room's recap route uses spec 011's wrong-code throttle.
5. Display: a `Voir le bilan` button in spec 024's toolbar, next to the chat toggle,
   shown once solved, that opens a modal dialog. The toolbar keeps the 100 px grid
   floor, and the dialog never opens by itself, so spec 026 AC-5 still taps the
   grid of a solved page.
6. Team: every player who joined minus those the host removed, each nickname once.
7. Colours: a swatch per row with spec 019's colour rule, so the recap matches the
   authors view; the nickname is always written.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question.

8. "Words they completed by writing the last missing letter" (former open question
   1). Options: (a) the player whose letter filled the word's last empty cell, right
   or wrong, the last such completion counting; (b) the player whose letter made
   the word full and right. Pick: (a), the backlog's words. Already part of the
   spec above.
9. Share link (former open question 2). Options: (a) a page of its own,
   `/recap/<token>`, with a random token per room; (b) a text to copy, with no link
   and no page. Pick: (a). Already part of the spec above.
10. Team on the share page (former open question 3). Options: (a) every player who
    joined, minus those the host removed; (b) only the players present at the
    solve; (c) only the players with at least one letter or word. Pick: (a).
    Already part of the spec above.
11. Opening the recap (former open question 4). Options: (a) a button that opens
    it; (b) open it by itself at `grid_solved`, which needs spec 026 AC-5's tests to
    close it first. Pick: (a). Already part of the spec above.
12. Dependency on spec 019's author rule (former open question 5). Options: (a)
    spec 019 keeps its rule as written; (b) the recap follows a changed rule.
    Settled: (a). Spec 019 keeps the author as the player of the last
    `letter_changed` (the undoer and the confirmer credited, nobody for a reveal),
    and the neutral band for authors who are no longer in the room, so AC-2 and the
    swatch rule stand as written. What changed: with spec 032's seat back (its
    decision 11), a player who times out and comes back with their token keeps one
    id, so their letters and words count once. "Players" now lists a player id with
    several `player_joined` entries once, "Team" follows that order, and the edge
    case "Rejoined players" says so. (Note from the lead, 2026-10-16: "the neutral
    band" is a hatched band since 2026-10-15 (spec 019's decision 10), no longer a
    plain one. The swatch follows it, and AC-2 gained a check for it; decision 13
    (first review of spec 028).)

Decided by the lead on 2026-10-16, after the first review of spec 028, under the
human's delegation of accessibility choices. Each one is already part of the spec
above. (Note from the lead, 2026-10-16: this group was added (first review of spec
028).)

13. A departed player's swatch (AC-2). Options: (a) a plain grey, as this spec
    first said ("a neutral grey that is none of the eight player colours"; the
    first build drew `#767676`); (b) spec 019's hatching, the diagonal stripes of
    greys that its decision 10 gave a departed author's band on 2026-10-15. Pick:
    (b). A plain mid-grey has almost the lightness of red, teal and olive, so
    colour-blind players read it as a player colour, which is the finding that made
    spec 019 hatch its band. The recap thus shows a player who is no longer in the
    room the way the authors view does, and the swatch differs from every
    player's by its pattern, not by its colour (a player's swatch has a
    `background-image` of `none`). It is one hatching shared by every departed
    player; their nicknames, always written (decision 7), tell them apart.

## Open questions

None.
