---
id: B-065
title: Milestone closes auto-merge
status: Done
assignee: []
created_date: '2026-11-03T09:25:00Z'
updated_date: '2026-11-03T09:29:00Z'
labels:
  - tooling
milestone: m-2
dependencies: []
priority: medium
ordinal: 53000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Who decides: the human (2026-11-03, chat): a backlog: close PR turns on auto-merge, except when its verdict is « not accepted »; a backlog: milestone PR (the bet) and a needs-human PR (an escalation) keep waiting for the human's merge. Task and board PRs already auto-merge.
- Why: the acceptance's real check is the independent reviewer's verdict, done before the PR opens; CI only checks the backlog files, so the merge was a formality. The human can still stop a close before CI ends by closing it or adding needs-human.
- In scope: .claude/skills/milestone/SKILL.md (Close a milestone, step 4), CLAUDE.md (« Decisions and escalations », « Git »).
- Out of scope: pitches, needs-human PRs; any workflow under .github/.
<!-- SECTION:DESCRIPTION:END -->

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
1. No spec (tooling): CLAUDE.md « Decisions and escalations » and « Git », .claude/skills/milestone/SKILL.md (description, Close step 4).
2. No tests (wording of the process).
3. Gate: uv run python scripts/gate.py --stage tests (no code).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: the edits as the human approved them in chat (2026-11-03).

Review round 2 asked two doc-001 lines (weekly table, « What you no longer do ») and a reflow; the lead applied them without a third round: wording only, same policy.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
A backlog: close PR now auto-merges once CI is green; the human stops it by closing it or adding needs-human. A not-accepted close carries needs-human and waits for the human; pitches and escalations never auto-merge. Changed: CLAUDE.md, the milestone skill (close step 4), doc-001, README. Review: round 2's remaining wording findings applied by the lead. Gate: --stage tests green (no code changed).
<!-- SECTION:FINAL_SUMMARY:END -->
