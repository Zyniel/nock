---
area: content
file: library
status: done
---

# content/library - The catalogue « Grilles » and the grid page

## Purpose

A player browses the published grids on « Grilles », filters them by force,
and opens one grid by its own link `/g/<number>`; each grid shows as a card
(`content/cards.md`). The grid APIs feed both pages and never send a clue or
an answer.

## Depends on

- `content/grid-files.md`: the index, the number, published and withdrawn.
- `content/cards.md`: the grid card, its progress and « Jouer ».
- `account/account.md`: the sign-in status; the account's progress is
  `account/erasure.md`.

## Rules

### Listed grids and their summary

1. A grid is listed when its index entry says published and not withdrawn
   (`content/grid-files.md` rule 13); a publication date in the future is listed.
2. A summary is exactly `number`, `published_on` (a calendar date,
   `YYYY-MM-DD`), `force`,
   `width`, `height` and `word_count` (the number of clues). No grid route sends
   anything else of a grid: no cell, clue, answer or credit.

### Grid APIs

3. `GET /api/grids` answers 200 with the summaries of the listed grids, newest
   publication date first (compared as dates), then higher number first; `[]`
   when none.
4. `?force=N`, with `N` exactly one of the characters `1`, `2`, `3`, `4`, keeps
   the grids of that force (`[]` when none). Any other value answers 422 with
   FastAPI's validation body. An unknown query parameter is ignored.
5. `GET /api/grids/<n>` answers 200 with one summary when `<n>` matches
   `^[1-9][0-9]{0,8}$` and is listed; otherwise 404 `{"detail": "Not Found"}`.
6. `GET /g/<n>` makes the same check: a listed grid gets the client's
   `index.html` (503 while the client is not built); anything else gets 404
   `{"detail": "Not Found"}`, never `index.html`, built or not. A trailing slash
   (`/api/grids/`, `/g/2/`) is 404 with no redirect.

### The catalogue page `/`

8. The page asks `GET /api/grids` once. It is loading until the answer, then
   ready, or in error when the request fails, answers another status than 2xx,
   or answers anything but a list of summaries. The heading « Grilles »
   (`catalogue.heading`) shows in every state. Once `GET /api/account` has
   answered signed in (`account/account.md` rule 13), it asks `GET
   /api/account/progress` once; signed out, never (proven by
   `content/cards.md` AC-9).
9. Its column holds, in order: the heading, « Mes salons » when it shows
   (`lobby/summaries.md`), the force filter, then one state line or the cards
   (`content/cards.md`), then « Grilles terminées » when it shows
   (`gameplay/history.md`). By state:

   | State | After the heading |
   | --- | --- |
   | loading | muted line `catalogue.loading`; no filter, no card |
   | error | error line `catalogue.error`; no filter, no card |
   | ready, no grid | muted line `catalogue.empty`; no filter |
   | ready, no grid of the force | filter, muted `catalogue.empty_filtered` |
   | ready, grids shown | filter, then the cards; no state line |

   No state shows a spinner, a progress bar or an animation.
10. The force filter is a group named by its visible label
    `catalogue.filter.label` (« Force »), then five toggle buttons in this
    order: « Toutes » (`catalogue.filter.all`), « Force 1 » to « Force 4 »
    (`catalogue.filter.force`). Exactly one is pressed (`aria-pressed`),
    « Toutes » on load. Pressing « Force N » shows the loaded grids of force N
    in the same order, with no new request; « Toutes » shows them all again.
11. The top bar holds the brand only (`client/shell.md` rule 17), plain text
    here, plus « Compte » while accounts are on (`account/account.md`).

### The grid page `/g/<n>`

16. The page asks `GET /api/grids/<n>` and, once, `GET /api/account/progress`
    (`content/cards.md` rule 1), nothing else of the grids or of the account
    (proven by `content/cards.md` AC-8). It shows, under a top bar holding the
    brand only (no « Compte », accounts on or off) and with no heading, filter,
    « Mes salons » or « Grilles terminées »: the muted line `catalogue.loading`
    while loading, then the grid's one card as on the catalogue
    (`content/cards.md`; progress, drawing and « Jouer » included); the error
    line `catalogue.error` when the request fails, answers another status than
    2xx or 404, or answers anything but a summary; the muted line
    `not_found.heading` (« Page introuvable ») and no card on a 404.

### Baselines

17. Both pages keep the baselines of `product.md`: keyboard reach, visible
    focus, contrast and language, at its windows.

### Look

- The brand bar and column of both pages and the filter chips:
  `_design/pages.md`, « Catalogue », with `_design/foundation.md`,
  « Components » (brand link, plain on the catalogue).
- The state lines: `_design/pages.md`, « States: opening, loading, empty,
  error ».

## Acceptance criteria

The examples use CAT, four grids on FX-01: 1 (`2026-09-01`, force 1), 2
(`2026-10-01`, force 2), 3 (`2026-10-01`, force 1), all published, and 4
(`2026-10-05`, force 3) unpublished.

- **AC-1** With CAT, `GET /api/grids/2` answers 200 with exactly `{"number": 2,
  "published_on": "2026-10-01", "force": 2, "width": 5, "height": 5,
  "word_count": 8}`; every item of `GET /api/grids` has those six keys, and
  neither body holds `"cells"`, `"clues"`, `"answer"`, `MIME` or `LEST`.
  (← 004 AC-1)
- **AC-2** With CAT, `GET /api/grids` lists 3, 2, 1, `?force=1` lists 3, 1,
  `?force=4` and `?force=3` answer `[]`, `?colour=red` lists 3, 2, 1, and an
  empty catalogue answers `[]`; `2026-10-01` comes before `2026-09-30`; a
  published grid dated `2999-01-01` is listed. (← 004 AC-1, 004 AC-2,
  004 AC-4)
- **AC-3** `?force=1` answers 200, while `0`, `5`, `x`, an empty value, `2.0`,
  `01`, ` 1`, `+1` and `1 ` each answer 422 with a `detail`. (← 004 AC-2,
  004 AC-7)
- **AC-4** With CAT, `/api/grids/4`, `/g/4`, `/g/99`, `/api/grids/0`, `/g/01`,
  `/g/abc`, `/g/1234567890` and `/g/2/` answer 404 `{"detail": "Not Found"}`
  with no redirect; `/g/2` and a listed `/g/999999999` serve `index.html`; with
  the client not built `/g/2` answers 503 and `/g/4` still 404.
  (← 004 AC-4)
- **AC-5** With CAT, `/` lists cards 3, 2, 1 with « Toutes » pressed and no
  card 4; card 2 shows « Grille n° 2 », « 1 octobre 2026 », « Force 2 »,
  « 5 × 5 » and « 8 mots », with the same date in the time zones of Kiritimati
  and Pago Pago. (← 004 AC-1, 004 AC-2, 004 AC-4)
- **AC-6** The filter group is named « Force » by its visible label and holds
  « Toutes », « Force 1 » to « Force 4 »; pressing « Force 1 » shows 3, 1 with
  it alone pressed; « Force 4 » shows no card and « Aucune grille de cette
  force. »; « Toutes » shows 3, 2, 1 again. After each press, in any order,
  the chip just pressed is the only one with `aria-pressed="true"`: after
  « Force 4 » then « Force 2 », only « Force 2 ». From the page's load through
  all these presses, `/` has made one request to `/api/grids`, with no query,
  and none other to it (`?force=` included). The label and
  the chips, pressed or not, follow the catalogue design ("Look").
  (← 004 AC-2, 046 AC-4)
- **AC-9** While `GET /api/grids` has not answered, the page is loading and
  shows « Grilles » and « Chargement… » as a muted line under it, with no
  filter and no card. (← 004 AC-1, 046 AC-9)
- **AC-10** When `GET /api/grids` answers 500, or answers `{}`, the page is in
  error and shows « Impossible de charger les grilles. » as an error line, with
  no filter and no card. (← 004 AC-1, 046 AC-9)
- **AC-11** An empty catalogue shows « Aucune grille pour le moment. » as a
  muted line and no filter; « Force 4 » on CAT keeps the filter, followed by
  « Aucune grille de cette force. », muted; in none of the four states is there
  a progress bar or an animation, and with cards shown there is no state line.
  (← 004 AC-1, 046 AC-9)
- **AC-12** On a computer and on a phone, with accounts off, `/` holds the
  brand bar with the brand alone in it, then the column: « Grilles », the
  filter, the cards, laid out by the catalogue design. (← 046 AC-2)
- **AC-17** `/g/2` asks `GET /api/grids/2` first and shows one card of grid 2,
  with the texts of AC-5, in the card design, under a brand bar with no
  « Compte » while accounts are on, and no heading; it has its drawing on a
  computer, none on a phone; `/g/3` shows grid 3. (← 004 AC-6, 046 AC-14)
- **AC-18** When `GET /api/grids/2` answers 404, `/g/2` shows « Page
  introuvable » and no card; when it answers 500, « Impossible de charger les
  grilles. » as an error line. While `GET /api/grids/2` has not answered,
  `/g/2` shows « Chargement… » as a muted line and no card.
  (← 004 AC-6, 046 AC-14)
- **AC-19** On `/` the brand is plain text read « Nock »: the top bar holds no
  link, Tab never stops on the brand, nothing on the page carries
  `aria-current`, and on a computer the hovered brand keeps its look at rest.
- **AC-20** On `/g/2` on a computer, the hovered brand takes the hover look of
  « Brand link » (`_design/foundation.md`, « Components »), its Nock mark and
  « Nock » where they are at rest.
- **AC-21** On `/g/2` the brand is the link « Accueil » to `/` with no
  `aria-current`; following it loads the catalogue, which asks
  `GET /api/grids`.
- **AC-25** When `GET /api/grids` answers CAT's list with grid 2's
  `published_on` `2026-02-30` or `hier`, `/` shows « Impossible de charger les
  grilles. » with no filter and no card; when `GET /api/grids/2` answers that
  summary, `/g/2` shows the same error line. So do `/` and `/g/2` when grid 2's
  item, in CAT's list or as `GET /api/grids/2`'s answer, lacks `word_count`,
  and `/g/2` when `GET /api/grids/2` answers `[]`.

## Edge cases

- Two grids of the same date: the higher number comes first (AC-2).
- A published grid dated in the future is listed (AC-2).
- A grid number of nine digits is valid; ten digits is 404 (AC-4).

## Out of scope

- Other orders than newest first, searching, paging, filtering by size.
- Showing grid credits (`content/grid-files.md` rule 11).
- Reloading the grid list while the server runs: `content/grid-files.md`.
- « Jouer », the room it creates and the writing of `nock.progress`:
  `lobby/rooms.md`. « Mes salons »: `lobby/summaries.md`. « Grilles terminées »:
  `gameplay/history.md`. « Compte » and its dialog: `account/account.md`; how
  the account's progress is derived: `account/erasure.md`.
- The frame of entry pages, the page not found, the scans of every page and
  their fit at every window: `client/shell.md`.

## Code

- `src/nock/catalogue.py`: `GridSummary`, `summarize`, `published_summaries`,
  `find_published`.
- `src/nock/server.py`: the grid routes, `GRID_NUMBER_PATTERN`,
  `FORCE_PATTERN`.
- `web/src/App.svelte`: the `/g/<n>` route. `web/src/lib/CataloguePage.svelte`,
  `GridPage.svelte`, `CatalogueFrame.svelte`, `CatalogueList.svelte`;
  `catalogue.ts` (the summary's check).
- Tests: `tests/test_library_*`, with `tests/library_harness.py`;
  `tests/test_spec_004_ac01_ac03_*` (004 AC-1, AC-2), `test_spec_004_ac04_*`,
  `test_spec_004_ac06_*`, the force tests of `test_spec_004_ac07_*`;
  `tests/test_spec_046_ac01_ac02_*` (046 AC-2), `test_spec_046_ac04_ac06_*`
  (046 AC-4), `test_spec_046_ac09_ac10_*` (046 AC-9), `test_spec_046_ac14_*`.
