---
id: "005"
title: Licensed content only
status: approved
---

# 005 - Licensed content only

Epic E1 Grid content and model (US-1.4) · Release: MVP · Epic depends on: None
The catalogue, its files and its routes are those of spec 004; rooms and their
store are those of specs 011 and 018. The stack and modeling rules are in
`specs/_architecture.md`.

## Goal

As the product owner, I want every grid tied to a source and a licence, so that we publish only what we may use.

Every other epic reads the grid through this model, so it ships first.

Where real grids come from (commission an author, license from a publisher, or
generate and review) is still an open decision of the owner. It does not block
this spec: the rules below hold whatever the source, and are tested with FX-01.

## Public interface

### Python: `src/nock/catalogue.py` (changes to spec 004)

```python
# src/nock/catalogue.py
from pydantic import StringConstraints

CreditText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class CatalogueEntry(BaseModel):
    """One grid of the catalogue, its listing data and its rights."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: GridNumber
    published_on: date
    force: Force
    published: StrictBool
    author: CreditText            # new: who wrote the grid
    source: CreditText            # new: where it comes from (publisher, commission, ...)
    licence: CreditText           # new: the licence or contract that allows its use
    withdrawn: StrictBool = False  # new: True once the grid may no longer start rooms
    grid: Grid


class Catalogue(BaseModel):
    # unchanged fields and validator

    def published_summaries(self, force: int | None = None) -> list[GridSummary]:
        """As in spec 004, but a withdrawn entry is never listed."""

    def find_published(self, number: int) -> CatalogueEntry | None:
        """Return entry `number` when it is published and not withdrawn, else None."""


def load_catalogue(directory: Path) -> Catalogue:
    """As in spec 004. A file without `author`, `source` or `licence`, or with one
    of them empty or blank once stripped, or longer than 200 characters, raises
    CatalogueError naming the file (raised `from` the pydantic ValidationError,
    whose text names the field)."""
```

`GridSummary`, `summarize` and every HTTP route of spec 004 keep their exact
shape: credits are not sent to players by this spec.

### Catalogue files (changes to spec 004)

One JSON object per file with these keys; `withdrawn` is optional (default
`false`), every other key is required, and an unknown key is still an error:

```json
{"number": 1, "published_on": "2026-10-01", "force": 2, "published": true,
 "author": "Équipe Nock", "source": "Commande Nock 2026", "licence": "Contrat d'auteur Nock n° 1",
 "withdrawn": false,
 "grid": {"width": 5, "height": 5, "cells": ["... spec 002 format ..."]}}
```

`author`, `source` and `licence` are free text (1 to 200 characters after
stripping spaces at both ends). `withdrawn` is a strict boolean.

### Withdrawing a grid

The operator sets `"withdrawn": true` in the grid's file and restarts the server
(the catalogue is read once at start, spec 004). From then on:

- the grid is absent from `GET /api/grids`, and `GET /api/grids/<n>`, `GET /g/<n>`
  and `POST /api/rooms` with `grid_number` `<n>` answer 404 (they all go through
  `find_published`);
- rooms already created on it keep working: a room holds its own copy of the grid
  (`RoomState.grid`, spec 011) and the store keeps it (spec 018), so joining,
  typing, reconnecting and reloading the room after a restart never look at the
  catalogue.

### No third-party fetching

No code under `src/` imports an HTTP client or opens an outgoing network
connection, and no code under `web/src/` names an absolute `http://` or
`https://` URL. Grids enter the product only as files in `grids/` (spec 004).

### Test harness

- Catalogue files are written to `tmp_path` by the test, wrapping the FX-01 grid
  (`json.loads(fx01_text)`) with the keys above.
- `CREDITS` below means `{"author": "Équipe Nock", "source": "Commande Nock 2026", "licence": "Contrat d'auteur Nock n° 1"}`.
- Existing tests that build a `CatalogueEntry` in code or write catalogue files
  (the test files of specs 004, 010, 011, 018 and 037) get the three credit
  fields added by this spec's test-writer, through one shared helper; their
  assertions do not change.
- HTTP and WebSocket tests use `TestClient(create_app(rooms=registry, catalogue=..., dist_dir=tmp_path))`
  as in specs 004 and 011. Two apps built on the same `RoomRegistry` share its
  rooms; this is how a test sees one room before and after a withdrawal.
- The static scans read files with Python only (`ast` for Python, text for the
  client), as spec 040's static criteria do.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-1.4.1) (Python) Import refuses a grid with no author, source or licence field. Given a catalogue directory holding one file `g1.json` with number 1 and `CREDITS`, when the file has no `author` key, or no `source` key, or no `licence` key (three runs), then `load_catalogue` raises `CatalogueError` whose message contains `g1.json` and whose `__cause__` is a `pydantic.ValidationError` naming the missing field.
- **AC-2** (AC-1.4.1) (Python) A blank credit counts as missing. Given the same file, when `author` is `""`, `"   "`, or 201 times `a`, or when `licence` is `null` or `42`, then `load_catalogue` raises `CatalogueError` naming `g1.json`; when `author` is `"  Équipe Nock  "`, then the entry loads with `author == "Équipe Nock"`.
- **AC-3** (AC-1.4.1) (Python) A complete file loads with its credits. Given `g1.json` with `CREDITS` and no `withdrawn` key, when it is loaded, then the entry has `author == "Équipe Nock"`, `source == "Commande Nock 2026"`, `licence == "Contrat d'auteur Nock n° 1"` and `withdrawn is False`; with `"withdrawn": true` it has `withdrawn is True`; with `"withdrawn": "yes"` or `"withdrawn": 1`, `load_catalogue` raises `CatalogueError` naming the file.
- **AC-4** (AC-1.4.2) (static) No server component can fetch grids from a third-party site. Every `.py` file under `src/` is parsed with `ast`; the test fails when a file imports one of the modules `httpx`, `httpx2`, `requests`, `urllib.request`, `aiohttp`, `urllib3`, `http.client`, `socket`, `ftplib` (as `import x`, `import x.y`, `from x import ...`, or `from urllib import request` / `from http import client`), or calls a function or method named `create_connection` or `open_connection`. The checker itself is checked on sample texts: each of `import httpx`, `import requests as r`, `from urllib.request import urlopen`, `from urllib import request`, `import aiohttp.client`, `from http import client`, `import socket`, `asyncio.open_connection("x", 80)` and `loop.create_connection(f, "x", 80)` is flagged; `import sqlite3`, `sqlite3.connect(path)`, `from urllib.parse import quote` and `import uvicorn` are not. The scan of today's `src/` finds nothing.
- **AC-5** (AC-1.4.2) (static) No client component can fetch grids from a third-party site. Every `.ts`, `.svelte` and `.html` file under `web/src/` and `web/index.html` is read as text; the test fails when one contains `http://` or `https://` (any case). The checker flags the sample texts `fetch("https://example.com/grids")` and `const u = 'HTTP://x'` and does not flag `` `${scheme}://${location.host}/api/rooms` `` or `fetch('/api/grids')`.
- **AC-6** (AC-1.4.3) (Python; HTTP) No new room can start on a withdrawn grid. Given a catalogue with entry 1 (`CREDITS`, published) and entry 2 (`CREDITS`, published, `withdrawn` True), both on FX-01: `published_summaries()` lists only number 1, `find_published(2)` is None; `GET /api/grids` lists only 1; `GET /api/grids/2`, `GET /g/2` and `POST /api/rooms` with `{"grid_number": 2}` answer 404 with `{"detail": "Not Found"}`, while the same requests for 1 answer 200, 200 (or 503 without a built client, as spec 040) and 201.
- **AC-7** (AC-1.4.3) (WebSocket) Open rooms on a withdrawn grid can finish. Given a registry `R` whose store is a SQLite file in `tmp_path`, app A built on `R` with entry 1 published and not withdrawn, and app B built on `R` with the same entry withdrawn: a room created with `POST /api/rooms` on app A, then, through app B, two clients join that room, type the 18 FX-01 letters between them and each `edit_letter` is answered with its `letter_changed` (no `error`), and `POST /api/rooms` with grid 1 on app B answers 404. After `R.close()`, a new registry on the same store file, served by an app built like B, still serves the room: a client joining it receives a `Snapshot` holding the 18 letters.

## Edge cases and errors

- Missing key versus unknown key (AC-1, AC-3): `"licence"` is required, `"license"`
  (American spelling) is an unknown key and makes the file invalid.
- Credits are any text (AC-2): accents, apostrophes and `n°` are kept as written
  after stripping. Line breaks inside are allowed; the 200-character limit counts
  code points.
- Withdrawn and unpublished (AC-6): an entry with `published` false and `withdrawn`
  true is hidden like any unpublished entry. `withdrawn` wins over `published`
  true.
- Withdrawn grid already open in a browser (AC-7): `/r/<code>` is served whatever
  the catalogue holds (spec 040), so a player who has the room link can still
  join it. Only new rooms are refused.
- Progress on this device (AC-6): a withdrawn grid marked `started` in
  `nock.progress` is simply no longer listed; nothing is deleted.
- A file in `grids/` refused at start (AC-1, AC-2): `load_catalogue` raises, so the
  server does not start with an unlicensed grid (spec 004 behaviour for invalid
  files).
- Static scan scope (AC-4): `tests/` and `scripts/` are not scanned (tests use
  `httpx2` through the FastAPI test client, and tooling is not a product
  component). `src/nock/__main__.py`, if a later spec adds it, is scanned like
  every other file; starting uvicorn is serving, not fetching.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Grid schema: spec 002.
- Grid validation at import: spec 003.
- Grid catalogue: spec 004.
- Choosing the grid source (commission, publisher licence, or generate and
  review): an owner decision outside the code.
- Showing the author or source to players (a credits line on the catalogue or
  the room page). The fields exist; displaying them is a later story.
- Withdrawing a grid without a restart, and closing rooms already open on it.
- Deleting stored rooms or history of a withdrawn grid (spec 038 owns retention).
- Checking that a licence is valid or not expired: the text is recorded, not
  interpreted.

## Work packages

None.

## Decisions

Decided by the lead on 2026-10-11, under the owner's delegation of technical
decisions. Each one is already part of the spec above.

1. Where the credits live. Options: on the `Grid` model (spec 002) or on the
   catalogue entry (spec 004). Pick: on `CatalogueEntry` and its file, as spec 004
   announced; `Grid` stays unchanged, so FX-01, FX-02 and every grid test are
   untouched.
2. Credit fields. Pick: three free-text fields `author`, `source`, `licence`, each
   1 to 200 characters after stripping, required; no list of allowed licences.
3. Withdrawal. Options: reuse `published: false`, or a separate flag. Pick: a
   separate optional `withdrawn` flag (default false), so "never released" and
   "rights ended" stay distinct and a withdrawn grid cannot be re-listed by
   flipping `published`. It is applied at the next start, like every catalogue
   change.
4. "Open rooms can finish." Pick: rooms keep their own grid copy, so nothing in a
   room depends on the catalogue; the test proves it through two apps sharing one
   registry and through a reload from the store.
5. How AC-1.4.2 is tested (owner's answer, 2026-10-11). Pick: a static test that
   fails when a module under `src/` imports an HTTP client (`httpx`, `httpx2`,
   `requests`, `urllib.request`, `aiohttp`) or opens an outgoing connection. The
   lead added `urllib3`, `http.client`, `socket`, `ftplib` and the
   `create_connection` / `open_connection` calls as the ways to open one, and the
   client-side scan for absolute URLs (AC-5).
6. Credits are not sent to browsers. Pick: `GridSummary` is unchanged, so spec 004's
   exact JSON criteria still hold.

## Open questions

None. (The grid source stays an owner decision; it does not block this spec.)
