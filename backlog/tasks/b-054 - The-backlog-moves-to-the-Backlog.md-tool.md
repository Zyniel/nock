---
id: B-054
title: The backlog moves to the Backlog.md tool
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - tooling
dependencies: []
priority: high
ordinal: 52000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Who decided: the human approved the v3 process on 2026-11-01 (milestones as
  bets, the Backlog.md tool, the six choices of the doc "How you steer Nock"),
  with `backlog.md@1.55.3` as a pinned global npm dependency, and lifted three
  rules: the approval of each brief and spec change, no push or pull request
  unless asked, and the human merging every pull request.
- Domains: none (tooling and process: `backlog/`, `scripts/`, `.claude/`,
  `.github/workflows/ci.yml`, `CLAUDE.md`, `README.md`, `specs/_map.md`)
- Problem: the hand-kept `Backlog.md` (140 KB, 2,363 lines) mixes every item's
  history with the queue, and its statuses are approval gates the human no
  longer wants for each item.
- In scope: `backlog/` and its config; every item imported with its number
  (done ones archived, gaps left free); the milestones "Connection and sync",
  "Grid and room screens" and "Upkeep"; the follow-ups and grid ideas as
  drafts; the release checklist and the human's guide as docs;
  `scripts/start_item.py` in place of `scripts/claim_item.py`; CI's skip list;
  the CLI in cloud sessions; and the pipeline the default statuses force: the
  spec-checker, `/milestone`, `/task` and the new `/feature` (push, pull request,
  auto-merge), with `CLAUDE.md`, the roles and `specs/_map.md` following.
- Out of scope: moving the dated decisions of `CLAUDE.md` into decision records
  (the next pull request of the migration); pruning the merged remote branches
  and the claim refs `refs/items/*`.
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
