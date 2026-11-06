---
id: B-101
title: Hidden tabs measured in three engines
status: In Progress
assignee: []
created_date: '2026-11-05T01:54:00Z'
updated_date: '2026-11-06T14:23:00Z'
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
- [ ] #1 The measure is recorded in the task, and a hidden tab stays connected in the three engines, or the spec says what happens
- [ ] #2 reconnection AC-6 (changed)
- [ ] #3 reconnection AC-9 (new)
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
<!-- SECTION:NOTES:END -->
