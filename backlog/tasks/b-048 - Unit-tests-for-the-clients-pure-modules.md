---
id: B-048
title: Unit tests for the client's pure modules
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:00:00Z'
labels:
  - tooling
milestone: m-2
dependencies: []
priority: medium
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Who decides: tooling, built by the lead; the runner, and a new
  dependency with option B, are the human's call.
- Priority: before B-049, if the human takes it
- Domains: none (tooling: `web/package.json`, `scripts/gate.py`, CI)
- Architecture decision: yes (the design of the tooling: a second test
  runner in the gate): options from the Plan agent on Fable
- Criteria: none (tooling)
- Problem: the client's pure modules (`roomSession`, `activityFeed`,
  `catchUp`, `remoteSelections`, `joinRules`, `navigation`, `history`,
  `wordSelection`, `gridLayout`, `ops.cellStatesAtStep`) are tested only
  through Playwright, one page per case. Their permutations (a gap in the
  sequence, an error during a resend, a snapshot over pending edits) are slow
  to reach that way, and the split of B-049 needs them pinned.
- In scope: a runner for TypeScript tests of those modules, a gate step and
  its CI job, and one test that proves the step runs; the test-writer adds
  tests with the items that need them. Options:
  - A (lead's pick): Node's own `node:test`, which runs TypeScript in Node 24
    (CI takes `lts/*`): no new dependency, but a resolve hook for the
    extensionless imports, the import of `fr.json` and `svelte/reactivity`.
  - B: Vitest, a new dev dependency that reads the Vite config as it is.
- Out of scope: component tests (the Svelte components stay with the browser
  tests).
- Screens: none.
- Open questions:
  1. Where the tests live: A (lead's default) `tests/web/`, written by the
     test-writer, whose folder it is; B beside the modules in `web/src`,
     which the implementer owns.
  2. Whether such a test proves a criterion: A (lead's default) no, criteria
     stay proven by `tests/test_<name>_*.py`; B the traceability check reads
     them too.
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human (2026-11-02, chat): take B-048 with option A, Node's own node:test (no new dependency), to unblock B-049 and with it « Grid and room screens ». Open questions 1 and 2 take the lead's defaults: the tests in tests/web/, written by the test-writer; they prove no criterion.
<!-- SECTION:NOTES:END -->
