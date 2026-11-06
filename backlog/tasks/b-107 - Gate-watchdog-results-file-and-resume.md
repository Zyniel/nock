---
id: B-107
title: Gate watchdog, results file and resume
status: In Progress
assignee: []
created_date: '2026-11-05T22:21:00Z'
updated_date: '2026-11-06T13:14:00Z'
labels:
  - follow-up
  - tooling
milestone: m-2
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Tooling, no spec: scripts/gate.py (watchdog per pass, orphan warning, load wait before the serial pass, serial re-run with --lf, junitxml and summary under .git/nock-gate-results/<branch>/, --resume, --shard i/n); no new dependency (pytest-timeout not approved)
Design by the Plan agent (tooling design), built by the lead
Gate: the full gate in Chromium, and the new options tried by hand
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The human queued this as a tooling pull request on 2026-11-06 ("Queue B-072 and B-074 as technical PR"): the escalation for new tooling behaviour is answered. Filed under Upkeep, label tooling, no spec; the lead builds it on its branch. pytest-timeout is not approved by that answer: the watchdog is built in gate.py without a new dependency; adding pytest-timeout stays the human's call.

Design (Plan agent): A1 watchdog in gate.py (Popen + wait timeout, stop the tree by descendants on POSIX / taskkill on Windows, without a new session so role_gate's killpg still reaches it); B1 the plugin writes each worker's current test (progress files) and one JSON line per report per pass, read for --resume and the serial re-run (explicit node ids, not --lf, whose fallback reruns everything); C1 --shard by file in the plugin (sorted, dealt round robin). Results under <git common dir>/nock-gate-results/<branch>/<run>/ (run.json, summary.txt, <pass>.xml, <pass>.jsonl, progress/). Load: os.getloadavg, GetSystemTimes on Windows, bounded 120 s wait. Orphans: warn, never kill. Lead's decisions: take A1/B1/C1; the serial re-run applies in CI too (never silent; budgets untouched), at most 20 failures re-run; keep --pass-timeout for trying the watchdog by hand; keep the 20-run pruning; junit upload in CI deferred.

Built by the lead's builder (Opus) from the design. Deviations accepted: the worker/controller check in pytest_sessionstart (xdist's dsession is not registered at configure time); shards chosen before resume's deselection, so a file keeps its shard; the POSIX tree stop kills the root first so xdist cannot start a replacement worker; plugin options passed as --x=value (else pytest took a .git path for a test path and the main checkout as rootdir); junit_family xunit1 (spec 015's record_property); orphan matching on the executable path only; two watchdog messages; --workers 0 is not a serial pass; --resume passes when nothing is left to run. Hand checks on Linux: results folder, watchdog at 0.4 min (gw0-gw3 named, no process left, lock released), a fail-once serial test passed on re-run under load, resume after SIGINT (2294 + 2432 = 4726), shards 1349 + 1415 + 1962 = 4726, bad --shard refused, orphan warning on real Firefox processes, pruning to 20. Windows parts (taskkill, PowerShell query, GetSystemTimes) untried.

Reviewer round 1: APPROVE, no blocking findings (it checked the watchdog at 0.1 min, resume, shards 1-4 = 8885 with an identical union, the lock on SIGINT). Taken: stop the tree before reporting; --resume's OK rests on what the selection really left out; shard wording per pass; non-finite --pass-timeout refused; the double load wait counted in the comment. Not taken, to a follow-up draft: the POSIX stop without ps (read /proc) and the race with a browser started during the listing (SIGSTOP the tree first); a fingerprint taken again at the end; pruning old branch folders by age.
<!-- SECTION:NOTES:END -->
