# The room page

The room page `/r/<code>` once the room has shown: its two layouts, top bars, clue
bar, in-app keyboard, menus, Salon, notes, reactions, bands, sheets and layers.
Tokens, type, icons and components: `foundation.md`. The cells: `cells.md`. The
vote banner, the end-of-grid band, the recap and the room-gone dialog:
`overlays.md`. The room while it opens, and the entry cards: `pages.md`.

## Which layout

Two layouts: "sheet" (panels open as a bottom sheet) and "column" (a side column
on the right).

- Column when the window is landscape (`innerWidth > innerHeight`) and at least
  900 px wide.
- A phone held sideways (landscape, at most 500 px high) has the column only while
  its in-app keyboard is hidden.
- Otherwise, sheet.

Together: column when the window is landscape and either at least 900 px wide and
more than 500 px high, or at most 500 px high with the in-app keyboard hidden;
otherwise sheet. A solved grid has no keyboard (« In-app keyboard »), so a phone
held sideways is then in the column layout.

## Phone and upright tablet (sheet layout)

Top to bottom, filling the window, nothing scrolls:

1. The phone top bar (« Phone top bar »).
2. The connection band, only while the connection is lost, or the status band
   (« Connection lost »).
3. The grid area: all the height left, white, the grid centred, cells as large as
   fit with 8 px around (the sheet keeps 16 px in total on each axis), and the
   Auteurs legend under the grid while that mode is on, or over the grid's bottom
   where its room would leave the grid under 100 px (`cells.md`, « Auteurs mode »).
4. The clue bar (« Clue bar »).
5. The end-of-grid band, when the grid is full (`overlays.md`, « End of grid »).
6. The in-app keyboard, on touch screens (« In-app keyboard »).

### Phone top bar

54 px high, white, 1 px line-grey bottom border, padding 0 4 px 0 10 px, items
centred vertically. The timer on the left (text, not a button, padding 0 4 px),
then `margin-right: auto`, then five buttons as high as the bar, each with a flex
basis of 56 px; on a window short of room they shrink equally, never below 40 px,
and the timer never shrinks. In order: Annuler, Aide, Salon, Clavier, Menu. The
fourth slot holds « Clavier » on a touch screen; on a window that is not a touch
screen, which has no in-app keyboard, it holds « Crayon ». Each button holds its
22 px icon over its label (gap 2 px), navy, radius 6 px. Pressed (Aide, Salon, Menu
while open; Clavier while the keyboard shows): word-blue background.

- Unread badge on Salon (messages): top 5 px, right 8 px (`foundation.md`,
  « Components »).
- New events and no unread message: an 8 px red dot on Salon, top 8 px, right
  15 px.
- Timer hidden (« Masquer le chrono »): the left slot holds a top-bar button
  « Chrono » with the chrono icon, `aria-label` « Afficher le chrono », which shows
  the timer again.

This bar is also the column layout's on a window at most 500 px high (« Low column
layout »).

### Clue bar

34 px high, navy, white text, in this order: ‹ button (36 px wide, chevron-left
icon), the clue text centred with its direction glyph (→ or ↓, 80 % opacity, 6 px
left margin), on one line with an ellipsis when too long; then « Réagir » (40 px
wide, smile icon, `aria-label` `reaction.button_label`); then « Je bloque » (40 px
wide, flag icon); then › (36 px wide, chevron-right icon). The two 40 px buttons
have radius 6 px. Je bloque not pressed: white outline flag; pressed
(`aria-pressed="true"`): white button background, navy filled flag. Text only: no
author name, no pencil tag. Focus inside the bar: white ring, offset −4 px
(`foundation.md`, « Components »).

With no cell selected, the text is the hint « Touchez une case ou une
définition. », and « Réagir » and « Je bloque » are drawn disabled, their icons in
`--nock-rule`, so the bar keeps its shape. While a vote is open, « Réagir » is
disabled (« Layers »).

In the column layout the clue bar is as wide as the grid (grid width + 1 px), and
never narrower than the smaller of 320 px and the play area. With the Auteurs mode
on, that width comes from the grid's box without the legend's room, so it does not
change.

On a low window the end-of-grid status may sit in the clue bar's row
(`overlays.md`, « End of grid »).

### In-app keyboard

Touch screens only. Background `--nock-keyboard-bg`, padding 6 px 3 px 8 px, rows
6 px apart, keys 4 px apart and centred.

- Rows: `A Z E R T Y U I O P`; `Q S D F G H J K L M`; `✎ W X C V B N ⇄ ⌫`.
- Keys: 44 px high, flexible width up to 33 px, radius 5 px, `--nock-key`, ink,
  shadow `0 1px 0 var(--nock-key-shadow)`, no border. ✎ and ⌫ are wide: up to
  48 px, flex basis 48 px, grow 1.5. Icons 22 px. On a window at most 500 px high
  the keys are 28 px high, so that a phone held sideways keeps 100 px of grid with
  the keyboard shown.
- ✎ (« Crayon ») pressed: navy key, white icon with `--nock-pen-fill` fill; every
  letter key then shows its letter italic in `--nock-pencil`.
- ⇄ (« Changer de sens ») switches the selected cell between its across and down
  word, as a second tap on the cell. ⌫ (« Effacer ») erases one letter. No long
  press on ⌫.
- « Clavier » hides and shows the keyboard; the choice is remembered per browser.
  The grid takes the space back. Once the grid is solved the keyboard goes away and
  « Clavier » is disabled.

## Computer and landscape tablet (column layout)

1. The computer top bar (« Computer top bar »), on a window more than 500 px high;
   on a lower one, the phone top bar (« Low column layout »).
2. The connection band or the status band under the top bar (« Connection lost »).
3. Body: the main area and, on its right, the side column.
   - Main area: padding 12 px, the grid centred and as large as fits in all the
     space left; under it the clue bar (« Clue bar »); then the end-of-grid band at
     the same width; on touch tablets the in-app keyboard under them, full
     width of the main area (margins −12 px, top 10 px).
   - Side column: 340 px wide, white, 1 px line-grey left border; the Salon
     (« Salon »). It is open by default in this layout, with « Salon » pressed.
     « Salon » closes and opens it; the grid refits each time. A column the player
     closed stays closed next time, per browser.
4. Nothing else is permanently on screen. Chat, players, progress, invitation,
   host settings and the account open on demand.

### Computer top bar

56 px high, white, 1 px line-grey bottom border, padding 0 16 px, gap 4 px, items
centred vertically, in this order: the brand link (`foundation.md`,
« Components »), then `margin-right: auto`; the timer (10 px right margin), or
« Chrono » while the timer is hidden; then buttons 38 px high, padding 0 12 px,
radius 6 px, gap 6 px, icon 20 px beside its label: Annuler, Crayon, « Aide ▾ »,
Salon, Clavier (touch screens only), Menu. Pressed: word-blue background. Unread
badge on Salon: top 2 px, left 24 px; the new-events dot, with no unread message,
at the same place. The bar shows no grid name. `room-heading` is visually hidden
in the room, on a computer and on a phone.

### Low column layout

The column layout on a window at most 500 px high (a phone held sideways with its
keyboard hidden, or a low desktop window such as 740 by 360) has the phone top bar,
54 px, its buttons 56 px wide, icons over labels, in the phone's slots and order
(« Salon » pressed while the column is open; its badge and dot at the phone's
places), the timer on the left and no brand. Under it the body of item 3 above:
the play area with its 12 px padding and the 340 px Salon column, open by default.
The menus sit as on a phone (« Menu »). Drawn in the screens sheet, part 8
(« A phone held sideways, keyboard hidden »).

## Aide menu

A popover (`foundation.md`, « Components ») under the button, min width 220 px:

- when the selected cell holds a pencil letter, first the item « Confirmer la
  lettre au crayon » (weight 600, detail ✎), then a separator;
- heading « Vérifier »; items « La lettre », « Le mot », « La grille »;
- separator;
- heading « Révéler »; items « La lettre » with the detail « n restantes », « Le
  mot » with « n restant » or « n restants » (the reveal budget).
- An item whose budget is spent stays in place, disabled: its text and detail
  muted, the detail « Plus de lettre » or « Plus de mot » (`reveal.letter_none`,
  `reveal.word_none`), no hover; the menu keeps its shape.
- In help mode « désactivée », « Aide » stays in the top bar; its menu holds the
  pencil confirm when it applies, otherwise the muted line « L'aide est désactivée
  dans ce salon. ».

The pencil toggle itself is the ✎ key on touch screens and the « Crayon » top-bar
button elsewhere.

## Menu

A popover anchored to the right (6 px from the right edge on a phone), in this
order: « Auteurs » (detail « activé » / « désactivé »); « Mots des autres »
(detail « teintés » / « sans teinte »); « Accessibilité » (detail « activée » /
« désactivée », off by default, per browser, `cells.md`, « Other players on a
cell »); « Inviter » (detail « lien »); « Réglages de l'hôte » (host only);
« Compte »; separator; « Masquer le chrono » (« Afficher le chrono » while hidden);
« Retour aux grilles ».

On a phone, a scrim (`--nock-scrim`) covers everything below the top bar (top
54 px) while a menu or a sheet is open; a tap on it closes them. Menus sit 58 px
from the top.

## Salon

- Phone: a bottom sheet, 62 % of the window height, white, radius 14 px on the
  top corners, shadow `0 -10px 30px -12px var(--nock-shadow)`, with a grab handle
  (40 by 4 px, radius 2 px, `--nock-handle`, margin 8 px auto 4 px).
- Wide windows: the side column.

Content, top to bottom:

1. Progress: « 31 / 54 mots » (words fully filled / words) then a bar: 6 px high,
   radius 3 px, word-blue track, navy fill; padding 4 px 16 px 8 px (14 px top in
   the column), gap 10 px.
2. Tabs « Discussion » | « Joueurs (n) »: two equal tabs, padding 10 px, 2 px
   bottom border (transparent, navy when selected), muted text (navy when
   selected); a 1 px line-grey border under the row.
3. Discussion: one stream, oldest first, padding 10 px 16 px, items 8 px apart,
   then the message box.
   - A message: a player dot (`foundation.md`, « Components ») and the name in
     weight 700 ink, gap 6 px, then the text. The dot is centred vertically on the
     line (`vertical-align: middle`).
   - An event: one line, 0.82rem, 16 px left padding, one line per room event (no
     grouping). Its pictogram is followed by a 0.25em gap before the text:

     | `data-kind` | Pictogram | Colour |
     | --- | --- | --- |
     | `player_joined` | → | muted |
     | `player_left`, `player_removed`, `player_timed_out` | ← | muted |
     | `check` | ✓ | muted; green when the check found no wrong letter |
     | `reveal` | ▲ | orange-red |
     | `flag` | inline filled flag icon | muted |
     | `room_locked`, `room_unlocked`, `settings_changed`, `host_changed` | none | muted |

     Catch-up lines take the same look. There is no line for typed letters or
     filled words. A vote's result line: `overlays.md`, « Vote ».
   - Message box: padding 8 px 12 px 12 px, 1 px line-grey top border, gap 8 px;
     the input (`foundation.md`, « Components », Text input, message box); the
     « Envoyer » pill (`foundation.md`, « Components »), disabled whenever sending
     is (an empty input, pacing, a page not joined, a muted player). The chat notes
     (« Patientez avant d'envoyer. », « L'hôte a coupé votre discussion. ») show as
     one muted line under the input (500 0.85rem/1.3, 12 px left padding), one at a
     time; while I am muted, the input and « Envoyer » are disabled.
4. Joueurs: padding 10 px 16 px, rows 8 px apart, 0.95rem. Each row on two lines.
   Line 1: player dot; name, « (vous) » after my own (my name weight 700); the
   « hôte » tag after the host's name (`foundation.md`, « Components »); for the
   host, on the right of each other player's row, « Couper » / « Rétablir » (the
   chat mute) and « Retirer », small secondary buttons. Line 2, under the name: the
   state word « actif », « inactif » or « déconnecté », « · » and the player's
   current clue, so the clue never ends in an ellipsis at 340 px. An inactive name
   is italic, a disconnected one italic and struck through. Under the rows, « Lien
   d'invitation » (dialog section heading), the URL box (`foundation.md`,
   « Components », Text input), full width, the primary « Copier le lien », and
   after a copy the green confirmation line « Lien copié ». « Inviter » in the Menu
   opens the Salon on this tab.

## 3-second notes

- One line, ink background, white text (`foundation.md`, « Typography »), padding
  8 px 12 px, radius 6 px, shadow `0 6px 18px -8px var(--nock-shadow-strong)`,
  centred over the top edge of the grid area, 8 px down, layer 6 of the grid area.
  No layout shift.
- While the vote banner shows, a note that shows (only « Rien à annuler. », since
  the others wait) sits 8 px under the banner's bottom edge instead, with the same
  look, layer 6 and horizontal centre, so that the banner (layer 9) never covers
  it; it moves with the banner when the banner comes, changes height or goes.
  Drawn in the screens sheet's « Help by vote ».
- A long note stays on its one line and ends with an ellipsis: at most the grid
  viewport's width in the sheet layout, that width less 16 px in the column layout,
  `overflow: hidden`, `text-overflow: ellipsis`. Drawn in the screens sheet's
  « Reactions and 3-second notes ».
- A line may start with its pictogram (the inline flag icon for a flag, ▲, →),
  followed by a 0.25em gap, as in the stream.
- One at a time; a new note replaces the current one. It shows for 3 s, then fades
  out in 0.25 s (opacity only, no slide), and leaves the page 100 ms after the
  fade's end (3,350 ms after it showed). With `prefers-reduced-motion: reduce` it
  appears and goes without transition.
- A tap opens the Salon on that line, as « Salon » does: the focus goes to the
  message box; nothing scrolls to the line.
- Not made while the stream is visible (Salon open on Discussion); a note already
  showing when the stream opens stays until its 3 s end. Held back while the vote
  banner shows: only the newest waits, shown when the banner goes, and dropped if
  the stream shows by then.
- Which events: others' messages (« Bruno : … »), « Je bloque », reveals, others'
  checks, joins and departures, and my own reaction. Never typed letters. Also two
  short answers of the room: « Rien à annuler. » after « Annuler » with nothing to
  undo, and a vote's result, « Vote accepté. », « Vote refusé. » or « Temps
  écoulé, vote annulé. », once its banner has gone.

## Reactions

- « Réagir » in the clue bar opens the picker; a second press closes it.
- Picker: `role="group"`, `aria-label` `reaction.picker_label` (« Réactions »), the
  five reactions 👍 👏 😂 😮 🤔 with their names. Over the bottom of the grid area,
  centred, 8 px above its bottom edge (so above the clue bar), layer 9: white, 1 px
  line-grey border, radius 24 px, padding 5 px, gap 2 px, shadow
  `0 10px 24px -10px var(--nock-shadow)`. Each reaction a 40 by 40 px round button
  (radius 20 px), no background (word blue on hover), emoji 22 px.
- A shown reaction: a white pill centred over its clue cell, 1 px line-grey
  border, radius 12 px, padding 2 px 6 px, emoji 16 px, line height 1.2, shadow
  `0 4px 10px -4px var(--nock-shadow-soft)`, layer 8, for 3 s. On a two-clue cell it
  is centred on its own clue's half.

## Connection lost

A band under the top bar, full width, while the room is reconnecting: background
`--nock-clue-bg`, 1 px line-grey bottom border, padding 8 px 12 px, gap 10 px,
items aligned to the top; an 8 px red dot (`--nock-red`, 5 px from the top), then
the ink text (500 0.85rem/1.3) « Connexion perdue. Vous pouvez continuer : vos
lettres seront envoyées au retour du réseau. ». The grid stays usable. The band
goes when the room is back. The band pushes the grid area down; nothing covers the
grid. `room-status` (« Reconnexion… ») is then visually hidden (class
`visually-hidden`), read by screen readers only.

The status band: a final status that comes once the room has shown (removed by the
host, replaced by another tab, the connection closed for good (« Connexion
perdue. »), and the room's other final statuses but its deletion) is the connection
band's look without the red dot: under the top bar, full width, `--nock-clue-bg`,
1 px line-grey bottom border, padding 8 px 12 px, the status text in ink 500
0.85rem/1.3, for example « Vous avez été retiré de ce salon. ». The room stays
drawn under it as it was. Drawn in the screens sheet, part 3 (« A final status
after the room showed »). The room deleted once it has shown has no band: the
connection band goes and the room-gone dialog shows (`overlays.md`, « Room
gone »). A refusal before the room shows is an entry card (`pages.md`, « Entry
and not-found pages »).

## Room sheets: host settings and account

On a phone these open as a bottom sheet from under the top bar (scrim from 54 px),
white, radius 16 px on the top corners, padding 14 px 18 px 18 px, gap 14 px; on a
computer as the recap's dialog (440 px, `overlays.md`, « Recap »).

- Host settings, from Menu « Réglages de l'hôte »: title « Réglages de l'hôte »; a
  switch row « Verrouiller le salon » (switch, `foundation.md`, « Components »);
  the field « Aide » with a three-way segmented control « libre » | « par vote » |
  « désactivée »; two number fields side by side, 16 px apart, « Lettres à
  révéler » and « Mots à révéler » (inputs 64 px wide, text centred); primary
  « Enregistrer », right-aligned.
- Account, from Menu « Compte » or the catalogue's « Compte ». Signed out: title
  `account.dialog_heading`, text `account.dialog_intro` (muted 0.9rem), field
  « Adresse e-mail », primary « Recevoir le lien », after sending the green line
  (« Lien envoyé à … Il est valable 30 minutes. »), secondary « Fermer »
  right-aligned. Signed in: title « Votre compte », « Connecté avec {email} », the
  text link « Gérer mon compte », secondary « Fermer » right-aligned. Outside a
  room (the catalogue's « Compte »), the intro is `account.signed_out_intro`, since
  `account.dialog_intro` speaks of « ce salon ».

## Layers

| Layer | z-index |
| --- | --- |
| 3-second note | 6 |
| Auteurs legend lying over the grid (`cells.md`, « Auteurs mode ») | 6 |
| Phone scrim | 7 |
| Menus, popovers, sheets, shown reaction | 8 |
| Vote banner, reaction picker | 9 |
| Recap overlay, room-gone overlay (dialog or sheet with its scrim) | 20 |

The vote banner is drawn above the Salon sheet and the scrim, which come later in
the page. The banner and the picker never show together. The room-gone overlay
closes the recap, so the two never show together either. The Auteurs legend under
the grid is in the flow and has no layer.
