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
