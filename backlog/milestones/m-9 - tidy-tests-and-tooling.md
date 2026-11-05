---
id: m-9
title: "Tidy tests and tooling"
---

## Description

- Problem: criteria proven only in part, tests that flake under load, and a few tooling gaps; each lets a regression pass green or makes a gate fail for nothing.
- Size: L (8 tasks): B-096 to B-103.
- In scope: the checks of specs 025, 048 and 035 tightened (DRAFT-011, 013, 014); untested client details (021); hud AC-21's other sheets and every summary field check (070, 072); unit tests of three B-050 fixes (071); the flakes under load (024, 032, 053, 018, and the two of B-079's gate); hidden tabs measured in three engines (060); SMTP sends out of the sync routes' pool (030); shared components named in the specs' Code sections (059).
- Out of scope: the font preload (050, acceptable as is); a screen-reader trial (065, the human's).
- Look: none.
- Risks: tooling (the flake task may change the harness's waits or SERIAL_TEST_FILES, the lead's fixes).
- Bet: the human, in chat, 2026-11-05 (« Create a milestone for all housekeeping tasks and queue it »). Queued after « Owner's calls » and Upkeep; the three housekeeping milestones run in this order: Spec splits 2, Tidy specs and code, Tidy tests and tooling.
- Questions for you: none.
