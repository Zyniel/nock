---
id: B-102
title: SMTP sends out of the sync routes' pool
status: Done
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T17:51:00Z'
labels:
  - domain:account
milestone: m-10
dependencies: []
documentation:
  - specs/account/account.md
priority: low
ordinal: 90000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-030: a slow mail server and many addresses could fill the 40 threads of every sync route. Runs after B-038 and the account split.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A slow SMTP server leaves the other sync routes answering, with a test
- [x] #2 account AC-24 (new)
- [x] #3 account AC-25 (new)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: account/account.md, a criterion: a slow SMTP server leaves the other sync routes answering
Tests: tests/test_account_*.py
Quick gate: uv run python scripts/gate.py --specs account --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions: the link request still answers 202 or 503 once its send ends (rule 6, AC-9 unchanged), the send no longer holding a sync-route thread; rule 7's sentence covers the sign-in link's sends only, the deletion e-mail (account/erasure.md) becomes a follow-up draft; no cap on sends at once (the per-address and per-client limits bound each client); AC-24 is a free number.

Spec-checker round 1: CHANGES REQUESTED: moving the sends to asyncio's default executor would pass but stall every room join (live-rooms rule 3 shares that executor); the rule now says the link's sends run on threads of their own, and AC-24 adds a socket joining a room. Test note from the checker: 50 requests within the limits need several client addresses and one event loop (httpx AsyncClients over ASGITransport with client=(addr, port)); a TestClient per address has its own pool and would pass before the fix.

Spec-checker round 2: APPROVED (the socket case split into AC-25, accepted).

Test-writer: AC-24 fails now (GET /api/grids answered after 19 sends had ended); AC-25 passes now (the join's room lookup runs on asyncio's default executor, not the sync pool) but fails for the default-executor fix the spec-checker raised (tried in a scratch copy), and both pass with each send on its own thread. Lead's decisions: AC-25 kept as a guard that cannot fail before the fix; no assertion that all 50 sends start at once (no cap was decided either way); the file joins SERIAL_TEST_FILES (it races a 5 s hold).

Reviewer round 1: CHANGES REQUESTED. Blocking: a mailer error other than MailError never resolved the send's future, so the request hung (and a graceful shutdown with it); the thread now passes any exception on. Also taken: rule 7 cited, annotations, prepare_sign_in_link's docstring. Noted: the sweep has no criterion of its own (covered through AC-25's executor).

Reviewer round 2: APPROVE.

PR: #173.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Milestone m-10 « Client and server cleanups ».

- **account rule 7** (changed): the sign-in link's sends run on threads of their own; however slow the SMTP server and however many sends wait, the other routes, the room sockets and the sweep go on; a link request still answers 202 or 503 once its send ends (rule 6 unchanged).
- **account AC-24 (new)**: `tests/test_account_slow_mail.py::test_ac24_grids_answer_while_fifty_link_sends_wait`: 50 link requests within the limits (5 client addresses, one event loop) wait on a mailer holding each message 5 s; `GET /api/grids` answers 200 before any send ends. Failed before the fix (19 sends had ended first).
- **account AC-25 (new)**: `::test_ac25_a_join_gets_its_snapshot_while_fifty_link_sends_wait`: a socket joining a room gets its snapshot before any send ends. It passed before the fix (the join's lookup is on asyncio's default executor) but fails for a fix that moves sends there: a guard the lead kept.
- **Code**: `ask_sign_in_link` is async; its checks and store work run in the sync pool (`run_in_threadpool`); each send runs on a daemon thread of its own, its result reaching an asyncio future; any exception from the mailer reaches the route (MailError → 503, anything else surfaces as before).
- **Spec-checker**: round 1 CHANGES REQUESTED (a fix on the default executor would have stalled room joins), round 2 APPROVED. **Reviewer**: round 1 CHANGES REQUESTED (a non-MailError hung the request), round 2 APPROVE.
- **Decisions**: the request still waits for its mail (no change players see); only the sign-in link's sends move (the deletion e-mail: DRAFT-093); no cap on sends at once; the test file joins SERIAL_TEST_FILES.
- **Gate**: the full gate in Chromium passed (8886 parallel; serial at load 2.8 of 4 CPUs).
<!-- SECTION:FINAL_SUMMARY:END -->
