---
id: B-045
title: One room sheet, focus kept in overlays
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T23:54:00Z'
labels:
  - domain:hud
  - domain:host
  - domain:hints
  - domain:account
milestone: m-1
dependencies: []
documentation:
  - specs/client/hud.md
  - specs/lobby/host.md
  - specs/gameplay/hints.md
  - specs/account/account.md
priority: medium
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: sixth of B-039's items (before B-049, whose split its tests pin)
- Domains: client/hud (rule 12: the focus and an open menu or the Salon
  sheet; rule 13: Tab stays in every room sheet), lobby/host (rule 8: the
  settings form's errors, the focus when the host role goes), gameplay/hints
  (rule 19: the vote's « Oui » disabled under the focus), account/account
  (rule 14: the backdrop closes the sheet only on a press and a release on
  it)
- Architecture decision: no (a client component)
- Problem: in the sheet layout, Shift+Tab from « Discussion » goes to the
  clue bar's buttons under the Salon sheet, and Tab from an open Aide menu
  goes to the grid under the scrim while the menu stays open (B-039 M7).
  `HostSettings`, `AccountDialog`, `RecapDialog` and `RoomGoneDialog` each
  reimplement the dialog, with different Tab traps, and the host sheet has
  none: Tab from « Enregistrer » leaves for the address bar (M8). When the
  host role goes, the sheet is unmounted and the focus falls to the page;
  « Oui » of the vote is disabled under the focus when the connection drops
  (L8). An invalid count in the host settings fails silently or in the
  browser's language (`HostSettings.svelte:65`, no `novalidate`; L9). A drag
  that starts in the account sheet and ends on the backdrop closes it,
  losing the typed address (L17).
- In scope: one `RoomSheet.svelte` (layout, title, backdrop and cancel
  rules, one Tab trap on a full tabbable selector, `open()`, `close()`,
  `onClosed`) used by the four sheets; the host sheet closed through it when
  the role goes; the vote buttons give the focus away before they are
  disabled, as the chat does for a mute; the settings form with
  `novalidate`, an error line from `fr.json`, `aria-invalid` and
  `aria-describedby`; the focus kept in an open menu or the Salon sheet.
- Out of scope: the settings form reset by any `settings_changed` (B-050);
  the overlays' state, which B-049 moves.
- Screens: the host's settings with an invalid count (a new error line,
  drawn in `docs/design/screens_sheet/`).
- Open questions:
  1. Focus leaving an open menu or the Salon sheet: A (lead's default) the
     overlay closes, without moving the focus; B Tab wraps inside it, as in
     the sheets.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 hud AC-23 (new): Tab or Shift+Tab out of an open menu closes it, the focus staying where it went
- [x] #2 hud AC-24 (new): Shift+Tab out of the Salon sheet closes it and its scrim
- [x] #3 hud AC-25 (new): a room sheet's backdrop closes it only on a press and its release both on it
- [x] #4 host AC-18 (new): Tab and Shift+Tab wrap inside the host sheet
- [x] #5 host AC-19 (new): an invalid count sends nothing and shows the error line, linked to its field
- [x] #6 host AC-20 (new): the loss of the host role closes the host sheet and focuses « Menu »
- [x] #7 hints AC-25 (new): a focused « Oui » or « Non » gives the focus to the grid before it is disabled
- [x] #8 account AC-34 (new): a drag from the account sheet to the backdrop keeps it open with what was typed
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: specs/client/hud.md, specs/lobby/host.md, specs/gameplay/hints.md, specs/account/account.md; the host settings' error line in specs/_design/ and docs/design/screens_sheet/.
Tests: tests/test_hud_room_sheet.py, tests/test_host_*.py, tests/test_hints_*.py, tests/test_account_*.py.
Quick gate: uv run python scripts/gate.py --specs hud,host,hints,account,board,product --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: base commit ffc9b81. Open question 1 (focus leaving an open menu or the Salon sheet): A, the overlay closes without moving the focus, the lead's default. The quick gate is widened with board and product because the change touches RoomPage.svelte.

Lead, on the spec-writer's questions: (1) one error line « Entrez un nombre entier de 0 à 99. » (settings.error.count) shared under both counts, the focus on the first refused count (the inputs are 64 px wide side by side). (2) The vote buttons give the focus to the grid before they are disabled, as rule 22 does when the banner leaves. (3) A focus lost to no element (another window, the browser's controls, an item disabled under it) closes no menu or Salon sheet: hud AC-7 keeps the Aide menu open when an item is disabled under the focus. (4) A focus moved by the page itself (the chat mute, « Inviter ») closes nothing, or chat rule 15 would close the Salon sheet. account.md (34 criteria, 32 KB) and hints.md (24) were over the budget before this change: their split is a follow-up for the human. Screens sheet rebuilt for « Host settings » (count refused).

Spec-checker: CHANGES REQUESTED in round 1 (rule 12's edge case and a press on the overlay's button, rule 13's wording, account rule 14's catalogue case, the look in host rule 8), APPROVED in round 2. Lead, on its optional notes: a Tab or Shift+Tab onto an element outside an open overlay closes it wherever the focus was, the mute case included; a press on its own button (« Aide », « Menu », « Salon ») closes it once.

Lead: merging origin/main (B-041) clashed on hints AC-24, which B-041 took for its offline requests; B-045's criterion of the vote's focus is hints AC-25 (spec, test name and this task renumbered in the merge commit, text unchanged).

Reviewer round 1: CHANGES REQUESTED. (1) Blocking: rule 12's case of a Tab from the browser's own controls cannot be seen by the page (no keydown reaches it), so the Salon sheet closes only on the next Tab inside the page. Lead: option (b), the spec states that limit (the harm is one Tab, the focus on the visible top bar); option (a), guessing a Tab from a focusin after the window regains focus, would misfire on the mute case and cannot be tested headless. (2) Taken: the vote's focus moves to the grid only from « Oui » or « Non », not from the status line a ballot focuses. (3) Taken: hud_harness.py's docstring renumbered to hints AC-25. (4) Taken: hud.md rule 12 rewrapped. The spec 035 AC-2 test edit (the walk starts inside the Salon sheet) keeps what AC-2 checks, per the reviewer.

Close: the full gate failed on 022 AC-18's mute test (after a Tab inside the Salon sheet, the mute's page-moved focus closed the sheet, against chat rule 15): the widened quick gate had left the chat domain out. Back to the implementer; the 006 AC-2 arrow failure was ERR_NO_BUFFER_SPACE and passes alone.

Pull request: https://github.com/Zyniel/nock/pull/88, auto-merge on.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The room's four sheets share one dialog frame, `RoomSheet.svelte`, and the focus no longer escapes an open menu, the Salon sheet or a sheet.

Criteria:
- hud AC-23: `tests/test_hud_overlay_focus.py::test_ac23_*` (Tab off the Aide menu focuses the grid and closes it; Shift+Tab off the Menu focuses « Menu » and closes it; a vote disabling the focused item leaves the menu open).
- hud AC-24: `test_ac24_shift_tab_on_discussion_focuses_the_clue_bar_and_closes_the_sheet`; rule 12's edge case in `test_ac24_tab_out_of_the_page_closes_nothing_until_the_focus_is_in_the_page`.
- hud AC-25: `test_ac25_*` (a press and release in two places close nothing; both on the backdrop close and focus « Menu »).
- host AC-18: `tests/test_host_settings_sheet.py::test_ac18_*` (Tab wraps in the host sheet).
- host AC-19: `test_ac19_*` (`100`, `-1`, `2.5`, empty: nothing sent, the field focused, `aria-invalid`, « Entrez un nombre entier de 0 à 99. »; a valid save closes; marks set anew and cleared on close).
- host AC-20: `test_ac20_a_host_change_closes_the_sheet_and_focuses_menu`.
- hints AC-25: `tests/test_hints_vote_focus.py::test_ac25_*` (« Oui » or « Non » focused when the socket closes: the focus on the grid, the selection kept, no ballot).
- account AC-34: `tests/test_account_sheet_backdrop.py::test_ac34_*` (a drag to the backdrop keeps the sheet and `lea@exa`, in a room and on the catalogue).
- product AC-2's feed outline test (spec 035) now starts its Tab walk inside the open Salon sheet: the old walk Tabbed through the top bar with the sheet open, which rule 12 now closes.

Reviewer: CHANGES REQUESTED in round 1, APPROVE in round 2. Blocking: rule 12 promised to close the Salon sheet on a Tab from the browser's own controls, which sends the page no keydown; the spec now closes it on the first Tab pressed inside the page (option b; option a, guessing from a focusin after the window regains focus, would misfire on the mute case and cannot be tested headless). Taken: the vote's focus moves only from « Oui » or « Non », not from the status line a ballot focuses; a harness docstring; rule 12 rewrapped.

The close gate: the first full gate found 022 AC-18's mute test closing the Salon sheet (a Tab whose focus stayed inside it left the Tab flag up, so the mute's page-moved focus was taken for the Tab's); fixed in 6821e89, the flag now clearing at the first focus change after a Tab and on the key's release. The widened quick gates had left the chat domain out; the full gate passed after the fix (8584 parallel, 160 serial).

Lead's decisions: a Tab or Shift+Tab onto an element outside an open menu or the Salon sheet closes it, the focus staying there (the task's default A), wherever the focus was, the mute case included; a focus lost to no element or moved by the page closes nothing; a press keeps the scrim's rules and a press on the overlay's own button closes it once; one shared error line under both counts, the focus on the first refused one; the vote's focus goes to the grid. The spec-checker asked for changes once and approved the second round.

Flagged: B-041 took hints AC-24 on main, so B-045's criterion is hints AC-25 (renumbered in the merge). Rule 12's mute case has no criterion of its own. `account.md` (34 criteria), `hints.md` (25), `host.md` (20) and `hud.md` are at or over the budget of `specs/_map.md`: their split is a follow-up for the human.

Code: `web/src/lib/RoomSheet.svelte` (new: open, close, onClosed, one Tab trap, canCancel, closesOnBackdrop), `HostSettings`, `AccountDialog`, `RecapDialog`, `RoomGoneDialog` on it, `revealCount.ts` (`isValidCount`, shared), `Salon.svelte` (a bindable element), `RoomPage.svelte` (the overlay Tab rule, the host sheet closed on the role's loss, the vote's focus), `fr.json` (`settings.error.count`). The look: the host's settings with a refused count, drawn in the screens sheet.
<!-- SECTION:FINAL_SUMMARY:END -->
