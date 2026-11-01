---
id: DRAFT-024
title: Known flakes to watch
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T20:21:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Known flakes: 036 AC-8's join on the room of `NOCK_DATABASE` fails under load and passes alone; 046 AC-22's nickname error failed once on Firefox, never reproduced; 046 AC-22's fit (`test_spec_046_ac22_fit.py`, chromium-1280x800-not-found) failed once in a parallel gate run during B-040 and passed alone; 019 AC-4's legend after Bob leaves failed once in the full gate on Windows (B-015), passed alone; on Windows, `net::ERR_NO_BUFFER_SPACE` after several gates in a row (rerun alone).
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
