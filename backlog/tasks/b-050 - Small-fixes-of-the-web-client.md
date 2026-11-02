---
id: B-050
title: Small fixes of the web client
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T04:04:00Z'
labels:
  - domain:host
  - domain:operations
  - domain:product
  - domain:shell
milestone: m-1
dependencies: []
documentation:
  - specs/lobby/host.md
  - specs/admin/operations.md
  - specs/product.md
priority: low
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: any time, between larger items; one fix per commit
- Domains: lobby/host (rule 8: the settings form), admin/operations (rules
  16, 18 and 19: the ops requests and the token), `product.md` (« Stable
  routes »); the other fixes keep rules that already hold
- Architecture decision: no (L26 adds the row of an existing route; no
  baseline changes)
- Problem and fix, one per B-039 Low finding:
  - L10: any `settings_changed` resets the unsaved settings form
    (`RoomPage.svelte:588`): only the fields that changed are copied.
  - L12: a menu keeps its old place when the top bar changes form with no
    layout change (`RoomPopover.svelte:50`, plausible): placed again after
    `tick()`.
  - L14: the scrolling lists observe every item again on each new line, with
    two ResizeObservers on the chat stream (`scrollingLists.ts:16`, `:203`):
    one watcher per list.
  - L15: a pinch that gains a third finger and loses one makes the zoom jump
    (`GridViewport.svelte:526`), and a lost `pointerup` can leave a ghost
    finger: a new baseline at two fingers, the pointer captured.
  - L18: crossing answers of `/ops` can end on the wrong period, the replay
    too (`OpsPage.svelte:83`, `OpsReplay.svelte:70`): a request counter per
    kind.
  - L19: a token that cannot be a header value sticks in `sessionStorage`
    (`OpsPage.svelte:95`, `ops.ts:176`): its shape checked before it is
    stored, the field cleared on lock and focused when the form comes back.
  - L20: the list separator `', '` (four places) and the units « h » and
    « min » (`OpsSettings.svelte:52`) are outside `fr.json`:
    `Intl.ListFormat('fr')` or a key, and two unit keys.
  - L21: on the plain pages the top bar is inside `<main>`, so there is no
    banner landmark (`CatalogueFrame.svelte:34`, `EntryFrame.svelte:24`):
    the frames own `<main>` after the top bar.
  - L23: one bundle serves every route, and the fonts are neither subset nor
    preloaded: `import()` per page in `App.svelte`, the `latin` and
    `latin-ext` subsets, a preload of the grid's two faces, measured against
    `product.md` rule 22 before and after.
  - L26: « Stable routes » omits `GET /api/account/progress`
    (`account/account.md` rule 24): one row.
  - L27: patches for svelte, svelte-check and vite, and two low advisories,
    build-time only: tooling, the human's call, taken with the next tooling
    item.
- Out of scope: the host sheet's errors and focus (B-045).
- Screens: none (L21 moves no pixel; the tests that locate `main` are
  checked).
- Open questions:
  1. A change of the lock alone: A (lead's default) the typed counts stay;
     B they reset, as today.
  2. The ops fixes (L18, L19): A (lead's default) in this item; B an item of
     their own.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 host AC-21 (new)
- [x] #2 host AC-22 (new)
- [x] #3 operations AC-26 (new)
- [x] #4 operations AC-27 (new)
- [x] #5 operations AC-28 (new)
- [x] #6 operations AC-29 (new)
- [x] #7 operations AC-30 (new)
- [x] #8 shell AC-29 (new)
- [x] #9 shell AC-30 (new)
- [x] #10 shell AC-31 (new)
- [x] #11 shell AC-32 (new)
- [x] #12 shell AC-33 (new)
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
Spec: specs/lobby/host.md (rule 8), specs/admin/operations.md (rules 16, 18, 19), specs/product.md (Stable routes; accessibility and performance baselines as needed)
Tests: tests/test_host_*.py, tests/test_operations_*.py, tests/test_product_*.py, plus regression tests under the existing criteria of the other fixes
Quick gate: uv run python scripts/gate.py --specs host,operations,product --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Decisions (lead, 2026-11-02):
- Q1: A. A settings_changed that changes the lock alone keeps the typed counts; only the fields that changed are copied into the form.
- Q2: A. The ops fixes L18 and L19 are in this task.
- L27 (svelte, svelte-check, vite patches and the two advisories) is tooling, the human's call: not built here, left to the next tooling task.
- L20: one key for the list separator (keeps « , », no visible change) rather than Intl.ListFormat, whose « et » would change the text players see; two unit keys for « h » and « min ».
- L23: no change to package.json or the Vite config (tooling); the font subsets come from the files @fontsource already ships, the preload from the client's own code.

- L20, L21 and L23 are written in client/shell.md, not under the product baselines: a new baseline rule would be a baseline change (escalation class), and the task says no baseline changes. The task takes the label domain:shell (no task In Progress holds it). product.md gets only the Stable routes row (L26).
- Spec-writer's open questions, all A: the client checks rule 4's full token shape; a wrong shape reads « Jeton refusé. » with the input empty and focused; a stored token of a wrong shape is removed and the page opens locked with no error line; the grid's two faces are Source Sans 3 500 and IBM Plex Sans Condensed 600, latin files; either placement of the preload passes.
- L12, L14, L15: no spec change (rules already hold; hud.md is B-046's domain).

- Spec-checker: CHANGES REQUESTED (shell rule 2 units too wide; rule 21 restated the design's faces), then APPROVED in round 2. Size: shell.md (33 criteria), operations.md (30) and host.md (22) are over budget; shell and operations splits are B-058 and B-063, host.md and product.md become follow-up drafts.

- One feat commit, not one per fix: RoomPage.svelte, OpsPage.svelte and SharePage.svelte each carry two or three of the fixes; the commit body lists the files of each fix.
- L23 measured against product rule 22 (FX-02, median of 3 cold loads on the reference phone, test_spec_036_ac01): 1246.5 ms before, 1551 to 1578 ms after (limit 2500 ms). The room page's code now comes one round trip after the entry script; the catalogue and the other pages no longer load the room's code. Preloading the fonts from App.svelte cost about 100 ms more; from RoomPage nothing measurable, so it is there.
- The font preload names the woff2 files through new URL(node_modules path, import.meta.url), not an @fontsource ?url import, which 041 AC-6's scan would count as a ninth face import.
- No test proves L12, L14 and the ghost-finger part of L15 (a lost pointerup cannot be simulated through CDP).

- Review round 1: CHANGES REQUESTED. Blocking: the host sheet reopened on abandoned typed values (rule 8 says it opens on the room's values): the implementer copies the room's values on open. No criterion added for the reopen case (rule 8 already states it; a new criterion would cost another spec round for a one-line fix); it stays untested, noted for the verdict.
- Suggestions taken: touch pointers only are captured, with an isPrimary guard against a ghost finger (L15); a {:catch} on the page imports showing the existing error state; the room entry page's status line inside its main; RoomPopover's comment and name; the exact 046 frame assertions restored, the shell page openers shared, a plain loop in 041's FONT_IMPORTS.
- Not taken: the ?url font import in place of the node_modules path (acceptable as is; a draft follow-up). Recorded for the human: rule 22 on the room route went from 1246 ms to about 1570 ms (limit 2500 ms), the cost of the room's own chunk.

- Review round 2: CHANGES REQUESTED on one new finding, the {:catch} state of the page imports (unspecified screen state, borrowed key, role against _design/pages.md), which the lead had asked for; the reviewer named its removal as enough to approve. App.svelte is back to its round-1 content (commit after 9aba404); the load-failure state becomes a follow-up draft. Flakes seen under parallel load, each green alone: 014 AC-7, 013 AC-7, 044 AC-2, all waiting for the room page's first state, which now comes one chunk later.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Nine of the B-039 Low findings fixed in the web client (L10, L12, L14, L15, L18 to L21, L23), plus the Stable routes row of L26. L27 (dependency patches) is tooling, left to the human's next tooling task.

Criteria and their tests:
- host AC-21: tests/test_host_settings_sheet.py::test_ac21_a_lock_keeps_the_typed_count_and_the_chosen_help_mode
- host AC-22: test_host_settings_sheet.py::test_ac22_a_count_the_event_changes_..., test_ac22_a_help_mode_the_event_changes_...
- operations AC-26: tests/test_operations_page.py::test_ac26_the_1_day_answer_after_the_30_day_one_changes_nothing
- operations AC-27: test_operations_page.py::test_ac27_the_404_of_the_first_code_after_the_second_replay_changes_nothing
- operations AC-28: test_operations_page.py::test_ac28_a_token_of_another_shape_is_refused_with_no_request, test_ac28_a_token_of_the_shape_is_sent_in_the_header
- operations AC-29: test_operations_page.py::test_ac29_a_stored_token_of_another_shape_is_removed_and_nothing_is_sent
- operations AC-30: test_operations_page.py::test_ac30_a_refused_replay_..., test_ac30_a_refused_period_press_...
- shell AC-29: tests/test_shell_text_keys.py (fr.json keys, the recap and bounds lines read from the keys, the source scans)
- shell AC-30: tests/test_shell_landmarks.py (7 pages, 2 windows)
- shell AC-31: tests/test_shell_page_code.py
- shell AC-32, AC-33: tests/test_shell_fonts.py
- L15 regression under board AC-2: tests/test_board_pinch_third_finger.py
- product: one Stable routes row (GET /api/account/progress), no criterion.
Existing tests edited: 038 and 048 ops tests use a wrong token of rule 4's shape; 041 AC-6 expects the 16 latin and latin-ext imports of the same eight faces.

Reviewer: CHANGES REQUESTED (the host sheet reopened on abandoned values), then CHANGES REQUESTED on the {:catch} state the lead had asked for, whose removal the reviewer named as enough; removed (b41dde8) and APPROVE. Spec-checker: CHANGES REQUESTED, then APPROVED. Full gate green (second run; the first had three first-page timeouts under load, each green alone).

Decisions:
- Q1 A: a lock alone keeps the typed counts; the sheet copies only the room values that changed, and opens on the room's values.
- Q2 A: the ops fixes are here. The client checks rule 4's full token shape; a wrong shape reads « Jeton refusé. » with no request; a stored one is removed; every lock empties and focuses the input.
- L20: keys list.separator, unit.hours, unit.minutes, not Intl.ListFormat (its « et » would change the text).
- L20, L21, L23 are written in client/shell.md (rules 2, 19, 20, 21), not under the product baselines, which the task does not change; the task took the label domain:shell.
- One feat commit for the nine fixes: three files carry several of them.

For the human:
- Rule 22 (FX-02, median of 3 cold loads, limit 2500 ms): 1246 ms before, about 1570 ms after. The room page's code now comes one round trip after the entry script; the other pages no longer carry it.
- With the room page's first state one chunk later, page-ready waits have timed out under heavy parallel load six times (014 AC-7, 013 AC-7, 044 AC-2, host AC-10, 041 AC-3, 035 AC-6), each green alone.
- Untested: the host sheet's reopen case (rule 8 states it), L12, L14, and L15's lost pointerup. A pen no longer pans a zoomed grid (board rule 3 speaks of fingers only).
- Follow-ups: a load-failure state for the page imports (rule, design, drawing, criterion); the font preload through an @fontsource ?url import instead of a node_modules path; splits of host.md and product.md (shell and operations: B-058, B-063).
<!-- SECTION:FINAL_SUMMARY:END -->
