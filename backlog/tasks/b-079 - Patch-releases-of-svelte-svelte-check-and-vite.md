---
id: B-079
title: Patch releases of svelte, svelte-check and vite
status: Done
assignee: []
created_date: '2026-11-04T01:17:00Z'
updated_date: '2026-11-04T12:07:00Z'
labels:
  - tooling
milestone: m-6
dependencies: []
priority: low
ordinal: 67000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-061 (L27 of the B-039 review), delegated by the human 2026-11-04. Update web/package-lock.json to the latest patch releases of svelte, svelte-check and vite within the ranges web/package.json already holds (npm update svelte svelte-check vite, no range change), check with npm audit that no advisory a release fixes remains, rebuild and run the full gate in the three engines. Out of scope: minor or major upgrades.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The lockfile holds the latest patches of the three packages in range, npm audit shows no advisory that a release fixes, and the gate passes in the three engines
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
1. No spec (tooling): npm update svelte svelte-check vite in web/ (lockfile only, ranges unchanged).
2. npm audit: the two low advisories gone.
3. Gate: the full gate, one engine at a time (chromium, firefox, webkit).
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The two low advisories are deepmerge (GHSA-gcqx-w48m-w2h4) via @sveltejs/vite-plugin-svelte: no fix available upstream, so they stay; the patch bumps of the three packages are done.

Review round 1: CHANGES REQUESTED. Fixed: the lockfile is now written by npm 11 (CI's lts/*), so it keeps its ten libc fields; npm 10 had dropped them. The criterion is reworded by the lead: 'the two advisories gone' could never be met, since deepmerge 4.3.1 is the latest release and @sveltejs/vite-plugin-svelte 7.3.1 still needs it; the two low advisories stay, with no fix published. Gate: the full gate in three engines ran 16,903 passed and 2 failed under load (webkit test_server_offline_undo ac29, firefox test_spec_033_ac09 at 320x568); both pass when rerun alone, and neither depends on these packages. The lead accepts that run with the reruns; CI's gate runs on the pull request and after the merge.

Review round 2: APPROVE.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
svelte 5.57.3, svelte-check 4.7.8 and vite 8.3.5 (with rolldown 1.2.16 and postcss 8.5.32, which vite needs) are in web/package-lock.json, written by npm 11 as in CI; web/package.json is unchanged. The lead reworded the criterion you delegated: it asked for the two low build-time advisories to be gone, which no release allows today (deepmerge 4.3.1, GHSA-gcqx-w48m-w2h4, is the latest and @sveltejs/vite-plugin-svelte 7.3.1 still needs it). They remain, low and build-time only. Full gate in three engines: 16,903 passed, 2 failed under load (webkit offline undo AC-29, firefox account menu at 320x568), both passing when rerun alone.
<!-- SECTION:FINAL_SUMMARY:END -->
