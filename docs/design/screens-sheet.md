# Screens sheet

`screens-sheet.html` draws every screen and state of Nock at phone width
(360 × 720) and computer width (1280 × 800, scaled down), with the strings of
`web/src/i18n/fr.json` and spec 043's. With `specs/_design.md` and `cell-sheet.html`
it is the visual reference of the web client (`_design.md` section 1). It reuses
the cell sheet's drawing of cells, so the two sheets read as one system.

## Keeping it current

The visual documentation is always current (human decision, 2026-10-22). Any change
that alters what a screen looks like updates `_design.md` (dated note) and redraws
the change here, in the same commit, before tests and code (`_design.md` section 1,
rule 3).

The page is generated; never edit the HTML by hand:

| File | Holds |
| --- | --- |
| `screens_sheet/build.py` | the parts, screens, captions and the decisions record |
| `screens_sheet/chrome.py` | bars, keyboard, Salon, menus, dialogs, plain pages |
| `screens_sheet/cells.py` | the grid cells, arrows and sample grids (ported from the cell sheet) |
| `screens_sheet/style.css` | the tokens, fonts and components of `_design.md` |
| `screens_sheet/header.html` | the page's header, width switch and summary |

```
uv run python docs/design/screens_sheet/build.py          # rebuild
uv run python docs/design/screens_sheet/build.py --check  # what the gate runs
```

The gate fails when the committed HTML is not what the sources build. The
spec-writer edits these files (it may write `docs/design/`); having no shell, it says
which screens it redrew and the lead rebuilds. The reviewer blocks a change of look
that is not drawn.

Labels on the sheet: a grey label cites the `_design.md` section or the spec a
screen follows; « Decided Pn » names a decision of 2026-10-22; a dashed label marks
what is still pending (none today), with an item in `_design.md` section 15. The page is static:
no script, the width switch is CSS. Fonts are the app's own @fontsource files once
spec 041's packages are installed, else a local copy, else the fallback stack;
never Google.

## What it covers

1. Catalogue with « Mes salons » and the history; loading, empty and error states.
2. Entry pages: nickname, refusals, expired or unknown room, page not found.
3. The room: in play, Salon (Discussion, Joueurs, host tools, muted player), Aide,
   Menu, host settings, reactions and notes, timer hidden, connection lost,
   catch-up, opening.
4. Help: check, reveal, vote, help switched off.
5. Completion: full but wrong, solved, recap and its states, shared recap page.
6. Account: sign-in sheet in a room and on the catalogue, account page, deletion.
7. Operator page (spec 038): token, dashboard, replay.
8. Keyboard; 9. « Auteurs » and « Accessibilité »; 10. small states.
11. Later: competitive modes (specs 030 and 031), named only.
12. Decisions: the record below.
13. Specs 044 to 048: their open questions, decided with their approval of
    2026-10-22 and drawn as decided (version 1.4): the grid page `/g/N`, tablets in
    portrait and landscape, the low keyboard, the wrapped Auteurs legend, the end of a
    vote and a vote from a snapshot, the recap with a player who left, the end band at
    320 px, the disabled « Envoyer », the plain pages while loading, and the replay of
    FX-02 in one column with its states.

## Decisions (human, 2026-10-22)

The human accepted every recommended answer of version 1.0. `_design.md` section 15
lists them with the sections that now carry them: P1 plain pages on a computer, P2
the opening room, P3 an expired room, P4 catalogue states, P5 the host's mute in
Joueurs and the chat notes, P6 the vote after voting, P7 spent reveal items, P8 the
empty clue bar's text, P9 « Rien à annuler. » as a note, P10 recap states, P11 the
shared recap page, P12 the account page and deletion (no red button), P13 the
account sheet's intro outside a room, P14 the operator page, P15 the slider, P16
« Lien copié » in the recap, D1 no « danger » button, D2 no grid credits for now,
D3 the sheet's fonts.

Where the sheet met spec 043, spec 043's version is decided, by the human's approval
of spec 043 on 2026-10-22 (`_design.md` section 15):

1. The Joueurs row: the state and the current clue on a second line under the
   name; the host's buttons on the right of the first (not P5's second line of
   buttons).
2. Help mode `none`: « Aide » stays, with the pencil confirm or « L'aide est
   désactivée dans ce salon. » (not P7's hidden button).
3. Réagir and Je bloque with nothing selected: disabled in rule grey (not P8's
   hidden buttons).
