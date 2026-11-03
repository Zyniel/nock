---
id: B-067
title: Chat refuses control and direction-override characters
status: In Progress
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T16:59:00Z'
labels:
  - domain:chat
milestone: m-4
dependencies: []
documentation:
  - specs/social/chat.md
priority: medium
ordinal: 55000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-029 (B-028's review). A chat text accepts control and bidirectional override characters (U+202E), which can show a message reversed; nicknames already refuse them. chat.md is past the budget of specs/_map.md: widen the existing criterion on a chat text's checks rather than add one. Out of scope: reactions, clue flags.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A chat text holding a control or bidirectional override character is refused as nicknames are
- [ ] #2 chat AC-9 (changed)
- [ ] #3 chat AC-21 (changed)
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
1. Spec: social/chat.md, widen the existing criterion on a chat text's checks (chat is past the budget).
2. Tests: tests/test_chat_*.py.
3. Quick gate: uv run python scripts/gate.py --specs chat --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: nicknames use an allow-list, so chat refuses Unicode Cc, Cf, Zl, Zp except U+000A, U+200C, U+200D (serving.md rule 9's set); only U+000A among line breaks stays allowed; invalid_message reused; a stored message with a refused character still loads (AC-21 widened).

Lead: tag characters U+E0020-U+E007F allowed too, so subdivision flag emoji (England, Scotland, Wales) are not refused (spec-checker's side-effect note).

Review round 1: APPROVE (quick gate passed full: 5404 + 124). Suggestion 1 taken (boundary cases: U+2029, U+200B, U+E0001 refused; U+200C, U+E0020 accepted). Not taken: 2 (one shared helper for the refused categories of chat and NOCK_DATABASE: the sets differ by the line feed and the tags; recorded as a draft at the milestone's close); 3 (chat.md past the budget: DRAFT-058).
<!-- SECTION:NOTES:END -->
