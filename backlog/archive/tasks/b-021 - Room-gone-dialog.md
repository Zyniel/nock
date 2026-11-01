---
id: B-021
title: Room gone dialog
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:hud
  - domain:shell
  - domain:joining
dependencies: []
ordinal: 31000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved the brief as written, then the spec
  change as written, 2026-10-28; built and reviewed in two rounds,
  2026-10-28)
- Domains: client/hud (a new rule and two criteria; rules 3 and 7 name the
  dialog), client/shell (rule 7, one line), lobby/joining (rule 16, one line);
  `_design/overlays.md` (a new section « Room gone »), `_design/room.md`
  « Connection lost » and « Layers », `_design/foundation.md` (the dialog
  scrim and bottom sheet rows); the screens sheet, part 3
- Architecture decision: no (the client only: the server already closes every
  socket of a deleted room with 4404; no message, stored data or public name
  changes)
- Criteria: hud AC-21, AC-22 (new); shell, joining: no criterion (one line
  each)
- Branch: feat/b-021-room-gone · PR: none yet
- Request (the human, 2026-10-28, word for word): "Players inside a room that
  expires are displayed a "This room no longuer exists" popup (To translate in
  French) and routed back to the menu."
- Problem: once the room has shown, the 4404 close of a deleted room ends the
  page on `not_found`: the status band « Ce salon n'existe pas. » under the top
  bar (`client/hud.md` rule 7), the grid still drawn and typable under it, its
  letters going nowhere, and no way on but « Retour aux grilles » or the brand.
- When it happens: a room expires 30 days after its last edit and the hourly
  sweep deletes it (`lobby/joining.md` rules 15, 16). A player meets it with a
  tab left open on an idle room, or when a page back from a long sleep or an
  offline spell opens a socket to the deleted room: a 4404 after the first
  snapshot, joined or reconnecting.
- In scope: on that 4404, a modal alert dialog titled `room.gone.title`
  « Ce salon n'existe plus. », with the existing line
  `room.status.not_found_detail` (« Un salon est effacé 30 jours après sa
  dernière modification. ») and one primary link, `share.home` « Voir les
  grilles », to `/`, the catalogue (the lead reads the human's "menu" as the
  home page, not the room's « Menu »). The dialog takes the focus and is
  announced; a menu, the Salon sheet, a room sheet or the recap open at that
  moment closes; the connection band goes, pending edits are dropped, and the
  room under the scrim is inert. It goes into `client/hud.md` (about 15.1 KB
  and 15 criteria after it, within the budget).
- Out of scope (the human's answer: removed players): a player removed by the
  host keeps the status band « Vous avez été retiré de ce salon. ». Also: a
  4404 before the first snapshot (the entry card « Ce salon n'existe pas. »
  stays, that player never saw the room); the other final statuses once the
  room has shown (locked, replaced, throttled keep the band); a warning before
  expiry or extending a room; forgetting the stored identity of a deleted room.
- Screens: the room page once it has shown, in both layouts; the screens sheet
  draws « The room deleted after it showed » in part 3. Options:
  - **A (the human's pick): a dialog with one way out.** The recap's frame
    (`_design/overlays.md` « Recap »: a 440 px dialog in the column layout, a
    bottom sheet in the sheet layout, over the dialog scrim): the title, the
    30-day line in muted, « Voir les grilles » right-aligned. Escape does
    nothing, since there is no room to go back to. The page changes only on
    the player's press, as the accessibility baseline wants.
  - B (rejected): the same dialog, and `/` loads by itself after 10 seconds.
  - C (rejected): no dialog; `/` loads at once and the catalogue shows a
    3-second note.
- Order: B-022 (creator rooms) runs alongside; the two share only this file.
  B-023 later moves `lobby/joining.md` rule 16 with this item's line in it.
- Answers (the human, 2026-10-28, on an earlier brief of this request):
  "Approved, option A. Removed players stay out of scope."
- Open questions: none new. To overrule if the lead misread: "menu" is the
  catalogue `/`, and the French text is the title « Ce salon n'existe plus. »
  over the existing 30-day line.
<!-- SECTION:DESCRIPTION:END -->
