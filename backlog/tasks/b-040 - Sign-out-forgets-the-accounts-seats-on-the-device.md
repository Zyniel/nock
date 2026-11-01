---
id: B-040
title: Sign-out forgets the account's seats on the device
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
