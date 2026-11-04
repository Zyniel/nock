---
id: DRAFT-061
title: Dependency patches of the web client (L27)
status: Draft
assignee: []
created_date: '2026-11-03T13:32:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Grid and room screens » close. B-050 left L27 of the B-039 review to a tooling task: patched releases of svelte, svelte-check and vite, and the two low build-time advisories. Bump the three packages in web/package.json and web/package-lock.json, check the two advisories, rebuild and run the full gate in the three engines. Tooling and dependency versions: the human's call before it starts.
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
