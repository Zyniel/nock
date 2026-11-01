---
id: B-040
title: Sign-out forgets the account's seats on the device
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T20:16:00Z'
labels:
  - domain:account
  - domain:hud
milestone: m-0
dependencies: []
documentation:
  - specs/account/account.md
  - specs/client/hud.md
priority: high
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: first of B-039's items (before the first public test: a leak of
  seats on shared devices, B-039 H1)
- Domains: account/account (rules 13 and 17: what sign-out and deletion
  forget on the device), client/hud (its « Out of scope » line on forgetting
  identities)
- Architecture decision: no with option A (a new device record that only the
  account code reads); yes with option B (the identity record of
  `lobby/joining.md` rule 8, which every page reads)
- Problem: after a sign-in, and on every catalogue load while signed in,
  `storeMissingIdentities` (`web/src/lib/account.ts:192`) copies each seat of
  the account (player id, resume token, nickname) into `localStorage`
  (`account/account.md` rule 13). « Se déconnecter » and « Supprimer mon
  compte » (`AccountPage.svelte:103`, `:112`) remove nothing, and nothing
  prunes `nock.identity.*`, `nock.room.*` or `nock.history`. On a shared
  computer the next person sees the account's rooms in « Mes salons », and
  « Reprendre » takes a seat with its nickname, its colour and its host
  rights. After a deletion the seats stay too, as `--`, and the history keeps
  the team-mates' nicknames.
- In scope: the device knows which identities the account brought; a 204 from
  sign-out or deletion removes them, their `nock.room.*` records and the
  history records of their rooms, then shows the state. The seats the device
  took itself stay: they are how a guest comes back. Options:
  - A (lead's pick): a list `nock.account_rooms` of the codes that
    `storeMissingIdentities` wrote.
  - B: a flag `from_account` in each identity record.
- Out of scope: forgetting an identity whose room the summaries no longer
  return; a session that expires with no sign-out (its seats stay until the
  next sign-out on that device).
- Overlaps: B-036 changes `account/account.md` rule 18, a different rule.
  The file is over the size guideline already ("Small follow-ups").
- Screens: none (« Mes salons » lists fewer rooms; no new state).
- Open questions:
  1. A sign-out or deletion that fails: A (lead's default) the device keeps
     everything, as the account does, and the page shows `error` (rule 16);
     B the device forgets anyway.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 account AC-31 (new)
- [x] #2 account AC-32 (new)
- [x] #3 account AC-33 (new)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Specs: specs/account/account.md, specs/client/hud.md
Tests: tests/test_account_*.py, tests/test_hud_*.py
Gate: uv run python scripts/gate.py --specs account,hud --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions: option A (a list nock.account_rooms of the codes storeMissingIdentities wrote), so no architecture decision; open question 1 takes A (a failed sign-out or deletion keeps everything, the page shows error, rule 16).

Tests: the device's own seat T keeps its room record too (rule 17: a seat the device took itself stays), so the test asserts nock.room.T stays.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Sign-out and deletion now forget, on a 204, the seats the account brought to the device; the device's own seats stay.

- account AC-31: tests/test_account_signout_forgets.py::test_ac31_a_sign_out_forgets_r_and_s_and_keeps_t, ::test_ac31_mes_salons_lists_t_alone_after_the_sign_out
- account AC-32: ::test_ac32_a_deletion_leaves_the_device_as_a_sign_out_does
- account AC-33: ::test_ac33_a_failed_sign_out_or_deletion_removes_nothing (sign-out, deletion)
- hud: its Out of scope line only (no criterion).

Code: web/src/lib/account.ts (nock.account_rooms written by storeMissingIdentities; forgetAccountSeats), web/src/lib/AccountPage.svelte (called on a 204 only). specs/_settings.md lists the new key.

Spec-checker: APPROVED in round 2 (round 1 asked for a clearer AC-31 setup and a concrete AC-33 example). Reviewer: APPROVE in round 1; two suggestions taken (the key in _settings.md; the history rewritten only when a record goes). Full gate: passed (8535 parallel, 160 serial).

Lead's decisions: option A (nock.account_rooms, read only by the account code), so no architecture decision; a failed sign-out or deletion keeps everything (open question 1, A); nock.progress stays out of scope; the device's own seat keeps its room record too (rule 17).

Flagged: account.md is over the size guideline (33 criteria), its split is a follow-up draft; readAccountRoomCodes keeps the string items of a mixed array (the rule leaves it open); when the sign-out does rewrite nock.history, malformed records of other rooms are dropped; tests/test_spec_046_ac22_fit.py failed once in the implementer's first gate run and passed alone (possible flake).
<!-- SECTION:FINAL_SUMMARY:END -->
