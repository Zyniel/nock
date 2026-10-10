---
id: "004"
title: Grid catalogue
status: approved
---

# 004 - Grid catalogue

Epic E1 Grid content and model (US-1.3) · Release: MVP · Epic depends on: None
The FX-01 reference grid is in `specs/_reference.md`. The stack and modeling rules
are in `specs/_architecture.md`. The server, routes, i18n and test harness this
spec extends are those of spec 040.

## Goal

As a player, I want to browse grids by difficulty and size, so that I pick one that suits my group.

Every other epic reads the grid through this model, so it ships first.

Where real grids come from (commission, licence, or generate and review) is decided
before launch and does not block this spec: it is built and tested with FX-01 and
test fixtures. Source, author and licence fields belong to spec 005.

## Public interface

### Python: `src/nock/catalogue.py`

Every name below is importable from `nock.catalogue`.

```python
# src/nock/catalogue.py
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from nock.grid import Grid

GridNumber = Annotated[int, Field(ge=1, le=999_999_999, strict=True)]
Force = Annotated[int, Field(ge=1, le=4, strict=True)]

GRIDS_DIR: Path  # <repository root>/grids, computed from the module file


class CatalogueEntry(BaseModel):
    """One grid of the catalogue and its listing data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: GridNumber          # catalogue number, unique in a catalogue
    published_on: date          # publication date; JSON "YYYY-MM-DD"
    force: Force                # difficulty, 1 (easy) to 4 (hard)
    published: StrictBool       # False: hidden from players (AC-4)
    grid: Grid


class GridSummary(BaseModel):
    """What a player may see of a grid in the catalogue: never the clues."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: GridNumber
    published_on: date
    force: Force
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    word_count: int = Field(ge=1, strict=True)


def summarize(entry: CatalogueEntry) -> GridSummary:
    """Return the summary of `entry`.

    `width` and `height` are those of `entry.grid`; `word_count` is the number of
    clues in the grid (one word per clue, as `ImportReport.word_count` of spec 003).
    """


class Catalogue(BaseModel):
    """Every grid this server knows, published or not."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[CatalogueEntry, ...] = ()
    # A model validator (mode="after") rejects two entries with the same number:
    # ValueError whose message contains "duplicate" and the number.

    def published_summaries(self, force: int | None = None) -> list[GridSummary]:
        """Summaries of the published entries, newest first.

        Order: `published_on` descending, then `number` descending.
        With `force`, only the entries of that force; a force with no entry
        gives an empty list.
        """

    def find_published(self, number: int) -> CatalogueEntry | None:
        """Return the published entry `number`, or None when it is unknown or
        unpublished."""


class CatalogueError(ValueError):
    """A catalogue directory holds a file that cannot be loaded."""


def load_catalogue(directory: Path) -> Catalogue:
    """Load every `*.json` file directly inside `directory`, in file-name order.

    A missing directory gives an empty catalogue. Sub-directories and files with
    another extension are ignored.

    Raises:
        CatalogueError: at the first file that is not valid (see "Catalogue
            files"), or when two files hold the same number. The message
            contains the file name; it is raised `from` the original error.
    """
```

### Catalogue files

One file per grid, a JSON object with exactly these keys:

```json
{"number": 1, "published_on": "2026-10-01", "force": 2, "published": true,
 "grid": {"width": 5, "height": 5, "cells": ["... spec 002 format ..."]}}
```

`load_catalogue` reads the object, runs `import_grid` (spec 003) on the JSON text of
`grid` (so a grid that `import_grid` rejects makes the file invalid), and builds the
`CatalogueEntry` with `report.grid`. An unknown key, a missing key or a value that
breaks a field constraint makes the file invalid. Spec 005 adds its own keys
(author, source, licence) to this format.

### Python: `src/nock/server.py` (changes to spec 040)

```python
from nock.catalogue import Catalogue

GRID_NUMBER_PATTERN: str = r"^[1-9][0-9]{0,8}$"


def create_app(
    rooms: RoomRegistry | None = None,
    dist_dir: Path | None = None,
    catalogue: Catalogue | None = None,
) -> FastAPI:
    """As in spec 040. catalogue: the grids served. None: Catalogue() (empty)."""


app: FastAPI  # create_app(catalogue=load_catalogue(GRIDS_DIR))
```

Every route and rule of spec 040 stays. New HTTP routes:

| Method and path | Answer |
| --- | --- |
| `GET /api/grids` | 200, JSON array of `GridSummary` (`model_dump(mode="json")` of each), `catalogue.published_summaries()` |
| `GET /api/grids?force=N`, `N` an integer 1 to 4 | 200, the same array filtered on that force |
| `GET /api/grids?force=X`, `X` not an integer 1 to 4 (`0`, `5`, `x`, empty) | 422, FastAPI's validation body |
| `GET /api/grids/{number}`, `number` matching `GRID_NUMBER_PATTERN` and published | 200, one `GridSummary` JSON object |
| `GET /api/grids/{number}`, unknown, unpublished, or not matching the pattern (`0`, `01`, `abc`, `-1`) | 404, `{"detail": "Not Found"}` |
| `GET /g/{number}`, published | `index.html` as for `/r/{code}` (503 when the client is not built) |
| `GET /g/{number}`, unknown, unpublished, or not matching the pattern | 404, `{"detail": "Not Found"}`, never `index.html` |

A summary in JSON, the only grid data these routes return:
`{"number": 1, "published_on": "2026-10-01", "force": 2, "width": 5, "height": 5, "word_count": 8}`.

### Client: `web/`

Routing (spec 040) gains one route: `/g/<number>` (number matching
`^[1-9][0-9]{0,8}$`) shows the grid page. `/` stays the catalogue page.

Catalogue page, root `data-testid="catalogue-page"` (spec 040), now with
`data-state`: `loading` until `GET /api/grids` answers, then `ready`, or `error`
when the request fails or the answer is not a JSON array. It keeps the heading
`t("catalogue.heading")`.

- Force filter: five buttons `data-testid="force-filter"` with `data-force` `all`,
  `1`, `2`, `3`, `4`, in that order, labelled `t("catalogue.filter.all")` and
  `t("catalogue.filter.force", { force })`. The selected one has
  `aria-pressed="true"`, the others `aria-pressed="false"`. `all` is selected on
  load. Selecting a force shows only the grids of that force; the client may filter
  locally or call `?force=N`.
- List `data-testid="catalogue-list"` holding one `data-testid="catalogue-item"`
  per shown grid, in the order of `GET /api/grids` (newest first). Each item has:

  | Attribute | Value |
  | --- | --- |
  | `data-number` | the number in decimal |
  | `data-published-on` | `YYYY-MM-DD` |
  | `data-force` | `1` to `4` |
  | `data-width`, `data-height` | decimal |
  | `data-word-count` | decimal |
  | `data-progress` | `none`, `started` or `finished` (AC-3) |

  and shows `t("catalogue.item.number", { number })`,
  `t("catalogue.item.published", { date })`, `t("catalogue.item.force", { force })`,
  `t("catalogue.item.size", { width, height })` and
  `t("catalogue.item.words", { count })`. `date` is the publication date written by
  `new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" })`
  on the UTC midnight of that date, for example `1 octobre 2026`. When
  `data-progress` is not `none`, the item holds `data-testid="catalogue-progress"`
  showing `t("catalogue.progress.started")` or `t("catalogue.progress.finished")`;
  otherwise it holds no such element.
- With no published grid at all, the page shows `t("catalogue.empty")` and no item.
  With grids but none of the selected force, it shows `t("catalogue.empty_filtered")`.
  While loading it shows `t("catalogue.loading")`; on error `t("catalogue.error")`.

Grid page, root `data-testid="grid-page"`, `data-state` as above, filled from
`GET /api/grids/<number>`: one `catalogue-item` with the same attributes and texts.
When that request answers 404, the page shows `t("not_found.heading")` and
`data-state="not_found"`.

Progress on this device (AC-3) is read from `localStorage` key `nock.progress`: a
JSON object whose keys are grid numbers in decimal and whose values are `"started"`
or `"finished"`, for example `{"1": "started", "2": "finished"}`. A grid with no
key, or with any other value, is `none`. A missing key, text that is not JSON, or
JSON that is not an object is read as `{}`. This spec only reads the key; spec 010
writes it.

New `fr.json` keys (proposed wording):

| Key | Value |
| --- | --- |
| `catalogue.loading` | `Chargement…` |
| `catalogue.error` | `Impossible de charger les grilles.` |
| `catalogue.empty_filtered` | `Aucune grille de cette force.` |
| `catalogue.filter.label` | `Force` |
| `catalogue.filter.all` | `Toutes` |
| `catalogue.filter.force` | `Force {force}` |
| `catalogue.item.number` | `Grille n° {number}` |
| `catalogue.item.published` | `Publiée le {date}` |
| `catalogue.item.force` | `Force {force}` |
| `catalogue.item.size` | `{width} × {height}` |
| `catalogue.item.words` | `{count} mots` |
| `catalogue.progress.started` | `Commencée` |
| `catalogue.progress.finished` | `Terminée` |

`catalogue.filter.label` labels the filter group (`aria-label`).

### Test harness

- Python and HTTP criteria build catalogues in code, reusing the FX-01 grid
  (`Grid.model_validate_json(fx01_text)`) for several entries with different
  numbers, dates, forces and `published` values. HTTP tests use
  `TestClient(create_app(catalogue=..., dist_dir=tmp_path))` as in spec 040.
- The test-writer adds to `tests/conftest.py` a function-scoped `catalogue` fixture
  returning `Catalogue()`, and passes it to `create_app` in `live_server`. A test
  module that needs grids overrides `catalogue` with its own fixture. Spec 040's
  tests are unchanged by this.
- Reference catalogue `CAT` used below (all on FX-01): entry 1, `2026-09-01`,
  force 1, published; entry 2, `2026-10-01`, force 2, published; entry 3,
  `2026-10-01`, force 1, published; entry 4, `2026-10-05`, force 3, **unpublished**.
- Progress is seeded in browser tests with
  `context.add_init_script("localStorage.setItem('nock.progress', '...')")`
  before `page.goto`.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-1.3.1) (Python, HTTP, browser with live server) Each grid lists its number, publication date, force, dimensions and word count. Python: `summarize` of entry 2 of `CAT` is `GridSummary(number=2, published_on=date(2026, 10, 1), force=2, width=5, height=5, word_count=8)`. HTTP: `GET /api/grids/2` answers 200 with exactly `{"number": 2, "published_on": "2026-10-01", "force": 2, "width": 5, "height": 5, "word_count": 8}`. Browser: on `/` with `CAT`, the item with `data-number="2"` has `data-published-on="2026-10-01"`, `data-force="2"`, `data-width="5"`, `data-height="5"`, `data-word-count="8"` and contains the texts `Grille n° 2`, `1 octobre 2026`, `Force 2`, `5 × 5` and `8 mots` (built from `fr.json`).
- **AC-2** (AC-1.3.2) (Python, HTTP, browser with live server) The list filters by force and sorts newest first by default. With `CAT`: `published_summaries()` gives the numbers `[2, 3, 1]` (2 and 3 share a date, the higher number first); `published_summaries(force=1)` gives `[3, 1]`; `published_summaries(force=4)` gives `[]`. `GET /api/grids` and `GET /api/grids?force=1` answer the same numbers in the same order. In the browser, `/` lists items `2, 3, 1` with `all` pressed; after clicking the `data-force="1"` filter, items `3, 1` with that filter pressed; after clicking `data-force="4"`, no item and the text `t("catalogue.empty_filtered")`.
- **AC-3** (AC-1.3.3) (browser with live server) A grid I started or finished shows that status on my device or account. With `CAT` and `nock.progress` seeded to `{"1": "started", "2": "finished", "99": "started"}`, item 1 has `data-progress="started"` and its `catalogue-progress` shows `fr.json["catalogue.progress.started"]`, item 2 has `data-progress="finished"` and shows `fr.json["catalogue.progress.finished"]`, item 3 has `data-progress="none"` and no `catalogue-progress` element. The same status shows on the grid page `/g/1`.
- **AC-4** (AC-1.3.4) (Python, HTTP, browser with live server) An unpublished grid is absent from the list and its direct URL returns "not found". With `CAT`: no summary of `published_summaries()` has number 4 and `find_published(4)` is None; `GET /api/grids` does not list 4; `GET /api/grids/4`, `GET /g/4` and `GET /g/99` answer 404 with `{"detail": "Not Found"}` while `GET /g/2` answers 200 with `index.html`; in the browser no `catalogue-item` has `data-number="4"`.
- **AC-5** (new) (Python) Catalogue files load as described in "Catalogue files". Given a directory holding `b.json` (number 2) and `a.json` (number 1), each wrapping the FX-01 grid, `load_catalogue` returns entries numbered `1` then `2` (file-name order) whose grids equal `Grid.model_validate_json(fx01_text)`; a missing directory returns `Catalogue()`; a file whose grid is FX-01 with the answer `MIME` changed to `MIMA` raises `CatalogueError` whose message contains that file's name and `__cause__` is a `GridImportError`.
- **AC-6** (new) (browser with live server) The grid page shows one grid by its direct URL. With `CAT`, opening `/g/2` shows `data-testid="grid-page"` with `data-state="ready"` and one `catalogue-item` with the attributes of AC-1.

## Edge cases and errors

- No answers leave the server (AC-1, AC-4): the bodies of `GET /api/grids` and
  `GET /api/grids/2` contain none of `"answer"`, `"cells"`, `"clues"`, `TAMIS`,
  `NAVAL`, `MIME`, `IDES`, `SENT`, `VIDE`, `AMEN`, `LEST`.
- Duplicate numbers (AC-5): `Catalogue(entries=(e1, e1_copy))` with the same
  number raises `pydantic.ValidationError` whose message contains `duplicate` and
  the number; two files with the same number make `load_catalogue` raise
  `CatalogueError` naming the second file.
- Invalid files (AC-5): text that is not JSON, a missing `force`, `"force": 5`,
  `"force": "2"`, `"number": 0`, `"published": "yes"`, `"published_on": "01/10/2026"`
  or an extra key `"colour"` each raise `CatalogueError` naming the file.
- Ignored files (AC-5): `notes.txt` and a sub-directory `old/` holding a `.json`
  file are not loaded.
- Empty catalogue (AC-1, AC-2): `GET /api/grids` answers `[]`; the page shows
  `t("catalogue.empty")`, `data-state="ready"`, no list item, and the filter
  buttons are still shown.
- Force query (AC-2): `?force=0`, `?force=5`, `?force=x` and `?force=` answer 422;
  an unknown query parameter is ignored. In Python,
  `published_summaries(force=5)` returns `[]` (no entry can have force 5).
- Grid number paths (AC-4): `/api/grids/0`, `/api/grids/01`, `/api/grids/abc`,
  `/g/0`, `/g/01` and `/g/1234567890` (10 digits) answer 404 JSON;
  `/api/grids/` and `/g/2/` answer 404 JSON with no redirect (spec 040 AC-28).
- Unbuilt client (AC-4): `GET /g/2` answers 503 as `/r/{code}` does in spec 040;
  `GET /g/4` (unpublished) still answers 404.
- Catalogue request failure (AC-1): when `GET /api/grids` answers 500 (forced with
  `page.route`), the page reaches `data-state="error"` and shows
  `t("catalogue.error")`.
- Corrupt progress (AC-3): `nock.progress` set to `not json`, `[1]`, or
  `{"1": "done"}` shows every item with `data-progress="none"`, and the page still
  reaches `data-state="ready"`.
- Same date (AC-2): ties are broken by number, higher first; dates are compared as
  dates, so `2026-10-01` is newer than `2026-09-30`.
- Date display (AC-1): the date is shown in UTC, so `2026-10-01` reads
  `1 octobre 2026` whatever the browser's time zone.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Grid schema: spec 002.
- Grid validation at import: spec 003.
- Licensed content only: spec 005 (source, author and licence fields, withdrawing a
  grid).
- Writing `nock.progress` (spec 010), progress on an account (spec 033) and game
  history (spec 029).
- Starting a game from the catalogue (spec 010).
- Sorting other than newest first, searching, paging, and filtering by size.
- Reloading the catalogue while the server runs: the catalogue is read once at
  start.
- Real grid content in `grids/`: the directory may be absent.

## Work packages

None.

## Open questions

Each pick below is already written into the spec. The lead confirms or changes it.

1. Where grids live. Options: one JSON file per grid in a directory, the SQLite
   store of spec 018, or Python code. Pick: one file per grid in `grids/`
   (`GRIDS_DIR`), loaded once at start by `load_catalogue`, a missing directory
   being an empty catalogue; tests pass a `Catalogue` to `create_app`.
2. Catalogue number. Pick: an integer 1 to 999,999,999, unique, used in URLs
   (`/g/<number>`, `/api/grids/<number>`).
3. "Unpublished". Options: an explicit `published` flag, or a publication date in
   the future. Pick: the flag; a published grid with a future date is listed.
4. Force range. The glossary says "commonly 1 to 4". Pick: exactly 1 to 4.
5. Sort options. "Newest first by default" suggests other orders. Pick: newest
   first only (ties: higher number first); other orders are out of scope.
6. Direct URL of a grid. Options: only an API path, or a page. Pick: a page
   `/g/<number>` (server 404 when unpublished) backed by `GET /api/grids/<number>`;
   the server knows the catalogue, so "not found" is a real 404 as spec 040
   decision 4 intended.
7. Invalid force query. Options: 422 (FastAPI default) or ignore the filter. Pick:
   422.
8. Progress status on this device. No account exists in the MVP. Pick: a
   `localStorage` key `nock.progress` read by this spec and written by spec 010;
   "on my account" waits for spec 033.
9. Coordination: spec 011 (written in parallel) may also change `create_app`.
   Pick: this spec adds only the keyword argument `catalogue`; the lead merges it
   with 011's changes.
