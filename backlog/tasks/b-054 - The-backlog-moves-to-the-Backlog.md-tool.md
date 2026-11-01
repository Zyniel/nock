---
id: B-054
title: The backlog moves to the Backlog.md tool
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T16:56:00Z'
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
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The lead's decisions:
- The pipeline planned for the third migration PR (spec-checker, /milestone, /task, the new /feature, the three lifted rules) is in this one: the default statuses cannot hold the brief, approved and ready gates that /new-spec and /feature relied on, and the human's guide names the new commands.
- A task starts from origin/main, where its file must be: a milestone's tasks arrive with its pitch, an added task through a board pull request with auto-merge (/task). start_item.py --board makes those board worktrees.
- A task's existing branch is reused (B-038, B-040 to B-050 keep their worktrees); start_item.py says when it lacks commits of origin/main.
- CI lists changed paths with core.quotePath=false, so a backlog file whose name has « », an accent or ’ still skips the gate jobs.
- The Definition of Done fits tooling tasks too ("or a tooling task", "or left to the human to merge"); a tooling task gets a reviewer round, the task standing for the spec.
- The imported done items keep their text and have no Definition of Done; created dates are the import's (git keeps the history).
- B-048, B-038 and B-003 stay unassigned: each escalates when it is started (Upkeep's pitch says so).
- The dead "item B-004 of Backlog.md" lines of social/catch-up.md and social/chat.md lost the pointer only; both stay done.
- Milestones are archived at a release, not at their close (release checklist).

Pull request: https://github.com/Zyniel/nock/pull/82 (no auto-merge: the human merges it as the bet).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Backlog.md (the file) is now backlog/, kept with the backlog CLI 1.55.3: 44 items imported with their numbers (31 Done and archived, 13 To Do in "Connection and sync", "Grid and room screens" and "Upkeep"), 37 drafts, 3 docs (the human's guide, the release checklist, grid engine and ipuz). scripts/start_item.py replaces scripts/claim_item.py. The v3 pipeline came with it: the spec-checker agent, /milestone, /task, the new /feature with push, pull request and auto-merge, and CLAUDE.md, the roles, specs/_map.md and README.md following. CI skips backlog/; cloud sessions install the CLI.

Checks: backlog doctor clean; the gate without browser tests green; start_item.py tried against a scratch origin; CI's changed-files step run on the import's file list (no job) and with a .py (every job).

No reviewer round and no spec-checker: a tooling and process change the human approved as a whole, merged by the human as the bet on the first two milestones.
<!-- SECTION:FINAL_SUMMARY:END -->
