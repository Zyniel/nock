---
id: DRAFT-025
title: 'Docker as the deployment: a domain and an image job in CI'
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:deployment
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
B-009's option B, once Docker is how Nock deploys: a domain `platform/deployment.md` and a CI job that builds the image and checks the running container (serves `/`, a room survives a restart, no `.env*` or `data/` inside, not root). Needs the human's approval of the CI actions.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
