---
id: "034"
title: Catching up after an absence
status: approved
---

# 034 - Catching up after an absence

Epic E9 Accounts and resume (US-9.3) · Release: V1 · Epic depends on: E3

## Goal

As a player who plays at different hours from my friends, I want to see what changed, so that I pick up where the team is.

The MVP ships with guests only: a guest can do everything needed to finish a grid. Accounts arrive in V1 and only add memory across devices.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-9.3.1) On my return, cells changed since my last visit are highlighted for 5 seconds.
- **AC-2** (AC-9.3.2) The activity feed lists words completed, checks and reveals since my last visit, newest first.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Payments and subscriptions (epic E9).
- Room resume: spec 032.
- Optional account: spec 033.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
