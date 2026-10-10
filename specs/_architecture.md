# Architecture

Not a spec: the quality gate ignores files starting with "_". Every spec's "Public
interface" follows this note. Decided with the human on 2026-10-10.

## Stack

| Layer | Choice |
| --- | --- |
| Game rules | Pure Python modules in `src/nock/`, no network and no database code |
| Data models | Pydantic v2 `BaseModel` by default (rules, messages, storage); see the modeling rules |
| Server | FastAPI with its WebSockets, run by uvicorn |
| Storage | SQLite: an append-only edit log per room plus snapshots |
| Client | Svelte + TypeScript, built with Vite into static files served by FastAPI |
| Tests | pytest for everything; browser criteria through pytest-playwright |

## Modeling rules

- Pydantic `BaseModel` is the default for data. It is required for every type
  that is part of a public interface, crosses a boundary (JSON, WebSocket,
  storage) or holds validated game data (grids, rooms, players, messages).
- A private value used only inside one module (an intermediate result, a value
  built in a hot loop) may be a `typing.NamedTuple` when that is lighter or
  clearer. It must stay private (leading underscore) and never be returned by a
  public function. Reviewers do not block on this choice. Do not use
  `dataclasses` or `TypedDict`.
- Models are immutable by default: `model_config = ConfigDict(frozen=True)`.
  A model that has to change is replaced, not mutated.
- A family of variants is a discriminated union on a `type` field holding a
  `Literal`, for example cell kinds or message kinds:
  `Annotated[LetterCell | ClueCell | EmptyCell, Field(discriminator="type")]`.
- Constraints live on the fields (`Field(ge=0)`, `min_length`, `max_length`,
  validators), so invalid data cannot be built at all.
- JSON in and out goes through `model_validate_json` and `model_dump_json`.
  Dictionary keys in JSON are strings, so a model never uses a tuple as a dict
  key; positions are fields (`row`, `column`) on the item instead.
- Rules that need the whole object (an arrow pointing outside the grid, two words
  disagreeing on a letter) are plain functions over validated models, not model
  validators, so each can raise an error that names the problem.

## How the server works

- The server holds the only true state of a room. Each room is handled by one
  asyncio task that applies messages in arrival order and gives each accepted
  edit a sequence number. Last edit received wins.
- A client shows its own letters at once, keeps unconfirmed edits in a queue and
  resends them after a reconnection.
- A joining client receives one snapshot with its sequence number, then every
  later event in order.
- Every event is appended to the room's log before it is broadcast. Restart
  recovery, replay and catch-up after an absence all read that log.
- Answers stay on the server. A check or reveal sends back only its result.

## Module layout (proposed)

| Module | Holds |
| --- | --- |
| `nock/grid.py` | Grid model, clue resolution, answer normalisation |
| `nock/grid_import.py` | Import checks and report |
| `nock/room.py` | Room state and the rules applied to each event |
| `nock/protocol.py` | Message models exchanged with the client |
| `nock/store.py` | SQLite log and snapshots |
| `nock/server.py` | FastAPI app and WebSocket endpoint |
| `web/` | Svelte client |

## Toolchain (in place since 2026-10-10)

- Python: `pydantic`, `fastapi`, `uvicorn[standard]`; for tests `httpx2` (used
  by the FastAPI/Starlette test client) and `pytest-playwright` (Chromium
  installed by `uv run playwright install chromium`).
- Client: Node.js LTS; `web/` was created from the Vite `svelte-ts` template.
- The full gate runs `npm --prefix web run check` (svelte-check and tsc) and
  `npm --prefix web run build` before pytest, so browser tests use the fresh
  build in `web/dist`. CI installs Node, runs `npm --prefix web ci` and installs
  Chromium first.
- The implementer may write `web/`. Its `package.json`, lock file and config
  files count as tooling: adding an npm dependency is the human's decision.
- The room events contract is spec 039 (`nock/protocol.py`).
