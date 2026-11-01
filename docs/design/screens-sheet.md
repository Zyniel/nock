# Screens sheet

`screens-sheet.html` draws every screen and state of Nock at phone width
(360 × 720) and computer width (1280 × 800, scaled down), with the strings of
`web/src/i18n/fr.json`. With the design files in `specs/_design/` and
`cell-sheet.html` it is the visual reference of the web client
(`specs/_design/foundation.md`, « Authority »). It reuses the cell sheet's drawing
of cells, so the two sheets read as one system.

## Keeping it current

The visual documentation is always current. Any change that alters what a screen
looks like updates the design file of that part of the screen and redraws the
change here, in the same commit, before tests and code (`foundation.md`,
« Authority », rule 3).

The page is generated; never edit the HTML by hand:

| File | Holds |
| --- | --- |
| `screens_sheet/build.py` | the parts, screens and captions |
| `screens_sheet/chrome.py` | bars, keyboard, Salon, menus, dialogs, plain pages |
| `screens_sheet/cells.py` | the grid cells, arrows and sample grids (ported from the cell sheet) |
| `screens_sheet/style.css` | the tokens, fonts and components of the design files |
| `screens_sheet/header.html` | the page's header, width switch and summary |

```
uv run python docs/design/screens_sheet/build.py          # rebuild
uv run python docs/design/screens_sheet/build.py --check  # what the gate runs
```

The gate fails when the committed HTML is not what the sources build. The
spec-writer edits these files (it may write `docs/design/`); having no shell, it says
which screens it redrew and the lead rebuilds. The reviewer blocks a change of look
that is not drawn.

Labels on the sheet: a grey label cites the design file and section
(« pages · Catalogue ») or the spec a screen follows; a dashed label marks what is
still pending (none today), with a task in `backlog/`. The page is static: no
script, the width switch is CSS. Fonts are the app's own @fontsource files once the
web client's packages are installed, else a local copy, else the fallback stack;
never Google.

## What it covers

1. Catalogue with « Mes salons » and the history; loading, empty and error states;
   the grid page `/g/N`; tablets in portrait and landscape.
2. Entry pages: nickname, refusals, expired or unknown room, page not found.
3. The room: in play, Salon (Discussion, Joueurs, host tools, muted player, the
   message box), Aide, Menu, host settings, reactions and notes, timer hidden,
   connection lost, a final status, focus rings, catch-up, opening.
4. Help: check, reveal, vote (from a snapshot, closed), help switched off.
5. Completion: full but wrong, solved, the status in the clue bar's row, the end
   band at 320 px, recap and its states, a player who left, shared recap page.
6. Account: sign-in sheet in a room and on the catalogue, account page, deletion,
   plain pages while they load.
7. Operator page: token, dashboard, replay, FX-02 in one column, its states.
8. Keyboard: pencil, hidden, a phone held sideways (keyboard shown or hidden), the
   fourth slot and the keys.
9. « Auteurs » (with a wrapped legend) and « Accessibilité ».
10. Small states.
11. Later: competitive modes (B-002), named only.
