---
id: "027"
title: Shared timer
status: draft
---

# 027 - Shared timer

Epic E7 Completion and recap (US-7.1) · Release: V1 · Epic depends on: E6

## Goal

As a team, we want one timer, so that we can compare our time from one grid to the next.

The recap credits contributions without turning a cooperative game into a ranking.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-7.1.1) The timer starts at the first letter typed and reads the same for all players, within 1 second.
- **AC-2** (AC-7.1.2) It pauses while no player is connected and resumes at the next connection.
- **AC-3** (AC-7.1.3) Each player can hide it on their own screen.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Public leaderboards (epic E7).
- End-of-game recap: spec 028.
- Game history: spec 029.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
