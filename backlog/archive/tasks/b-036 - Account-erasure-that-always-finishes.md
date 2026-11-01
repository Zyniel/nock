---
id: B-036
title: Account erasure that always finishes
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:account
  - domain:lifetime
  - domain:operations
dependencies: []
ordinal: 46000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done
- Priority: eighth (privacy; the failure needs a busy engine, which B-030 and
  B-031 make rare)
- Domains: account/account, lobby/lifetime (the sweep's step),
  admin/operations (the record's retention)
- Waits for: B-035 (PR #76: it changes `account/account.md` and the sweep
  whose shape option 1's retries follow)
- Architecture decision: yes (a new table, stored data): options from the
  Plan agent on Fable
- Criteria: account AC-24 to AC-30 (new), operations AC-23 (changed)
- Branch: feat/b-036-erasure-finishes · PR: #77
- Problem: `DELETE /api/account` (`server.py:1696`) deletes the account rows,
  then erases its players from the live rooms, waiting up to 5 seconds on the
  engine for each (`hub.py:1548`, `hub.py:1685`). A timeout answers 500 once
  the account is gone; the remaining rooms and the history records keep the
  nickname, and nothing is left to retry from (B-028 L2). Also, from spec 029
  ("Small follow-ups"): a history save that read the room before an erasure
  and writes after it keeps the nickname. And the module docstring of
  `accounts.py` promises that a copy of the database "cannot sign anybody
  in": true of accounts, but its room identities hold resume tokens in clear,
  as they must (the account gives them back to the player's devices).
- Market practice (Plan agent on Fable, 2026-10-31): mature products split
  deactivated, deletion requested (a grace period, undone by signing in:
  Discord 15 days, Steam and Facebook 30) and deleted; a deleted user's
  posts in shared spaces stay under a placeholder (GitHub's ghost, Discord's
  Deleted User), which Nock already does with `--`; the erasure runs as a job
  retried until done, with a record of completion that keeps no personal
  data (CNIL: within one month, keep a record of the request, and the purge
  and the erasure share one mechanism); a notice by e-mail on completion.
  Nock lacks the job, the record and the notice.
- In scope: every step of the erasure runs even when one room fails, and a
  failure is not lost; the history-save race; the docstring says what a copy
  of the database does give. Options:
  - 1: a table of pending erasures written in the deletion's transaction;
    the route tries once and answers 204 whatever happens; the sweep and the
    app's start retry each pending erasure (rooms, creator rooms, history
    last), idempotent, until done; a done row keeps only its times and
    counts.
  - 2 (lead's pick): 1, plus an e-mail « Votre compte Nock a été supprimé »
    sent once the erasure is done, best effort, and a line in the spec on a
    device that rejoins as « Ancien joueur ».
  - 3: an account lifecycle epic: a deletion requested with a grace period
    and an undo by signing in, then 1's erasure; four or five items, a state
    that every account query and the engine's account checks must read.
- Out of scope: an export of the account; backups and chat texts; a
  confirmation link before deleting and a grace period (option 3, later if
  abuse shows up); keeping creator rooms alive for their other players.
- Screens: none.
- Open questions:
  1. The completion e-mail (option 2): A (lead's default) yes; B no.
  2. Creator rooms on deletion: A (lead's default) still deleted
     (`lobby/host.md` rule 14); B made anonymous so the others finish, as
     an item of its own.
- Decisions: the human, 2026-10-31: option 2, the pending-erasure job
  retried by the sweep, the completion e-mail (1A), the spec line on a
  returning device; creator rooms still deleted (2A). The spec change
  approved, with the lead's picks: a done erasure kept 5 years with times
  and counts only; the e-mail sent in the request when its attempt ends
  the erasure; a save slower than a whole erasure accepted; no split of
  account.md in this item.
<!-- SECTION:DESCRIPTION:END -->
