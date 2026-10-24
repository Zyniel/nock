# Pages

The pages that are not the room in play: the catalogue, the entry and not-found
pages, the plain pages (account, shared recap, operator), and the one rule of
every loading, empty and error state. Tokens, type and components:
`foundation.md`.

A page is wide on a window that is landscape, at least 900 px wide and more than
500 px high (the room's threshold for its computer top bar, `room.md`, « Which
layout »); otherwise it is narrow, a portrait tablet and a low window in the
column layout included.

## Catalogue

- Top bar 56 px as the computer room's, with the Nock mark and « Nock », and on the
  right « Compte »: a computer top-bar button with no icon, pressed while its sheet
  is open (`room.md`, « Room sheets: host settings and account »), 38 px high on a
  wide window and 34 px high on a narrow one.
- Main column: max width 920 px, centred, padding 24 px (16 px on a narrow
  window), gap 16 px, in this order:
  1. heading « Grilles » (`foundation.md`, « Typography »);
  2. « Mes salons », when the player has open rooms on this device or account:
     section heading, then list rows (`foundation.md`, « Components »), 10 px apart.
     Each row: title « Grille n° N · W × H » (and the « Terminée » pill when
     solved), « Joueurs : … », « Dernière activité : {date} à {time} », and
     « Reprendre » (primary; secondary when the room is solved);
  3. the filter row: label « Force », then chips « Toutes », « Force 1 » to
     « Force 4 »: radius 16 px, padding 7 px 14 px, 1 px line-grey border, white,
     navy text. Pressed: word-blue background, navy border;
  4. the grid cards;
  5. « Grilles terminées », when the history holds finished grids: section
     heading, then list rows: title « Grille n° N · W × H », « Terminée le {date} ·
     en {time} · Avec {names} » or « … · En solo », and secondary « Rejouer ».
- Cards in a grid: `repeat(auto-fill, minmax(min(100%, 400px), 1fr))`, gap 12 px,
  so one per row on a phone. A card: 1 px line-grey border, radius 8 px, padding
  12 px 14 px, gap 14 px, white:
  - a generic grid drawing, built from the grid's width W and height H only: it
    shows the proportions, not the real layout. An SVG 51 px high and
    round(51 × W / H) px wide (39 by 51 for 13 by 17), viewBox W × 10 by H × 10
    (10 units per cell): white cells; clue cells in `--nock-thumb` in row 0 at the
    even columns (0, 2, 4, …) and in column 0 at the even rows from 2 (2, 4, …);
    inner grid lines in `--nock-line`, 1 unit wide; a 1 px rule-grey border. Shown
    only while the cards sit more than one per row (wide windows); with one card
    per row the card has no drawing and keeps its text only. Drawn in the cell
    sheet's `genericThumb()`;
  - « Grille n° N » and, after it, the status pill: « Commencée » (word blue,
    navy) or « Terminée » (green background, green text), radius 12 px, padding
    3 px 9 px;
  - « Publiée le … »;
  - four Nock marks (8 by 11 px, gap 2 px), navy up to the grid's force and
    `--nock-thumb` after, then « Force F · W × H · N mots ». Force is written, so
    it never relies on the drawing alone;
  - the primary button « Jouer » on the right (padding 9 px 16 px).
- Loading, empty and error states: « States: opening, loading, empty, error ».
- Grid credits are not on the screens while no spec sends them to players; when
  one does, they take one muted card line (« Auteur : … »).

## Entry and not-found pages

Pages shown instead of the room: a top bar 54 px with the Nock mark and « Nock »
only (padding 0 14 px), then the page on `--nock-page`, padding 20 px 16 px, gap
14 px, holding:

- the room code line « Salon {code} » (muted, 600 0.85rem), above the card, on
  room pages;
- one card (`foundation.md`, « Components »).

Cards:

- Nickname: title « Choisissez un pseudo »; field « Pseudo »; when refused, the
  input's border turns red and the error text shows in red under the field;
  primary « Entrer dans le salon ».
- Entry statuses (full, locked, not found, removed, replaced, throttled): the
  status text as the card title, a muted line when the status has one, secondary
  « Voir les grilles ».
- Not found: title « Page introuvable », primary « Voir les grilles », no room code
  line.
- A room that is not found or has expired (an expired room is deleted, so both
  read « Ce salon n'existe pas. »): the status card with the muted line « Un salon
  est effacé 30 jours après sa dernière modification. » and « Voir les grilles »
  primary, the only way on.

On a wide window these pages, and the plain pages below, use the 56 px top bar of
the catalogue and the phone's column, centred, at most 420 px wide, 48 px under the
top bar (page padding 48 px 24 px), on `--nock-page`.

## Plain pages: account, shared recap, operator

Drawn in the screens sheet, parts 5 to 7.

- Shared recap `/recap/<token>`: an entry page with no room code line and one
  card: title « Grille terminée » (`share.heading`), « Grille n° N » (card
  secondary text), « Temps : m:ss » in the recap time style (`foundation.md`,
  « Typography »), « Équipe : … » (card text), « Voir les grilles », a link drawn
  as a primary button. While it loads, the card holds only the muted line
  « Chargement du bilan… ». The unavailable recap is the same card with the title
  « Ce bilan n'est pas disponible. » and the button.
- Account page `/account`: an entry page with one card titled « Mon compte ».
  While its first request runs, the card holds its title only (no line, so a
  signed-in player never sees the signed-out form flash). Signed in: « Connecté
  avec {email} », the text link « Retourner au salon {code} » when there is one,
  then « Se déconnecter » and « Supprimer mon compte », both secondary, side by
  side (gap 8 px, wrapping). « Supprimer mon compte » is a disclosure: it asks once
  more in the same card, 12 px under a line-grey divider: the warning
  (`account.delete_warning`) in ink, then « Supprimer définitivement » (primary)
  and « Garder mon compte » (secondary); while asked, « Supprimer mon compte »
  shows pressed (quiet), and a second press closes the question, as « Garder mon
  compte » does. No red button: red keeps its one job (`foundation.md`, « Colour
  tokens »). The other states are one line in the card (« States »): « Connexion… »
  muted, the invalid link as an error line above the e-mail field and « Recevoir le
  lien », « Votre compte a été supprimé. » as a confirmation line with « Voir les
  grilles » primary, the generic error as an error line. Only a refused address
  (not a refusal for too many requests or a failed send) turns the e-mail input's
  border red.
- Operator page `/ops`: the catalogue's frame (top bar with the brand only, the
  920 px column on `--nock-page`), heading « Exploitation » in the catalogue
  heading style. The token form is one card: the field « Jeton d'opérateur » (a
  password input), the error line « Jeton refusé. » or « Trop d'essais… » under
  it, primary « Ouvrir ». Then a card « Tableau de bord » (card title): the field
  « Période » with the three periods as the catalogue's filter chips, the label
  naming the chips' group, then one tile per figure (white, 1 px line-grey border,
  radius 8 px, padding 12 px 14 px, in a grid of `repeat(auto-fill, minmax(min(100%,
  270px), 1fr))`, gap 10 px) holding the `fr.json` line as it is. Then a card
  « Relecture d'un salon »: the field « Code du salon » with « Relire » (primary)
  beside it; « Salon introuvable. » is an error line under the form. The edits, one
  line each (0.85rem, tabular), the current step on word blue and weight 600, later
  steps muted; the grid at the chosen step, drawn with the cells of `cells.md` with
  no clue text, no arrows and no players, showing the playing grid's marks at that
  step: pencil (italic, pencil grey), locked (bold on locked grey), revealed
  (locked plus the notch); under it the field « Étape » with the slider
  (`foundation.md`, « Components ») and « Étape n sur m » (card secondary text). On
  a window at least 900 px wide the edits sit left of the grid, gap 20 px, and the
  cells are `min(44, …)` px; narrower, the grid, the slider, then the edits, and
  the cells `min(36, …)` px; either way they shrink to the whole px that fits the
  card (FX-02's 13 columns get 22 px on a 360 px phone). A room with no edit shows
  its muted line « Aucune modification dans ce salon. » only, with no grid and no
  slider.

## States: opening, loading, empty, error

One rule for every page: a state is one line of text where its content will be:
muted (`--nock-muted`) while waiting or when empty, an error line
(`foundation.md`, « Components ») when something failed, a confirmation line when
done. No spinner, no skeleton: no `<progress>`, no `role="progressbar"`, and no CSS
animation anywhere in the client (`@keyframes`, `animation`, and their
vendor-prefixed forms); transitions (the note's fade) stay.

Its size and role depend on where the line stands:

- For a page's whole content (the catalogue, the grid page, the opening room): a
  waiting or empty line is 400 16 px/1.5 (1rem), muted; a failure is an error line.
  None of them has a role, the catalogue's and « Mes salons »'s load-error lines
  included.
- Inside a card, a sheet or a dialog (the recap, the shared recap page, the account
  page, the operator page): a waiting or empty line is 400 0.95rem (the card text
  size), muted. A waiting line and a confirmation line are announced politely
  (`role="status"`), an error line at once (`role="alert"`), an empty line not at
  all.
- The error line of a failed action (« Jouer », « Rejouer », a refused nickname,
  address or operator token) is announced at once (`role="alert"`).

Where each shows:

- Opening the room: before the first snapshot, the room's top bar is in place,
  inert, with no timer yet, and the grid area holds one line, « Connexion… » or
  « Entrée dans le salon… » (`room-status`); no clue bar, no keyboard. A refusal
  before the join then shows its card (« Entry and not-found pages »); a final
  status after a snapshot shows the status band (`room.md`, « Connection lost »).
- Catalogue: « Chargement… », « Aucune grille pour le moment. » (the chips are not
  shown) and « Aucune grille de cette force. » (the chips stay) as muted lines
  under the heading, « Impossible de charger les grilles. » as an error line there;
  a failed « Jouer » puts « Impossible de lancer la partie. Réessayez. » as an error
  line inside its card, under its text. « Mes salons » shows nothing while it loads
  and has no section when there is no room; « Impossible de charger vos salons. »
  is an error line under its heading.
- Recap: inside its sheet or dialog, the title, then « Chargement du bilan… »
  muted or « Le bilan n'est pas disponible. » as an error line, and « Fermer ».
- The plain pages: « Plain pages: account, shared recap, operator ».
