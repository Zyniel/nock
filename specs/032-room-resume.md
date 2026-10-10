---
id: "032"
title: Room resume
status: draft
---

# 032 - Room resume

Epic E9 Accounts and resume (US-9.1) · Release: V1 · Epic depends on: E3

## Goal

As a player, I want to come back to our grid tomorrow, so that a long grid doesn't need one sitting.

The MVP ships with guests only: a guest can do everything needed to finish a grid. Accounts arrive in V1 and only add memory across devices.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-9.1.1) A room stays open for 30 days after its last edit, then is deleted.
- **AC-2** (AC-9.1.2) Opening the link on another device shows the same letters, timer and hint budget.
- **AC-3** (AC-9.1.3) "My rooms" lists my open rooms with their grid, players and last activity.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Payments and subscriptions (epic E9).
- Optional account: spec 033.
- Catching up after an absence: spec 034.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
