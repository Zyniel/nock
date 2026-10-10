---
id: "028"
title: End-of-game recap
status: approved
---

# 028 - End-of-game recap

Epic E7 Completion and recap (US-7.2) · Release: V1 · Epic depends on: E6
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a player, I want to see what each of us brought, so that the win feels shared.

The recap credits contributions without turning a cooperative game into a ranking.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-7.2.1) The recap shows total time, checks used and reveals used.
- **AC-2** (AC-7.2.2) For each player it shows the final correct letters they authored and the words they completed by writing the last missing letter.
- **AC-3** (AC-7.2.3) Revealed letters are credited to nobody. Player letter counts plus revealed letters equal the grid's letter cells: 18 on FX-01.
- **AC-4** (AC-7.2.4) A share link shows the time and the team, and no letter of the solution.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Public leaderboards (epic E7).
- Shared timer: spec 027.
- Game history: spec 029.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
