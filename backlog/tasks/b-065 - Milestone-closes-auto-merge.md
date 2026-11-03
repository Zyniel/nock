---
id: B-065
title: Milestone closes auto-merge
status: To Do
assignee: []
created_date: '2026-11-03T09:25:00Z'
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
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
