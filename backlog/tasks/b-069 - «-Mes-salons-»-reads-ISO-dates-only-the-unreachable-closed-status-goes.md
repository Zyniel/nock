---
id: B-069
title: « Mes salons » reads ISO dates only; the unreachable closed status goes
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T20:11:00Z'
labels:
  - domain:summaries
  - domain:shell
milestone: m-4
dependencies: []
documentation:
  - specs/lobby/summaries.md
  - specs/client/shell.md
priority: low
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-057 and DRAFT-020. isTime in web/src/lib/myRooms.ts uses Date.parse alone, which reads some non-ISO strings as dates in V8 only; anchor it to an ISO 8601 pattern first, as B-047 did for ops.ts's isDateTime. The room page's 'closed' status can no longer be reached, yet room.status.closed (« Connexion perdue. ») is a required key of 040 AC-22's test: drop the key, the status and that test entry. Out of scope: DRAFT-020's history entries of 046 AC-23 and 043 AC-31 (archived specs, left as they are).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 A summary whose last_activity_at is not ISO 8601 reads as no date in every engine
- [x] #2 The room page has no closed status and no room.status.closed key
- [x] #3 summaries AC-4 (new)
- [x] #4 shell AC-3 (changed)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: lobby/summaries.md (ISO dates in « Mes salons »), client/shell.md (no closed status, no room.status.closed key).
2. Tests: tests/test_summaries_* or tests/web/myRooms.test.ts; the 040 AC-22 test entry.
3. Quick gate: uv run python scripts/gate.py --specs summaries,shell --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: « Connexion perdue. » (room.status.closed) is unreachable (no closed status in any spec or in RoomStatus); the band room.banner.offline stays. The ISO check applies to a summary's finished_at too (one function). isTime is shared with history.ts (results' « Grilles terminées »): option (a), the stricter check applies there too, the server having only ever stored ISO strings; stating it in gameplay/results.md is a follow-up draft at the milestone's close. test_spec_012_ac01_nickname_rule.py's status-text list also drops closed.

Lead: the test-writer's two finished_at cases kept (rule 2 covers both fields).

Review round 1: APPROVE. Not taken: 1 (negative offset or bare-date test cases: the spec's examples are tested); 2 and 4 (calendar check and history's stricter reading: in the follow-up draft for gameplay/results.md); 3 (the caption's wording: accurate).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
« Mes salons » counts a summary's dates only as an ISO 8601 date-time with a time zone (fractional seconds read), else the existing my_rooms.error: isDateTime moves from ops.ts to web/src/lib/dateTime.ts and myRooms' isTime uses it (history.ts too). The unreachable room.status.closed key leaves fr.json; _design/room.md and the screens sheet's caption drop it.

Criteria and their tests:
- summaries AC-4 (new): tests/test_summaries_iso_dates.py (last_activity_at and finished_at, two refused forms each; a fraction with Z or +00:00 lists the row).
- shell AC-3 (changed, ← 040 AC-22..24): tests/test_spec_040_ac22_ac26_static_client.py (no room.status.closed); tests/test_spec_012_ac01_nickname_rule.py's status list drops closed.

Spec-checker: APPROVED in round 2 (the design file's status list, fractional seconds). Reviewer: APPROVE in round 1; suggestions not taken (reasons in the notes). Full gate: passed (8719 parallel, 162 serial).
Decisions: « Connexion perdue. » (room.status.closed) was unreachable, the band room.banner.offline stays; finished_at checked too; history.ts reads dates the same stricter way, stated in results.md by DRAFT-066.
<!-- SECTION:FINAL_SUMMARY:END -->
