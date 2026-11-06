---
id: B-102
title: SMTP sends out of the sync routes' pool
status: In Progress
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T15:39:00Z'
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
- [ ] #1 A slow SMTP server leaves the other sync routes answering, with a test
- [ ] #2 account AC-24 (new)
- [ ] #3 account AC-25 (new)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
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
<!-- SECTION:NOTES:END -->
