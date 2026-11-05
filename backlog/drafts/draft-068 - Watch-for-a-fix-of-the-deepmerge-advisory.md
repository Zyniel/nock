---
id: DRAFT-068
title: Watch for a fix of the deepmerge advisory
status: Draft
assignee: []
created_date: '2026-11-05T05:01:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From the close of « Owner's calls »: GHSA-gcqx-w48m-w2h4 (low, build-time) stays in web/package-lock.json via @sveltejs/vite-plugin-svelte, which needs deepmerge ^4.3.1; 4.3.1 is the latest. When a fixed deepmerge or a plugin release without it ships, update the lockfile (npm 11).
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
