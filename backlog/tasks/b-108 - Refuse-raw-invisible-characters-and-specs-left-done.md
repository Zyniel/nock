---
id: B-108
title: Refuse raw invisible characters and specs left done
status: In Progress
assignee: []
created_date: '2026-11-05T22:21:00Z'
updated_date: '2026-11-06T11:49:00Z'
labels:
  - follow-up
  - tooling
milestone: m-2
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), items I-1 and I-2. New tooling behaviour, the human's call.
(1) guard_paths.py refuses an Edit or Write holding raw Cf, Cc or Zs characters other than the plain space, with an allowlist for the zero-width joiner inside emoji. The same scan becomes a static step of gate.py. Today it would flag the raw U+3000 at tests/test_spec_037_ac02_edit_validation.py:427.
(2) A SubagentStop check for the spec-writer in role_gate.py: every spec changed since origin/main reads status: draft. Size S each.
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Tooling, no spec: scripts/hooks/guard_paths.py refuses raw Cf/Cc/Zs (ZWJ in emoji allowed); the same scan as a static step of scripts/gate.py; role_gate.py checks the spec-writer leaves changed specs at status: draft
Tests: tests of the hooks if any exist (test-writer), the raw U+3000 in tests/test_spec_037_ac02_edit_validation.py (test-writer)
Gate: the full gate in Chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The human queued this as a tooling pull request on 2026-11-06 ("Queue B-072 and B-074 as technical PR"): the escalation for new tooling behaviour is answered. Filed under Upkeep, label tooling, no spec; the lead builds it on its branch.

Lead's decisions: the scan applies to every caller and allows the space, the line feed and the tab (Caddyfile's tabs); the ZWJ between two emoji parts; the spec-writer check counts only specs with an uncommitted change, since the lead commits approved and done statuses itself. Reviewer round 1: CHANGES REQUESTED, blocking: .claude/settings.json's SubagentStop matcher never ran role_gate.py for the spec-writer. Fixed by the lead: the matcher names spec-writer (and the PreToolUse matcher MultiEdit); the status is read from the front matter as gate.py reads it; Zl and Zp join the refused categories; control characters get their \N names; the hook gives the total past five; main's two modes documented; CLAUDE.md's Quality gate names both checks.
<!-- SECTION:NOTES:END -->
