---
id: DRAFT-049
title: A load-failure state for the page imports
status: Draft
assignee: []
created_date: '2026-11-02T08:22:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-050 (#95). The pages are now imported lazily; when an import fails (the network, or a deploy that replaced the chunks) nothing says so. Needs a rule, a design in specs/_design/, its drawing and a criterion. B-050's review removed the {:catch} state the lead had added (an unspecified screen state with a borrowed key, against _design/pages.md).
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
