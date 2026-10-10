---
id: "025"
title: Group decision on help
status: draft
---

# 025 - Group decision on help

Epic E6 Help and validation (US-6.3) · Release: V1 · Epic depends on: E4

## Goal

As a host, I want to choose how help is granted, so that the room plays at the difficulty it agreed on.

Help is decided by the server and shared by the room, so one impatient player cannot solve the grid for everyone.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-6.3.1) At room creation the host picks a help mode: free, vote or none.
- **AC-2** (AC-6.3.2) In vote mode, a reveal or a grid check needs a yes from more than half of the connected players within 20 seconds. The requester counts as a yes.
- **AC-3** (AC-6.3.3) A vote that fails or times out changes nothing and spends no budget.
- **AC-4** (AC-6.3.4) In none mode, the check and reveal controls are hidden.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Generated hints and dictionary lookups (epic E6).
- Check a letter, a word or the grid: spec 023.
- Reveal a letter or a word: spec 024.
- Completion detection: spec 026.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Does a word check need a vote too, or only a reveal and a grid check as written?
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
