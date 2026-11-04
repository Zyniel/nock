---
id: B-079
title: Patch releases of svelte, svelte-check and vite
status: In Progress
assignee: []
created_date: '2026-11-04T01:17:00Z'
updated_date: '2026-11-04T01:19:00Z'
labels:
  - tooling
milestone: m-6
dependencies: []
priority: low
ordinal: 67000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-061 (L27 of the B-039 review), delegated by the human 2026-11-04. Update web/package-lock.json to the latest patch releases of svelte, svelte-check and vite within the ranges web/package.json already holds (npm update svelte svelte-check vite, no range change), check that the two low build-time advisories are gone (npm audit), rebuild and run the full gate in the three engines. Out of scope: minor or major upgrades.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The lockfile holds the latest patches of the three packages in range, npm audit shows the two advisories gone, and the gate passes in the three engines
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
1. No spec (tooling): npm update svelte svelte-check vite in web/ (lockfile only, ranges unchanged).
2. npm audit: the two low advisories gone.
3. Gate: the full gate, one engine at a time (chromium, firefox, webkit).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The two low advisories are deepmerge (GHSA-gcqx-w48m-w2h4) via @sveltejs/vite-plugin-svelte: no fix available upstream, so they stay; the patch bumps of the three packages are done.
<!-- SECTION:NOTES:END -->
