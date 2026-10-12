---
id: "020"
title: Pencil letters
status: approved
---

# 020 - Pencil letters

Epic E5 Collaboration aids (US-5.2) · Release: V1 · Epic depends on: E4

## Goal

As a player, I want to mark a guess as uncertain, so that others don't build on it blindly.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-5.2.1) A letter typed in pencil mode shows in grey italics for every player.
- **AC-2** (AC-5.2.2) Any player can confirm a pencil letter with one action; it then shows as a normal letter.
- **AC-3** (AC-5.2.3) Completion (spec 026, backlog US-6.4) evaluates pencil and normal letters the same way.

## Edge cases and errors

Note from the lead (2026-10-11, from the spec 037 review): `pencil_edit` and
`confirm_pencil` are counted by the rate limit (spec 037) but do not yet go
through checks 2 to 5 of spec 015's order. This spec must route them through
the same edit checks, so a refused pencil edit (for example on a clue cell)
is answered with its error and not counted.

Note from the lead (2026-10-12, from the spec 026 review): completion counts
pencil letters like normal letters (AC-3, backlog AC-5.2.3; spec 026's
definitions and decision 6 were amended on 2026-10-12 to match). On the
server, `_is_filled` in `src/nock/room.py` still returns False for a pencil
letter (`cell.letter is not None and not cell.pencil`); this spec must change
it so a pencil letter fills its cell, and a pencil edit that fills or
completes the grid must trigger spec 026's completion rule like any letter
change. On the client, `isGridFull` in `web/src/lib/RoomPage.svelte` (around
line 229) checks only `cell.letter !== null`, so it already counts pencil
letters towards the `full_wrong` banner, which is now right; it needs no
change. `pencil_edit` and `confirm_pencil` are refused with `grid_solved` once the
grid is solved; until this spec defines its own checks, only the rate limit
comes before that refusal. This spec must place its own refusals before
`grid_solved`, in the order spec 026 sets.

- AC-3 depends on behaviour owned by spec 026; test only this spec's side of it here.

## Out of scope

- Voice and video (epic E5).
- Authorship view: spec 019.
- Clue flag: spec 021.
- Chat and reactions: spec 022.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
