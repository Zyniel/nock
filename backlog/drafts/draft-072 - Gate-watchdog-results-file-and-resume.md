---
id: DRAFT-072
title: Gate watchdog, results file and resume
status: Draft
assignee: []
created_date: '2026-11-05T22:21:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the Investigation report of 2026-11-05 (artifact Cheu7PqfqNyy8VT9UZ1LWQ), items A, B and H. New tooling behaviour, the human's call: escalate before taking it.
- A gate watchdog: a timeout per pass (about 75 min parallel, 20 min serial) that stops the process tree, and each worker's current test written to a file the watchdog prints.
- A warning at start about orphan browser processes.
- Before the serial pass, wait for the load average to fall under about 0.75 × CPUs, and print the load beside the result.
- Re-run the serial pass's failures once with --lf, reported as 'passed on re-run under load L'.
- --junitxml and a summary file per run under .git/nock-gate-results/<branch>/.
- --resume (skip the tests already passed on the same commit) and --shard i/n, so long engines fit the 2-hour background limit.
- pytest-timeout would be a new dependency: the human's call.
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
