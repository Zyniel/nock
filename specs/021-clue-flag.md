---
id: "021"
title: Clue flag
status: approved
---

# 021 - Clue flag

Epic E5 Collaboration aids (US-5.3) · Release: V1 · Epic depends on: E4

## Goal

As a stuck player, I want to flag a clue, so that my team-mates know where help is wanted.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-5.3.1) Flagging a clue shows a marker on its clue cell for all players and adds a line to the activity feed.
- **AC-2** (AC-5.3.2) The flag clears when every cell of the word is filled.
- **AC-3** (AC-5.3.3) A player holds one flag at a time; a new flag replaces the previous one.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Voice and video (epic E5).
- Authorship view: spec 019.
- Pencil letters: spec 020.
- Chat and reactions: spec 022.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
