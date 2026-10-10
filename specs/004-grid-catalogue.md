---
id: "004"
title: Grid catalogue
status: approved
---

# 004 - Grid catalogue

Epic E1 Grid content and model (US-1.3) · Release: MVP · Epic depends on: None

## Goal

As a player, I want to browse grids by difficulty and size, so that I pick one that suits my group.

Every other epic reads the grid through this model, so it ships first.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-1.3.1) Each grid lists its number, publication date, force, dimensions and word count.
- **AC-2** (AC-1.3.2) The list filters by force and sorts newest first by default.
- **AC-3** (AC-1.3.3) A grid I started or finished shows that status on my device or account.
- **AC-4** (AC-1.3.4) An unpublished grid is absent from the list and its direct URL returns "not found".

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Grid schema: spec 002.
- Grid validation at import: spec 003.
- Licensed content only: spec 005.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Grid source (open decision in the backlog): commission an author, license from a publisher, or generate and review. This blocks E1.
