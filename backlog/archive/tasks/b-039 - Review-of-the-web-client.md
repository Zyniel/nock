---
id: B-039
title: Review of the web client
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels: []
dependencies: []
ordinal: 48000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human asked for it, 2026-10-30: « As the Code Reviewer
  agent "code-reviewer.md", create a new branch and proceed to a full review
  of the frontend. Propose a strategy to resolve each point. »; a review,
  built by the lead)
- Domains: none (the report `claude_docs/frontend-review.md`; no spec, test or
  code changes)
- Architecture decision: no
- Branch: feat/b-039-frontend-review · PR: #70
- Problem: no review had looked at `web/` as a whole, across specs, for
  correctness, security, accessibility, performance and maintainability.
- In scope: every file of `web/src`, the web client's config, its build,
  audit and type check, and a screenshot check of the grid's focus ring in
  Chromium and WebKit.
- Out of scope: the Python backend (B-028), the tests themselves, the tooling.
- Screens: none.
- Findings: 1 High (sign-out leaves the account's seats on the device),
  11 Medium (undo, check and reveal overtake the resent edits; no rejoin when
  storage is refused; the selection is not sent again after a reconnection;
  the grid's focus ring is painted under the letter cells; every frame
  re-runs every letter cell; a zoomed grid does not follow the selection;
  focus under the sheets; four copies of the dialog; live regions created
  full; no caching headers; the connection inside `RoomPage.svelte`),
  27 Low. The report proposes twelve items; most need a spec change first.
- Queued (the human, 2026-10-30: « Claim the twelve proposed items of the
  B-039 review and write their briefs in Backlog.md, in the proposed
  order. »), in the report's order. Eleven items, claimed with
  `scripts/claim_item.py`; the twelfth, the caching headers (M10), joins
  B-034 as the report proposed, since both set the headers of the same
  answers:
  1. Before the first public test, with B-031 to B-034: B-040 (sign-out
     forgets the account's seats), B-041 (reconnection keeps order and
     presence), and B-034 with the caching headers.
  2. Next, a baseline the product breaks today: B-042 (the grid's focus
     ring).
  3. Then cost, reach and focus on the room page: B-043 (remote updates),
     B-044 (zoomed grid), B-045 (room sheets), B-046 (one status region),
     B-047 (connection hardening).
  4. Before the split, if the human takes it: B-048 (unit tests, tooling).
  5. Last: B-049 (the split of `RoomPage.svelte` and `GridViewport.svelte`),
     once B-041 and B-045 pin the behaviour it keeps. B-050 (small fixes)
     at any time.
  Each item's branch takes `main` once this one is merged, so it has its
  brief. The human approved the order on 2026-10-30 (« Approve the order.
  Push and open PR for all new features. Let the main session handle the
  queuing / priority management »): the main session places these items
  among the others and sets their priorities. Each brief still waits for
  its own approval.
<!-- SECTION:DESCRIPTION:END -->
