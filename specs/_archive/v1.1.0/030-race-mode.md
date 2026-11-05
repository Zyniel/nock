---
id: "030"
title: Race
status: approved
---

# 030 - Race

Epic E8 Game modes (US-8.1) · Release: Later · Epic depends on: E7

## Goal

As a group, we want to race on the same grid, so that we can find out who is fastest.

Cooperative play is the default and the only MVP mode; these two stories add competition later on the same engine.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-8.1.1) In race mode each player fills a private copy; no letter of another player is ever sent to my browser.
- **AC-2** (AC-8.1.2) I see each opponent's progress as a percentage of filled cells, updated within 2 seconds.
- **AC-3** (AC-8.1.3) The first player with a fully correct grid wins; the others can keep playing and get a finishing rank.
- **AC-4** (AC-8.1.4) Checks and reveals are disabled in race mode.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Ranked play and tournaments (epic E8).
- Teams: spec 031.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Competitive play (open decision in the backlog): is E8 wanted at all?
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
