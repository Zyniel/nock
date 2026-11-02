---
id: B-048
title: Unit tests for the client's pure modules
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T10:39:00Z'
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
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. No spec (tooling): the runner, its resolve hook, a gate step and CI job, built by the lead.
2. Tests: tests/web/, one proving the step runs, by the test-writer; they prove no criterion.
3. Gate: uv run python scripts/gate.py (full), node:test step included.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human (2026-11-02, chat): take B-048 with option A, Node's own node:test (no new dependency), to unblock B-049 and with it « Grid and room screens ». Open questions 1 and 2 take the lead's defaults: the tests in tests/web/, written by the test-writer; they prove no criterion.

Lead (2026-11-02): the human's option A, node:test; tests in tests/web/ by the test-writer; they prove no criterion. Base: origin/main 4005dc3 merged into the stale branch.

Lead: design from the Plan agent (Fable, high), option 1 of 3: the hook in scripts/ (tooling the human owns; a hook in web/ would be the implementer's), the step with the static group of the full stage rather than a third --tests kind (TEST_SELECTIONS are pytest selections), a dedicated web/tsconfig.tests.json (node types kept out of the app's config). No new CI job: the static job runs it; tests/web/* is static-only in the change detection. erasableSyntaxOnly added to tsconfig.app.json so the app refuses syntax Node cannot strip (none exists today). Local PATH node is v22.23 (fine: 22.18+); CI is lts/*.
Lead: review round 1 CHANGES REQUESTED (the version check never ran on a Node without registerHooks; suggestions: the tests' tsconfig stricter than the app's, the hook's limits undocumented), all taken in 114e139; round 2 APPROVE, its wording suggestion taken. The full gate ran green at 21e0d86; after the review fixes, which touch only the hook and the tests' tsconfig, the gate without browser tests ran green.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Node's own node:test now runs TypeScript unit tests of the client's pure modules, tests/web/*.test.ts, with no new dependency (the human's option A).
- scripts/node_test_hooks.mjs: resolve hook for the imports Vite allows and Node does not (extensionless relative .ts, JSON without its attribute); a version guard (Node 22.18+ with type stripping).
- scripts/gate.py: step 'node:test (web unit tests)' in the full stage with the static group; left out by --skip-static and --tests browser; the node_modules check covers it.
- CI: the static job runs it; tests/web/* is static-only in the change detection. No new job.
- web/tsconfig.tests.json + npm run check type-check the tests; tsconfig.app.json gains erasableSyntaxOnly.
- Docs: CLAUDE.md (command, quality gate), .claude/agents/test-writer.md (where such tests go; they prove no criterion).
- Smoke test: tests/web/ops.test.ts, cellStatesAtStep (3 tests), through both hook branches. The reviewer loaded all ten named modules under the hook.
Criteria: none (tooling). Reviewer: CHANGES REQUESTED round 1, APPROVE round 2. Full gate green (8674 + 162) at 21e0d86; gate without browser tests green after the fixes. Not verified: Windows, Node before 22.15.
<!-- SECTION:FINAL_SUMMARY:END -->
