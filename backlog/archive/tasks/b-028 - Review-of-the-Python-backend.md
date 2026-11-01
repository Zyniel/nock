---
id: B-028
title: Review of the Python backend
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels: []
dependencies: []
ordinal: 38000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human asked for it, 2026-10-29: « As the Code Reviewer
  agent "code-reviewer.md", create a new branch and proceed to a full review
  of the python backend. »; a review, built by the lead)
- Domains: none (the report `claude_docs/backend-review.md`; no spec, test or
  code changes)
- Architecture decision: no
- Branch: feat/b-028-backend-review · PR: none yet
- Problem: no review had looked at `src/nock/` as a whole, across specs, for
  security, capacity and maintainability.
- In scope: every module of `src/nock/`, the gate without browser tests, and
  measurements of the hot paths on the largest catalogue grid.
- Out of scope: the web client, the tests themselves, the tooling.
- Screens: none.
- Findings: 2 High (unlimited room creation that stays in memory; grid checks
  and full-grid edits that pin the one engine thread), 7 Medium, 11 Low, and a
  gap of the gate (pyrefly skips `scripts/`). One recommendation changed on a
  second reading: L1 asked to hash the resume tokens of the account tables,
  which cannot work, since the account hands the raw token back to the
  player's other devices; only the docstring that promises safety is wrong
  (B-036).
- Queued (the human, 2026-10-29: « Review your comments, regroupe them in
  technical coherent fixes and queue them in the backlog »), one item per
  coherent fix, in the lead's order:
  1. Before the first public test, the ways one client hurts every room:
     B-029 (gate), B-030 (grid lookups), B-031 (check and reveal limits),
     B-032 (room capacity), B-033 (sockets), B-034 (HTTP edge).
  2. Next, privacy promises that are not checked: B-035 (store deletion),
     B-036 (account erasure).
  3. When convenient, cost and structure: B-037 (lean snapshots), B-038
     (server structure).
  The rest went to "Small follow-ups". Each item's branch takes `main` once
  this one is merged, so it has its brief. The human approved the order on
  2026-10-29 (« Approve the order: B-029 to B-034 before the first public
  test, then B-035 and B-036, then B-037 and B-038. Start with B-029. »); the
  briefs B-030 to B-038 still wait for their own approval.
<!-- SECTION:DESCRIPTION:END -->
