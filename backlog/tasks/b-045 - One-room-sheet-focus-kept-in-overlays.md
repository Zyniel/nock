---
id: B-045
title: One room sheet, focus kept in overlays
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T22:00:00Z'
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
- [ ] #1 hud AC-23 (new): Tab or Shift+Tab out of an open menu closes it, the focus staying where it went
- [ ] #2 hud AC-24 (new): Shift+Tab out of the Salon sheet closes it and its scrim
- [ ] #3 hud AC-25 (new): a room sheet's backdrop closes it only on a press and its release both on it
- [ ] #4 host AC-18 (new): Tab and Shift+Tab wrap inside the host sheet
- [ ] #5 host AC-19 (new): an invalid count sends nothing and shows the error line, linked to its field
- [ ] #6 host AC-20 (new): the loss of the host role closes the host sheet and focuses « Menu »
- [ ] #7 hints AC-24 (new): a focused « Oui » or « Non » gives the focus to the grid before it is disabled
- [ ] #8 account AC-34 (new): a drag from the account sheet to the backdrop keeps it open with what was typed
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
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
<!-- SECTION:NOTES:END -->
