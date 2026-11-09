---
id: DRAFT-102
title: 'Quick gate: a harness another domain''s tests import'
status: Draft
assignee: []
created_date: '2026-11-09T22:22:00Z'
labels:
  - follow-up
  - tooling
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-113. role_gate.py and gate.py name a domain from a changed harness by its prefix only (names_domain): a change to tests/cards_harness.py does not add library or my-account to the quick gate, though test_library_filter.py and test_my_account_progress_signout.py import it. CI runs every test, so nothing is missed in the end. Closing it (adding the domains whose tests import a changed harness) is new tooling behaviour: the human decides.
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
