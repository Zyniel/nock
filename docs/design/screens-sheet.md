# Screens sheet

`screens-sheet.html` draws every screen and state of Nock as it exists on `main`
(2026-10-22) in the validated design: the tokens, player colours, type, icons and
components of `specs/_design.md`, and the cells of `cell-sheet.html`, whose cell
drawing it reuses so the two sheets read as one system. It is a design document,
not a spec: nothing in it binds the code until `_design.md` and the specs take it in.

Each screen is drawn at phone width (360 × 720) and at computer width (1280 × 800,
scaled down), with the strings of `web/src/i18n/fr.json`. The page is static (no
script); a CSS-only switch shows both widths, phones only, or computers only. Fonts
are the app's own files from `web/node_modules/@fontsource` once spec 041's packages
are installed, else a local copy, else the fallback stack; never Google.

A grey label on a screen cites the `_design.md` section or the spec it follows. A
dashed orange-red label marks a proposal where `_design.md` says nothing; each one
is listed below, as in the sheet's last part.

## What it covers

1. Catalogue: « Mes salons », filter chips, grid cards, « Grilles terminées »;
   loading, empty and error states; « Jouer » failing.
2. Entry pages: nickname form (with its error), the refusal cards (full, locked,
   removed, other tab, throttled), the expired or unknown room, page not found.
3. The room: in play, Salon Discussion (and paced chat), Joueurs with the invite link
   and the host's tools, a muted player, Aide, Menu, host settings, reactions and
   3-second notes, timer hidden with the new-events dot, connection lost, catch-up,
   opening the room.
4. Help: check, reveal, help by vote (asked, voted, waiting), help switched off.
5. Completion: full but not right, solved, the recap (and its loading and error),
   the shared recap page.
6. Account: the sign-in sheet in a room and on the catalogue, the account page,
   deletion, and the page's other states.
7. Operator page (spec 038): token form, dashboard, room replay.
8. The in-app keyboard: normal, pencil on, hidden, on a touch computer.
9. « Auteurs » and « Accessibilité » modes.
10. Small states: notes, clue bar states, buttons, fields, switch, segmented
    control, slider.
11. Later: competitive modes (specs 030 and 031) are not drawn, only named.

Where the lead decided an open item of `_design.md` on 2026-10-22 (branch
`design-specs`, not yet on `main`: « Compte » placed after « Réglages de l'hôte »,
the new-events dot on a computer, a reaction on a two-clue cell), the sheet follows
that decision.

## Proposals and decisions to take

Each item: what the sheet proposes (recommended), and the alternative.

- **P1 Plain pages on a computer** (entry, not found, account page, shared recap).
  Recommended: the phone's column, centred, at most 420 px, 48 px under the 56 px
  top bar, on the page grey. Alternative: a wide two-column page.
- **P2 The room while it connects and joins.** Recommended: the top bar in place,
  one muted line (« Connexion… », « Entrée dans le salon… ») where the grid will be;
  no clue bar, no keyboard, no spinner. Alternative: a skeleton grid.
- **P3 An expired room.** Recommended: the not-found card « Ce salon n'existe pas. »
  plus a muted line « Un salon est effacé 30 jours après sa dernière modification. »
  (a new fr.json key) and « Voir les grilles » primary. Alternative: no extra line.
- **P4 Catalogue and « Mes salons » states.** Recommended: one line where the content
  will be, muted while loading or empty, red on error; a failed « Jouer » shows its
  red line inside the card; « Mes salons » shows nothing while loading and no section
  when empty. Alternative: skeleton cards.
- **P5 Chat moderation and chat notes** (spec 022's « Sourdine » block, « Patientez
  avant d'envoyer. », « L'hôte a coupé votre discussion. »). Recommended: the host's
  « Couper » / « Rétablir » as small secondary buttons beside « Retirer », on a line
  under each other player's row in Joueurs; the notes as one muted line under the
  message box; a muted player's box disabled. Alternative: keep a « Sourdine » block
  in the Discussion tab.
- **P6 The vote after voting, and its result.** Recommended: after my vote the
  buttons give way to a muted « Vote enregistré. En attente des autres joueurs… »;
  the asker sees « En attente des autres joueurs… »; the result is a 3-second note
  and a stream line. Alternative: keep the buttons with the chosen one pressed.
- **P7 Help with no budget, and help switched off.** Recommended: spent reveal items
  stay, muted and inert, with « Plus de lettre » / « Plus de mot » as the detail; in
  « désactivée » mode the Aide button is not drawn (confirms `_design.md` §12's « to
  confirm »). Alternative: hide spent items, or show Aide disabled.
- **P8 Clue bar with nothing selected.** Recommended: « Touchez une case ou une
  définition. » with the ‹ › chevrons only; Réagir and Je bloque not drawn.
  Alternative: show them disabled (needs a disabled look on navy).
- **P9 « Rien à annuler. »** Recommended: a 3-second note. Alternative: disable
  « Annuler ».
- **P10 Recap loading and unavailable.** Recommended: inside the sheet or dialog, the
  title, then a muted « Chargement du bilan… » or the red « Le bilan n'est pas
  disponible. », and « Fermer ».
- **P11 Shared recap page `/recap/<token>`.** Recommended: an entry page with one
  card: « Grille terminée », « Grille n° 12 », the time in the recap's large style,
  « Équipe : … », primary « Voir les grilles »; the unavailable recap uses the same
  card.
- **P12 Account page `/account` and deletion.** Recommended: an entry page with one
  card « Mon compte »; « Se déconnecter » and « Supprimer mon compte » secondary;
  the confirmation in the same card, « Supprimer définitivement » primary and
  « Garder mon compte » secondary; no red button. Alternative: a red « danger »
  button variant.
- **P13 Account sheet outside a room.** Recommended: on the catalogue the intro is
  `account.signed_out_intro`, since `account.dialog_intro` speaks of « ce salon ».
- **P14 Operator page `/ops`.** Recommended: the catalogue's frame and column; the
  token form in one card; the periods as the catalogue's filter chips; one tile per
  figure with fr.json's line as it is; the replay as the list of edits beside the
  grid (cell styles, no clue text, no arrows) with a step slider. Alternative: leave
  browser defaults.
- **P15 A slider** (the replay's step). Recommended: built from the progress bar:
  word-blue 6 px track, navy fill, 18 px navy knob, §11's focus ring; added to §11.
- **P16 « Lien copié » in the recap.** Recommended: the button keeps « Copier le
  lien » and the green « Lien copié » line appears under it, as in Joueurs (spec 028
  refined; today it changes the button's text).
- **D1 Is a destructive action ever red?** Recommended: no (see P12).
- **D2 Grid credits (spec 005).** Recommended: leave them off the screens until a
  spec sends them to players; then one muted line on the catalogue card.
- **D3 The sheet's fonts.** Recommended: keep loading the app's own @fontsource
  files, else local, else the fallback stack; never Google.
