---
id: "005"
title: Licensed content only
status: draft
---

# 005 - Licensed content only

Epic E1 Grid content and model (US-1.4) · Release: MVP · Epic depends on: None

## Goal

As the product owner, I want every grid tied to a source and a licence, so that we publish only what we may use.

Every other epic reads the grid through this model, so it ships first.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-1.4.1) Import refuses a grid with no author, source or licence field.
- **AC-2** (AC-1.4.2) No component fetches grids from a third-party site, at run time or in a batch.
- **AC-3** (AC-1.4.3) When a grid is withdrawn, open rooms on it can finish and no new room can start.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Grid schema: spec 002.
- Grid validation at import: spec 003.
- Grid catalogue: spec 004.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Grid source (open decision in the backlog): commission an author, license from a publisher, or generate and review. This blocks E1.
- AC-2 is a rule about the whole codebase. How is it tested: a test that scans the code for outgoing HTTP calls, or a review checklist item?
