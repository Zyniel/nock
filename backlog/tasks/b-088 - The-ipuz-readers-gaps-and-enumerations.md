---
id: B-088
title: The ipuz reader's gaps and enumerations
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T02:59:00Z'
labels:
  - domain:ipuz
milestone: m-8
dependencies: []
documentation:
  - specs/content/ipuz.md
priority: low
ordinal: 76000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-009 and DRAFT-010: dotted (drawn as dashed), solution letters, a key written twice, a UTF-8 byte order mark, a clue's explanation, tags or type; ’ as an enumeration separator, and a test that a leading zero loads. Decide each in the spec, then build. Out of scope: other ipuz features.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Each of the reader's gaps and the ’ separator is decided in the specs with a criterion, tested and built
- [x] #2 content/ipuz.md AC-10, AC-12 and AC-15 to AC-18: dotted, solution letters, keys written twice, the byte order mark, clue keys, ’ and a leading zero
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decisions on the spec-writer's choices:
- The seven cases all go in content/ipuz.md, which owns the reader. grids.md rule 4 already treats ' and ’ alike, so the task's domain is ipuz, not grid-files and grids.
- Solution letters: any case and accents are accepted (e, É and ê agree with E), because French tools write É. Separators and second letters are still refused.
- An answer built from an enumeration writes ’ as '.
- A key written twice is refused anywhere, namespaced keys included.
- One byte order mark is skipped for .ipuz files only; the catalogue index is out of scope.
- The ’ and leading-zero cases are folded into AC-10, and the clue keys into AC-12, to save size; AC-15 to AC-18 are new.
- The ipuz.py docstring still points to grid-files.md; the implementer fixes it.
- ipuz.md is 14.4 KB with 18 criteria.

Spec-checker APPROVED in round 2. Round 1 asked for namespaced keys and 'one' byte order mark to be written in the text, the solution row to point to grids.md rule 4, and two lines to be reflowed. For the implementer: confirm that grids/*.ipuz still load under the duplicate-key check.

Tests: 20 fail for the missing feature, 154 pass. Lead decision: read_ipuz takes text, so a byte order mark reaches it as U+FEFF at the start; no bytes input.

Reviewer round 2: CHANGES REQUESTED. Five of six round-1 findings are fixed. Left open: test_ac4_a_dashed_value_that_is_not_made_of_t_r_b_l_is_refused (tests/test_ipuz_structure.py) passes even if the dotted letters are not checked, because each bad case is refused later for another reason; the reviewer proved it with a mutation. Its fix is one assertion on the message (re.search for 'T,? R,? B,? L'), checked against the mutation. The code is correct. Escalated: CHANGES REQUESTED after two review rounds (CLAUDE.md). Recommendation: let the test-writer add that assertion, have the reviewer confirm it in a short third round, then close.

The human's answers (chat, 2026-11-06):
1. Dotted borders draw enumeration gaps of any separator (- . ' ’ space), as the spec already says; no change.
2. Solution letters are upper-case only: an accented upper-case letter is read as its base letter (É, Ê, and E followed by a combining accent, count as E); a lower-case letter, accented or not, is refused.
3. No objection to the recommendation: a key written twice stays refused.
4. Input is UTF-8 without a byte order mark: a file starting with one is refused, as before B-088.
5. A clue's explanation, tags and type are ignored; no change.
6. ’ is a separator; no change.
7. No leading zero in an enumeration: each count is a whole number of at least 1 written without a leading zero (05, 02-3 and 0 refused).
The task is unassigned; the spec changes for 2, 4 and 7 go through the spec-writer and spec-checker, then tests, code and one review round.

Reviewer round 3 (first on the human's revised spec): CHANGES REQUESTED. Its mutations show the code is correct and every answer of the human is pinned. One blocking gap: the AC-15 empty-style test passes when that check is removed, because the break-edge check also names (2, 2). Lead decision: the human's answers rewrote the spec, so this counts as the revised task's first review and a confirming round follows. Taken: the blocking assertion; a count of 10 or more tested; the leading-zero refusal message and dead code; test names that match the upper-case rule.

Confirming review: APPROVE. M7 (empty-style check removed) and M2 (one-digit counts) now fail the tests. Note: 5bac515 changed tests and code together; the reviewer checked that the new tests pass on the previous code, so no test was fitted to the code.

Full gate here (Chromium): static checks, 8,829 parallel and 162 serial tests, all green. Firefox and WebKit are left to CI after the merge; the change is server-side only. Not verified: no sample grids are in grids/ (only .gitkeep), so real grids were not loaded under the stricter rules.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
content/ipuz.md now says what the ipuz reader does in seven cases, as the human decided on 2026-11-06:
- a dotted edge draws a break, as dashed does, whatever the separator (AC-15);
- a solution letter is upper-case, its accent dropped: É, Ê and E with a combining acute count as E; a lower-case one is refused (AC-16);
- a key written twice in any object is refused, naming it (AC-17);
- a file starting with a byte order mark is refused as not valid JSON (AC-18);
- a clue's explanation, tags and type are ignored (AC-12);
- ’ is an enumeration separator, the same as ' (AC-10);
- an enumeration's counts have no leading zero (AC-10).
src/nock/ipuz.py implements them. Review went three rounds on the first spec, then the human's answers rewrote it and one confirming round followed; the reviewer's mutations show that every rule is pinned by a test. ipuz.md is 14.9 KB with 18 criteria.
<!-- SECTION:FINAL_SUMMARY:END -->
