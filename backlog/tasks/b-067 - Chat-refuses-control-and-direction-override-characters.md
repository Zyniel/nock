---
id: B-067
title: Chat refuses control and direction-override characters
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T18:24:00Z'
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
- [x] #1 A chat text holding a control or bidirectional override character is refused as nicknames are
- [x] #2 chat AC-9 (changed)
- [x] #3 chat AC-21 (changed)
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
1. Spec: social/chat.md, widen the existing criterion on a chat text's checks (chat is past the budget).
2. Tests: tests/test_chat_*.py.
3. Quick gate: uv run python scripts/gate.py --specs chat --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: nicknames use an allow-list, so chat refuses Unicode Cc, Cf, Zl, Zp except U+000A, U+200C, U+200D (serving.md rule 9's set); only U+000A among line breaks stays allowed; invalid_message reused; a stored message with a refused character still loads (AC-21 widened).

Lead: tag characters U+E0020-U+E007F allowed too, so subdivision flag emoji (England, Scotland, Wales) are not refused (spec-checker's side-effect note).

Review round 1: APPROVE (quick gate passed full: 5404 + 124). Suggestion 1 taken (boundary cases: U+2029, U+200B, U+E0001 refused; U+200C, U+E0020 accepted). Not taken: 2 (one shared helper for the refused categories of chat and NOCK_DATABASE: the sets differ by the line feed and the tags; recorded as a draft at the milestone's close); 3 (chat.md past the budget: DRAFT-058).

PR #122.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
A chat text is now refused (invalid_message) when it holds a character of Unicode category Cc, Cf, Zl or Zp, but U+000A, U+200C, U+200D and the tag characters U+E0020-U+E007F: a field_validator on the incoming Chat message's text (src/nock/protocol.py); ChatText and stored ChatMessage rows are untouched, so old history still loads.

Criteria and their tests:
- chat AC-9 (changed, ← 022 AC-2): tests/test_spec_022_ac01_ac02_chat_messages.py, test_ac2_websocket_a_text_with_a_control_or_override_character_is_refused (U+202E, U+0007, U+2028, U+2029, U+200B, U+E0001) and test_ac2_websocket_a_line_feed_a_joiner_and_tags_are_sent_as_they_are (line feed, a ZWJ emoji, the Scotland flag, U+200C, U+E0020).
- chat AC-21 (changed): tests/test_chat_history.py::test_ac21_a_stored_message_holding_u202e_loads_unchanged.

Spec-checker: APPROVED in round 2 (examples as escapes). Reviewer: APPROVE in round 1; boundary cases added; the shared helper with NOCK_DATABASE's check not taken (the sets differ). Full gate: passed (8717 parallel, 162 serial).
Decisions: nicknames use an allow-list, so the refused set is serving.md rule 9's (Cc, Cf, Zl, Zp but U+200C, U+200D); only U+000A among line breaks; tag characters allowed for the subdivision flags; invalid_message reused; stored messages not checked again.
<!-- SECTION:FINAL_SUMMARY:END -->
