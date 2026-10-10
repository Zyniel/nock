---
id: "037"
title: Integrity
status: approved
---

# 037 - Integrity

Epic E10 Quality bar (US-10.3) · Release: MVP · Epic depends on: All
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a team, we want a game nobody can shortcut, so that finishing means something.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-10.3.1) No payload sent to a browser contains an answer letter the room has not earned. An automated test inspects all traffic of a full FX-01 game.
- **AC-2** (AC-10.3.2) The server accepts an edit only if it is one A to Z letter, on a letter cell of the room's grid, from a member of the room.
- **AC-3** (AC-10.3.3) A client sending more than 20 edits a second is throttled.
- **AC-4** (AC-10.3.4) Nicknames and chat are escaped: a nickname containing an HTML tag displays as plain text.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Nothing stated in the backlog (epic E10).
- Accessibility: spec 035.
- Performance: spec 036.
- Privacy and operations: spec 038.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
