---
id: B-101
title: Hidden tabs measured in three engines
status: Done
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T15:34:00Z'
labels:
  - domain:reconnection
milestone: m-9
dependencies: []
documentation:
  - specs/platform/reconnection.md
priority: low
ordinal: 89000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-060: measure whether a real hidden tab's throttled pings let the server's 6 s silence close it, in Chromium, Firefox and WebKit, and apply what the measure calls for.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The measure is recorded in the task, and a hidden tab stays connected in the three engines, or the spec says what happens
- [x] #2 reconnection AC-6 (changed)
- [x] #3 reconnection AC-9 (new)
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
Measure first: a hidden tab of a real room in Chromium, Firefox and WebKit (real throttling, the server log of closes) over several minutes
Then: no change if every engine stays connected; else a spec change in platform/reconnection.md (or an escalation if it needs server pings, a protocol change)
Gate: the reconnection quick gate, then the full gate in Chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Measure (2026-11-06; scripts and results in the lead's scratchpad b101/, rerunnable): Playwright never truly hides a page in any engine (it disables Chromium's backgrounding, forces Firefox's docShell active, keeps WebKit visible), so the real app was driven outside it: Chromium 153 over raw CDP without Playwright's switches, Firefox 155 with Playwright's forcing lines removed, WebKitGTK 2.52.6 default and with Safari-like increasing throttling. Each hidden 421 s, a second player (a Python socket) watched presence.
- Chromium (headless and headed): pings stall after ~60 s hidden (intensive wake-up throttling; the open WebSocket does not exempt it); the server closes with 4408 at ~66 s, then every ~21 s; the room sees « déconnecté » 17 times, each resumed within 2 s.
- Firefox (headless and headed): 2.0 s median, 2.5 s max: never closed.
- WebKitGTK default: 3.0 s pings: never closed. Safari-like: closed at 19.8 s, then every ~20 s (20 disconnects).
- A 2 s timer in a dedicated Web Worker kept its 2 s ticks in all three engines while the main thread's stalled (Chromium 60 s gaps, WebKit 20 s).
Lead's decision: option 1, the page's ping timer runs in a Web Worker (client only: platform/reconnection.md rule 3 and the client; no protocol change, no dependency). Server pings or a longer silence would be protocol or realtime changes (the human's); writing the flicker into the spec would accept a visible « déconnecté » flicker (a product call). A tab the browser suspends or discards still reconnects as today.

Spec-checker: APPROVED; its three wording notes applied (AC-9 names the 4408 close, the fallback covers a worker that cannot be created or reports an error, AC-6 rewrapped). Lead's decisions: the fallback to the page's own timer has no criterion of its own; the harnesses that freeze the page clock remove Worker so the page's timer (and the page clock) drives their pings, which proves the fallback through the 017 AC-1 tests.

Reviewer round 1: APPROVE (its probes: AC-9 fails without a worker; a 404 on the worker asset falls back to the page's timer with no close; a throwing constructor falls back; five hide/show cycles leave one worker). Taken: two spec lines rewrapped, a docstring. Not taken, to a follow-up draft: a test of the worker's error fallback (a stale asset hash after a deploy), which has no criterion of its own.

PR: #170.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Milestone m-9 « Tidy tests and tooling ».

- **The measure** (task notes; scripts rerunnable): Playwright never truly hides a page, so the real app ran outside it: Chromium 153 over raw CDP, Firefox 155 without Playwright's forcing, WebKitGTK default and Safari-like, each hidden 421 s with a second player watching. Chromium stops a hidden page's timers after ~60 s: the server closed the socket with 4408 at ~66 s, then every ~21 s, and the room saw « déconnecté » 17 times. Safari-like WebKit: from ~20 s, every ~20 s. Firefox and default WebKitGTK stayed connected. A dedicated worker's 2 s timer kept its pace in all three engines.
- **reconnection rule 3** (changed): the ping ticks come from a dedicated worker served from the app's origin; a page whose worker cannot be created or reports an error keeps the 2 s with its own timer; a page the browser suspends whole loses its socket and reconnects as before.
- **reconnection AC-9 (new)**: `tests/test_reconnection_worker_pings.py::test_ac9_a_hidden_page_whose_own_timers_stop_pings_every_2_s_and_stays_open` (three engines; serial): a hidden page whose clock is paused pings every 2 s for 10 s, one socket, never disconnected. It fails without the worker.
- **reconnection AC-6 (changed)**: wording (a page held back whole); its tests run without Worker.
- **Task #1**: the measure is recorded, and a hidden tab now stays connected in the three engines.
- **Code**: `web/src/lib/pingWorker.ts`, `roomConnection.ts` (`createPingWorker`, `startPingTicks`). The frozen-clock harnesses load the page without Worker, so the 017 AC-1 pace tests prove the fallback.
- **Spec-checker**: APPROVED. **Reviewer**: APPROVE, round 1 (its probes: a 404 on the worker asset and a throwing constructor both fall back; one worker after five hide/show cycles). Follow-up: a test of the worker's error fallback.
- **Decisions**: option 1 (a worker) over server pings or a longer silence (protocol changes, the human's) or a flicker written into the spec (a product call).
- **Gate**: the full gate in Chromium passed (8886 parallel; serial at load 2.8 of 4 CPUs).
<!-- SECTION:FINAL_SUMMARY:END -->
