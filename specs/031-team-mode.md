---
id: "031"
title: Teams
status: draft
---

# 031 - Teams

Epic E8 Game modes (US-8.2) · Release: Later · Epic depends on: E7

## Goal

As a larger group, we want two teams racing, so that we keep the cooperation inside each team.

Cooperative play is the default and the only MVP mode; these two stories add competition later on the same engine.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-8.2.1) The host splits players into 2 teams before the first letter; teams are fixed afterwards.
- **AC-2** (AC-8.2.2) Inside a team, every E3 to E6 rule applies. Between teams, the rules of spec 030 AC-1 and AC-2 apply (backlog AC-8.1.1 and AC-8.1.2).

## Edge cases and errors

- AC-2 depends on behaviour owned by spec 030; test only this spec's side of it here.

## Out of scope

- Ranked play and tournaments (epic E8).
- Race: spec 030.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Competitive play (open decision in the backlog): is E8 wanted at all?
- How are players split when the count is odd, and can a team be empty?
