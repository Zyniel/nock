---
id: "022"
title: Chat and reactions
status: draft
---

# 022 - Chat and reactions

Epic E5 Collaboration aids (US-5.4) · Release: V1 · Epic depends on: E4

## Goal

As a player, I want to talk to the room, so that we can share half-ideas without leaving the grid.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-5.4.1) The room has a text chat. Messages are at most 280 characters and arrive in the same order for everyone.
- **AC-2** (AC-5.4.2) A reaction from a set of 5 appears on a chosen word for 3 seconds.
- **AC-3** (AC-5.4.3) The chat can be collapsed and then shows an unread count.
- **AC-4** (AC-5.4.4) The host can mute a player's chat. Messages are deleted when the room expires.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Voice and video (epic E5).
- Authorship view: spec 019.
- Pencil letters: spec 020.
- Clue flag: spec 021.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
