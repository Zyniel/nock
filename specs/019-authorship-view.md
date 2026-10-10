---
id: "019"
title: Authorship view
status: approved
---

# 019 - Authorship view

Epic E5 Collaboration aids (US-5.1) · Release: V1 · Epic depends on: E4

## Goal

As a player, I want to see who wrote each letter, so that I know whom to ask about a doubtful answer.

These four aids give back what a shared paper grid offers for free: seeing who wrote what, writing lightly, pointing at a clue and talking.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-5.1.1) An "authors" switch tints each filled cell with the colour of the last player who edited it.
- **AC-2** (AC-5.1.2) With the switch off, all letters share one neutral colour.
- **AC-3** (AC-5.1.3) Authorship survives reconnection and feeds the recap (spec 028, backlog US-7.2).

## Edge cases and errors

- AC-3 depends on behaviour owned by spec 028; test only this spec's side of it here.

## Out of scope

- Voice and video (epic E5).
- Pencil letters: spec 020.
- Clue flag: spec 021.
- Chat and reactions: spec 022.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
