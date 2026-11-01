---
id: B-050
title: Small fixes of the web client
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:host
  - domain:operations
  - domain:product
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
