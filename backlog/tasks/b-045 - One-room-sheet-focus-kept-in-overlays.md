---
id: B-045
title: One room sheet, focus kept in overlays
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
