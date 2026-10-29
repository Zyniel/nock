# Room overlays

What comes over or under the play area of the room page: the vote banner, the
end-of-grid band, the recap and the room-gone dialog. Tokens, type and components:
`foundation.md`. The room's layouts and layers: `room.md`.

## Vote

A banner over the top of the grid area: 8 px from its top, left and right edges,
white, 2 px navy border, radius 10 px, padding 10 px 12 px, gap 8 px, shadow
`0 10px 24px -12px var(--nock-shadow)`, layer 9, above the Salon sheet and the
scrim (`room.md`, « Layers »). Content: the question (`vote.question.*`); a row with
« Oui » (primary) and « Non » (secondary), both with padding 7 px 16 px, and on the
right the seconds left (« 18 s »); then a progress bar 4 px high, radius 2 px,
word-blue track, navy fill for the time left. No layout shift. Notes wait while it
shows; « Rien à annuler. », which does not wait, shows 8 px under its bottom edge
(`room.md`, « 3-second notes »).

Once I have voted, « Oui » and « Non » give way to the muted line « Vote
enregistré. En attente des autres joueurs… » (500 0.85rem/1.3) in their row, the
seconds kept on the right; the player who asked sees « En attente des autres
joueurs… » there from the start.

The seconds and the bar count from the moment the page learned that the vote
opened, updated at least every 250 ms with no transition; a page that learned of
the vote only from a snapshot (a reload, a late joiner) does not know when it
opened and shows neither, keeping the question and the row.

The banner goes as soon as the vote closes and never shows the result itself. The
result is a 3-second note (`room.md`, « 3-second notes ») and a line in the stream,
muted, with no pictogram, for every outcome.

## End of grid

A band under the clue bar, padding 8 px 12 px, gap 10 px, text 600 0.95rem/1.2:

- Finished: background `--nock-green-bg`, green text « ✓ Grille terminée, bravo ! »
  and, pushed right, the primary button « Voir le bilan » (padding 7 px 12 px,
  0.85rem), which opens the recap. A solved grid has no in-app keyboard (`room.md`,
  « In-app keyboard »).
- Full but wrong: background `--nock-clue-bg`, navy text « Grille complète, mais
  pas encore juste. ». No red, no cell changes look. It sits between the clue bar
  and the keyboard, which stays.
- On a window too narrow for the text and « Voir le bilan » on one line (320 px),
  the text wraps onto a second line and the button keeps its whole label on one
  line, on the right, centred on the text; the band grows by the line.
- In the clue bar's row: in the sheet layout on a touch screen on a window at most
  500 px high, where the in-app keyboard shows and a band would take the grid's
  last height, the status is no band. It sits in the navy clue bar, after the clue
  text and before « Réagir », on one line: white text 600 0.95rem/1.2, padding
  0 8 px, gap 10 px, no background; the clue text gives it its width (ellipsis).
  Only full but wrong takes the row: « Grille complète, mais pas encore juste. » in
  white. A solved page has no in-app keyboard, so its status is always the band
  above. Drawn in the screens sheet, part 5 (« The status in the clue bar's row »).

## Recap

Opens only when asked.

- Phone: a bottom sheet over a `--nock-scrim-dialog` scrim covering the whole
  window, radius 16 px on the top corners, padding 14 px 18 px 18 px, no grab
  handle; at most the window height less 54 px high, scrolling inside.
- Computer: a dialog 440 px wide, centred, over a `--nock-scrim-dialog` scrim
  covering the whole window, white, radius 12 px, padding 20 px 22 px, gap 14 px,
  shadow `0 20px 40px -16px var(--nock-shadow-strong)`; at most the window height
  less 32 px high.
- The frame follows the room's layout (`room.md`, « Which layout »): the dialog in
  the column layout, the sheet in the sheet layout.

Content in order: title « Bilan de la partie »; « Temps : m:ss » (recap time
style); the lines « Vérifications : n », « Révélations : … », « Lettres révélées :
n » (gap 4 px); heading « Qui a fait quoi »; one row per player (dot, name,
« (vous) » in muted after mine, and on the right « n lettres · n mots
complétés »), rows 8 px apart. On the phone the value wraps under the name, 18 px
in; on a computer, when a long name leaves no room, it wraps under the name and
stays on the right, its right edge on the list's. A player the page no longer knows
(who left before the recap opened) has no dot: their row keeps a 10 px empty slot
so the names stay aligned, and their nickname names them. Then heading « Lien à
partager »; the URL box and « Copier le lien » (secondary, padding 8 px 12 px),
sharing one row on a computer (the box takes the width left, gap 8 px), the button
under the full-width box on a phone; « Fermer » (primary), right-aligned. Échap
closes it.

After a copy, « Copier le lien » keeps its label and the confirmation line « Lien
copié » shows under the box and button's row, as in the Joueurs tab (`room.md`,
« Salon »). Loading and unavailable: `pages.md`, « States: opening, loading, empty,
error ».

## Room gone

The room deleted once it has shown. The recap's frame (« Recap »): the 440 px
dialog in the column layout, the bottom sheet in the sheet layout, over the
`--nock-scrim-dialog` scrim covering the whole window, top bar included, at the
recap's layer (`room.md`, « Layers »). Content in order: the title « Ce salon
n'existe plus. » in the recap's title style; the line « Un salon est effacé
après un certain temps sans modification. » in muted (0.95rem); « Voir les grilles »
(primary), right-aligned. No « Fermer » and no close button. Under the scrim the
room stays drawn as it was, without the connection band or a status band. Drawn
in the screens sheet, part 3 (« The room deleted after it showed »).
