---
id: "038"
title: Privacy and operations
status: approved
---

# 038 - Privacy and operations

Epic E10 Quality bar (US-10.4) · Release: MVP · Epic depends on: All

## Goal

As the product owner, I want minimal data and clear signals, so that we stay compliant and can diagnose a bad game.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-10.4.1) A guest is stored as a nickname and a random identifier, nothing else. Playing needs no advertising cookie.
- **AC-2** (AC-10.4.2) Room data, chat included, is deleted at room expiry (spec 032 AC-1, backlog AC-9.1.1).
- **AC-3** (AC-10.4.3) A dashboard shows rooms created, players per room, completion rate, median solving time, sync latency and disconnection rate.
- **AC-4** (AC-10.4.4) An operator can replay the ordered edits of a room from the logs.

## Edge cases and errors

- AC-2 depends on behaviour owned by spec 032; test only this spec's side of it here.

## Out of scope

- Nothing stated in the backlog (epic E10).
- Accessibility: spec 035.
- Performance: spec 036.
- Integrity: spec 037.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Which tool hosts the dashboard of AC-3 (new dependency to approve)?
