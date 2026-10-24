"""Building blocks for the screens sheet: cells, grids, bars, panels.

Ported from docs/design/cell-sheet.html (its script), so the two sheets draw
cells the same way. Everything here returns static HTML strings.
"""

from __future__ import annotations

import html
import math

P = [
    "#604800",
    "#608838",
    "#008878",
    "#6838E0",
    "#B83850",
    "#D000A0",
    "#B06000",
    "#784030",
]
INK = [
    "#604800",
    "#4B6A2C",
    "#006D60",
    "#6838E0",
    "#AD354B",
    "#B3008A",
    "#904F00",
    "#784030",
]
NAMES = ["Ana", "Bruno", "Céline", "Dédé", "Éloïse", "Farid", "Gus", "Hugo"]


def esc(s: str) -> str:
    """Escape text for HTML."""
    return html.escape(s, quote=False)


def mix(hexv: str, pct: float) -> str:
    """Return a hex colour mixed with white (pct of the colour)."""
    h = hexv.lstrip("#")
    out = "#"
    for i in range(3):
        v = int(h[i * 2 : i * 2 + 2], 16)
        out += f"{round(v * pct + 255 * (1 - pct)):02x}"
    return out


# ---------- icons (foundation.md, « Icons ») ----------
def svg(inner: str, cls: str = "") -> str:
    """Return a 24-unit outline icon."""
    c = f' class="{cls}"' if cls else ""
    return f'<svg{c} viewBox="0 0 24 24" aria-hidden="true">{inner}</svg>'


IC = {
    "undo": svg('<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>'),
    "aide": svg(
        '<path d="M9 18h6M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 '
        '1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/>'
    ),
    "salon": svg('<path d="M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z"/>'),
    "kbd": svg(
        '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 '
        '10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>'
    ),
    "menu": svg('<path d="M4 7h16M4 12h16M4 17h16"/>'),
    "pen": svg('<path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/>'),
    "swap": svg('<path d="M4 8h14l-3-3M20 16H6l3 3"/>'),
    "del": svg('<path d="M9 5h11v14H9l-6-7 6-7z"/><path d="M13 9l4 6M17 9l-4 6"/>'),
    "chrono": svg(
        '<circle cx="12" cy="13.5" r="7.5"/><path d="M12 10v3.5l2.5 2M9.5 3h5M12 3v3"/>'
    ),
    "flag": svg('<path d="M6 21V4"/><path d="M6 4h12l-3 4.5 3 4.5H6z"/>'),
    "chev_l": svg('<path d="M15 5l-7 7 7 7"/>'),
    "chev_r": svg('<path d="M9 5l7 7-7 7"/>'),
    "smile": svg(
        '<circle cx="12" cy="12" r="9"/><path d="M8.5 14.5c1.8 2 '
        '5.2 2 7 0"/><path d="M9 9.5h.01M15 9.5h.01"/>'
    ),
}
FLAG_ICO = (
    '<svg class="ico filled" viewBox="0 0 24 24" aria-hidden="true"><path '
    'd="M6 21V4" fill="none"/>'
    '<path d="M6 4h12l-3 4.5 3 4.5H6z"/></svg>'
)
NOCK = (
    '<svg viewBox="0 0 10 14" aria-hidden="true"><polygon points="0,0 '
    '10,0 10,14 5,10 0,14"/></svg>'
)

PICONS = [
    '<circle cx="5" cy="5" r="4.4"/>',
    '<rect x="0.9" y="0.9" width="8.2" height="8.2"/>',
    '<polygon points="5,0.4 9.7,9.3 0.3,9.3"/>',
    '<polygon points="5,0.1 9.9,5 5,9.9 0.1,5"/>',
    (
        '<polygon points="5,0.2 6.3,3.6 9.9,3.7 7.1,6 8.1,9.6 5,7.5 '
        '1.9,9.6 2.9,6 0.1,3.7 3.7,3.6"/>'
    ),
    (
        '<polygon points="3.3,0.4 6.7,0.4 6.7,3.3 9.6,3.3 9.6,6.7 '
        '6.7,6.7 6.7,9.6 3.3,9.6 3.3,6.7 0.4,6.7 0.4,3.3 3.3,3.3"/>'
    ),
    '<path d="M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z"/>',
    '<polygon points="0.6,0.6 9.4,0.6 5.6,5 9.4,9.4 0.6,9.4 4.4,5"/>',
]


def picon(p: int, size: int) -> str:
    """Return a player's Accessibilité icon at the given size."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 10 10" aria-hidden="true" '
        f'style="fill:var(--player-colour-{p});display:inline-block;vertical-align:mid'
        f'dle;flex:none">{PICONS[p]}</svg>'
    )


def dot(p: int, access: bool = False) -> str:
    """Return a player dot, or the player's icon in Accessibilité mode."""
    if access:
        return picon(p, 12)
    return f'<i class="pdot" style="background:var(--player-colour-{p})"></i>'


# ---------- arrows (cells.md, « Direction arrows ») ----------
ARROWS = {
    "right": '<path d="M2 12H15"/><polygon points="14,7.5 22,12 14,16.5"/>',
    "down": '<path d="M12 2V15"/><polygon points="7.5,14 12,22 16.5,14"/>',
    "down_then_right": (
        '<path d="M5 2V10Q5 15 10 15H15"/><polygon points="14,10.5 ' '22,15 14,19.5"/>'
    ),
    "right_then_down": (
        '<path d="M2 5H10Q15 5 15 10V15"/><polygon points="10.5,14 ' '15,22 19.5,14"/>'
    ),
}


def fmt(v: float) -> str:
    """Return a number with at most two decimals."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def arrow_svg(kind: str, style: str) -> str:
    """Return a direction arrow (cells.md) with its box style."""
    return (
        '<svg class="arw" viewBox="0 0 24 24" '
        f'style="{style}" aria-hidden="true">{ARROWS[kind]}'
        "</svg>"
    )


def arrow_for(kind: str, s: float, slot: int | None = None, shift: bool = False) -> str:
    """Return a direction arrow placed in its letter cell."""
    a = max(9, s * 0.26)
    if kind == "down_then_right" and shift:
        return arrow_svg(kind, f"top:-1px;left:{fmt(s * 0.4)}px")
    if kind == "right":
        if slot == 0:
            top = s * 0.25 - a / 2
        elif slot == 1:
            top = s * 0.72 - a / 2
        else:
            top = s / 2 - a / 2
        return arrow_svg(kind, f"left:-1px;top:{fmt(top)}px")
    if kind == "down":
        return arrow_svg(kind, f"top:-1px;left:{fmt(s / 2 - a / 2)}px")
    if kind == "down_then_right":
        return arrow_svg(kind, f"top:-1px;left:{fmt(s * 0.06)}px")
    return arrow_svg(kind, f"left:-1px;top:{fmt(s * 0.06)}px")


def arrow_map(clues: dict, s: float, w: int, h: int) -> dict:
    """Return the arrows of each letter cell, collision rules applied."""
    at: dict[tuple[int, int], list] = {}
    for (r, c), lst in clues.items():
        for i, q in enumerate(lst):
            t = (r, c + 1) if q["arrow"] in ("right", "right_then_down") else (r + 1, c)
            if t[0] >= h or t[1] >= w or t in clues:
                continue
            at.setdefault(t, []).append((q["arrow"], i))
    out = {}
    for k, lst in at.items():
        kinds = [x[0] for x in lst]
        rights = kinds.count("right")
        res = []
        for kind, i in lst:
            slot = None
            if kind == "right":
                if "right_then_down" in kinds:
                    slot = 1
                elif rights > 1:
                    slot = i
            res.append(
                arrow_for(
                    kind,
                    s,
                    slot,
                    kind == "down_then_right" and "right_then_down" in kinds,
                )
            )
        out[k] = res
    return out


# ---------- cells ----------
CORNERS = ["tl", "tr", "br", "bl"]
POINTS = {
    "tl": "0,0 10,0 0,10",
    "tr": "0,0 10,0 10,10",
    "br": "10,0 10,10 0,10",
    "bl": "0,0 10,10 0,10",
}


def corners(lst: list[int], s: float, access: bool) -> str:
    """Return the corner triangles (or icons) of the players on a cell."""
    t = max(6, round(s * 0.3))
    out = ""
    for i, p in enumerate(lst[:4]):
        k = CORNERS[i]
        if access:
            size = max(6, round(s * 0.24))
            off = max(1, round(s * 0.04))
            pos = (
                ("top:" if k[0] == "t" else "bottom:")
                + f"{off}px;"
                + ("left:" if k[1] == "l" else "right:")
                + f"{off}px;"
            )
            out += (
                f'<span class="tri" style="{pos}width:{size}px;height:{size}px"><svg '
                'viewBox="0 0 10 10" '
                f'aria-hidden="true" style="fill:var(--player-colour-{p}'
                f')">{PICONS[p]}</svg></'
                "span>"
            )
            continue
        out += (
            f'<span class="tri {k}" style="width:{t}px;height:{t}px"><svg '
            'viewBox="0 0 10 10" preserveAspectRatio="none" '
            f'aria-hidden="true"><polygon points="{POINTS[k]}" '
            'style="fill:var(--player-co'
            f'lour-{p})"/></svg></span>'
        )
    return out


FLAG_CELL = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 '
    '21V4"/><path d="M6 4h12l-3 4.5 3 4.5H6z"/></svg>'
)


def cell(o: dict, s: float) -> str:
    """Return one grid cell (cells.md)."""
    cls = ["c", *list(o.get("cls", []))]
    style = ""
    tint = o.get("tint")
    if tint is not None and not ({"sel", "locked", "word"} & set(cls)):
        style += (
            f"background:color-mix(in srgb, var(--player-colour-{tint}) "
            "16%, var(--nock-white));"
        )
    if o.get("flash") is not None:
        cls.append("flash")
        style += (
            f"background:color-mix(in srgb, var(--player-colour-{o['flash']}) "
            "38%, var(--nock-white));"
        )
    h = ""
    typ = o.get("type")
    if typ == "empty":
        cls.append("empty")
    elif typ == "clue":
        cls.append("clue")
        active = o.get("active") or []
        for i, q in enumerate(o["clues"]):
            if i:
                h += '<div class="sep"></div>'
            act = " active" if i < len(active) and active[i] else ""
            flag = (
                '<span class="flag">' + FLAG_CELL + "</span>" if q.get("flag") else ""
            )
            text = "" if o.get("blank") else esc(q["text"])
            h += f'<div class="q{act}">{flag}<span>{text}</span>'
            if o.get("reaction") and o["reaction"][0] == i:
                h += f'<span class="react">{o["reaction"][1]}</span>'
            h += "</div>"
    else:
        letter = o.get("letter")
        lc = ""
        if o.get("authors") and o.get("author") is not None and "rev" not in cls:
            lc = f' style="color:var(--player-ink-{o["author"]})"'
        if letter:
            h += f'<div class="ltr"{lc}><span>{esc(letter)}</span></div>'
        if o.get("caught"):
            h += '<span class="ring"></span>'
        h += corners(o.get("cursors", []), s, bool(o.get("access")))
    for a in o.get("arrows", []) or []:
        h += a
    st = f' style="{style}"' if style else ""
    return f'<div class="{" ".join(cls)}"{st}>{h}</div>'


def grid(rows: list[list[dict]], s: int, extra_style: str = "") -> str:
    """Return a grid of cells at side s."""
    out = (
        f'<div class="g" style="--s:{s}px;grid-template-columns:repeat({len(rows[0])},'
        f'{s}px);{extra_style}">'
    )
    for r in rows:
        for o in r:
            out += cell(o, s)
    return out + "</div>"


# ---------- FX-01-like phone grid (cell sheet's FX) ----------
FX_CLUES = {
    (0, 0): [
        {"text": "Passoire fine", "arrow": "down_then_right", "word": 0},
        {"text": "De la marine", "arrow": "right_then_down", "word": 1},
    ],
    (0, 2): [{"text": "Artiste muet", "arrow": "down", "word": 2}],
    (0, 3): [{"text": "Fatales à César", "arrow": "down", "word": 3}],
    (0, 4): [{"text": "Flaire", "arrow": "down", "word": 4}],
    (2, 0): [{"text": "Sans contenu", "arrow": "right", "word": 5}],
    (3, 0): [{"text": "Fin de prière", "arrow": "right", "word": 6}],
    (4, 0): [{"text": "Alourdit le ballon", "arrow": "right", "word": 7}],
}
FX_WORDS = [
    [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)],
    [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1)],
    [(1, 2), (2, 2), (3, 2), (4, 2)],
    [(1, 3), (2, 3), (3, 3), (4, 3)],
    [(1, 4), (2, 4), (3, 4), (4, 4)],
    [(2, 1), (2, 2), (2, 3), (2, 4)],
    [(3, 1), (3, 2), (3, 3), (3, 4)],
    [(4, 1), (4, 2), (4, 3), (4, 4)],
]
FX_CLUE_TEXT = [
    "Passoire fine",
    "De la marine",
    "Artiste muet",
    "Fatales à César",
    "Flaire",
    "Sans contenu",
    "Fin de prière",
    "Alourdit le ballon",
]
FX_DIR = ["→", "↓", "↓", "↓", "↓", "→", "→", "→"]
# letters in play (cell sheet's L); authors by join index:
# Ana 0, Bruno 1, Céline 2, Dédé 3
FX_L = {
    (0, 1): {"l": "N", "a": 0},
    (1, 0): {"l": "T", "a": 0},
    (1, 1): {"l": "A", "a": 0},
    (1, 2): {"l": "M", "a": 1, "locked": True},
    (1, 3): {"l": "I", "a": 1},
    (1, 4): {"l": "S", "a": 3},
    (2, 1): {"l": "V", "a": 0},
    (2, 3): {"l": "D", "a": 1, "pencil": True},
    (2, 4): {"l": "E", "a": 3},
    (3, 1): {"l": "A", "a": 1},
    (3, 2): {"l": "M", "a": 2},
    (3, 3): {"l": "O", "a": 0, "wrong": True},
    (3, 4): {"l": "N", "a": 3, "locked": True, "rev": True},
    (4, 1): {"l": "L", "a": 1},
    (4, 2): {"l": "E", "a": 2},
    (4, 3): {"l": "S", "a": 1},
}
FX_SOLVED = {
    (0, 1): "N",
    (1, 0): "T",
    (1, 1): "A",
    (1, 2): "M",
    (1, 3): "I",
    (1, 4): "S",
    (2, 1): "V",
    (2, 2): "I",
    (2, 3): "D",
    (2, 4): "E",
    (3, 1): "A",
    (3, 2): "M",
    (3, 3): "E",
    (3, 4): "N",
    (4, 1): "L",
    (4, 2): "E",
    (4, 3): "S",
    (4, 4): "T",
}
# other players: (player, cell, word)
FX_OTHERS = [(1, (4, 4), 7), (3, (4, 4), 4), (2, (3, 2), 2)]


def fx_rows(s: int, **o: object) -> list[list[dict]]:
    """Return the 5 x 5 phone grid at side s.

    Options: sel, word, letters, others, flagged, authors, access, caught,
    flash, reaction, solved, full, tint, blank_clues.
    """
    solved = o.get("solved", False)
    full = o.get("full", False)
    sel = o.get("sel", (2, 2))
    word = o.get("word", 5)
    others = o.get("others", FX_OTHERS)
    flagged = o.get("flagged", {4})
    letters = o.get("letters")
    amap = arrow_map(FX_CLUES, s, 5, 5)
    rows = []
    for r in range(5):
        row = []
        for c in range(5):
            k = (r, c)
            if k in FX_CLUES:
                lst = FX_CLUES[k]
                clues = [
                    {"text": q["text"], "flag": (q["word"] in flagged) and not solved}
                    for q in lst
                ]
                active = [
                    q["word"] == word and not solved and sel is not None for q in lst
                ]
                reaction = None
                if o.get("reaction") and o["reaction"][0] == k:
                    reaction = (o["reaction"][1], o["reaction"][2])
                row.append(
                    {
                        "type": "clue",
                        "clues": clues,
                        "active": active,
                        "reaction": reaction,
                        "blank": o.get("blank_clues"),
                    }
                )
                continue
            if letters is not None:
                d = letters.get(k, {})
            elif solved or full:
                d = {"l": FX_SOLVED[k], "a": (r + c) % 4}
                if full and k == (3, 3):
                    d = {"l": "O", "a": 0}
            else:
                d = FX_L.get(k, {})
            cell_o: dict = {
                "letter": d.get("l"),
                "cls": [],
                "cursors": [],
                "arrows": [] if o.get("blank_clues") else amap.get(k, []),
                "author": d.get("a"),
            }
            if not solved and sel is not None and k in FX_WORDS[word]:
                cell_o["cls"].append("word")
            if not solved and sel == k:
                cell_o["cls"].append("sel")
            for flag in ("locked", "pencil", "wrong", "rev"):
                if d.get(flag):
                    cell_o["cls"].append(flag)
            if d.get("rev") and "locked" not in cell_o["cls"]:
                cell_o["cls"].append("locked")
            if o.get("caught") and k in o["caught"]:
                cell_o["caught"] = True
            if o.get("flash") and o["flash"][0] == k:
                cell_o["flash"] = o["flash"][1]
            if not solved:
                cell_o["cursors"] = [p for (p, at, _w) in others if at == k]
                if o.get("tint", True):
                    for p, _at, w in sorted(others):
                        if k in FX_WORDS[w]:
                            cell_o["tint"] = p
                            break
            cell_o["authors"] = o.get("authors", False)
            cell_o["access"] = o.get("access", False)
            row.append(cell_o)
        rows.append(row)
    return rows


# ---------- 13 x 17 computer grid (cell sheet's BIG) ----------
BW, BH = 13, 17
BIG_INNER = [
    (4, 6),
    (6, 3),
    (7, 9),
    (9, 5),
    (11, 8),
    (12, 2),
    (13, 11),
    (15, 6),
    (3, 10),
    (10, 1),
]
BIG_CLUES_TXT = [
    "Astre du jour",
    "Petit cours d'eau",
    "Métal jaune",
    "Saison chaude",
    "Oiseau noir",
    "Fruit rouge",
    "Pronom",
    "Arbre fruitier",
    "Pièce d'échecs",
    "Mammifère marin",
    "Couleur vive",
    "Avant midi",
    "Instrument à cordes",
    "Partie du pied",
    "Boisson chaude",
    "Récipient",
    "Sans effet",
    "Vieille note",
    "Sur la portée",
    "Rivière",
    "Cri de joie",
    "Tissu léger",
    "Bien à soi",
    "Fin de journée",
]


def _big_layout() -> dict:
    cells: dict = {}
    n = [0]

    def clue(r: int, c: int, kinds: list[str]) -> None:
        lst = []
        for a in kinds:
            lst.append({"text": BIG_CLUES_TXT[n[0] % len(BIG_CLUES_TXT)], "arrow": a})
            n[0] += 1
        cells[(r, c)] = lst

    clue(0, 0, ["down_then_right", "right_then_down"])
    for c in range(2, BW, 2):
        clue(0, c, ["down", "right_then_down"] if c % 4 == 0 else ["down"])
    for r in range(2, BH, 2):
        clue(r, 0, ["right", "down_then_right"] if r % 4 == 2 else ["right"])
    for r, c in BIG_INNER:
        clue(r, c, ["right"])
    return cells


BIG = _big_layout()
FILL = "ESARINTULOMDPCGBVHFQ"


def big_rows(s: int, **o: object) -> list[list[dict]]:
    """Return the 13 x 17 computer grid, with its options applied."""
    solved = o.get("solved", False)
    authors = o.get("authors", False)
    amap = arrow_map(BIG, s, BW, BH)
    rows = []
    for r in range(BH):
        row = []
        for c in range(BW):
            k = (r, c)
            if k in BIG:
                clues = [
                    {"text": q["text"], "flag": k == (0, 6) and i == 0 and not solved}
                    for i, q in enumerate(BIG[k])
                ]
                row.append(
                    {
                        "type": "clue",
                        "clues": clues,
                        "active": [k == (4, 0) and not solved, False],
                    }
                )
                continue
            cell_o: dict = {"cls": [], "cursors": [], "arrows": amap.get(k, [])}
            if solved or (r * 5 + c * 11) % 7 < 4:
                cell_o["letter"] = FILL[(r * 7 + c * 3) % 20]
            if not solved and r == 4 and 1 <= c <= 5:
                cell_o["cls"].append("word")
            if not solved and k == (4, 3):
                cell_o["cls"].append("sel")
                cell_o["letter"] = None
            if not solved and k == (4, 4):
                cell_o["cls"].append("pencil")
                cell_o["letter"] = "R"
            if r == 1 and 1 <= c <= 4:
                cell_o["cls"].append("locked")
                cell_o["letter"] = cell_o.get("letter") or "E"
            if k == (10, 6):
                cell_o["cls"] += ["locked", "rev"]
                cell_o["letter"] = "O"
            if k == (6, 8) and not solved:
                cell_o["cls"].append("wrong")
                cell_o["letter"] = "U"
            if not solved:
                if r == 8 and c >= 1:
                    cell_o["tint"] = 1
                if r == 12 and c >= 3:
                    cell_o["tint"] = 3
                if k == (8, 7):
                    cell_o["cursors"] = [1]
                if k == (12, 6):
                    cell_o["cursors"] = [3]
                if k == (2, 9):
                    cell_o["cursors"] = [2]
            if cell_o.get("letter"):
                cell_o["author"] = (r + c) % 4
            cell_o["authors"] = authors
            row.append(cell_o)
        rows.append(row)
    return rows


def generic_thumb(w: int, h: int, px: int) -> str:
    """Return the catalogue's generic grid drawing (pages.md, « Catalogue »)."""
    c = px / h
    wpx = round(c * w)
    out = (
        f'<svg class="thumb" width="{wpx}" height="{px}" viewBox="0 '
        f'0 {w * 10} {h * 10}" aria-hidden="true">'
        f'<rect width="{w * 10}" height="{h * 10}" fill="var(--nock-white)"/>'
    )
    for x in range(0, w, 2):
        out += (
            f'<rect x="{x * 10}" y="0" width="10" '
            'height="10" fill="var(--nock-thumb)"/>'
        )
    for y in range(2, h, 2):
        out += (
            f'<rect x="0" y="{y * 10}" width="10" '
            'height="10" fill="var(--nock-thumb)"/>'
        )
    for gx in range(1, w):
        out += (
            f'<line x1="{gx * 10}" y1="0" x2="{gx * 10}" y2="{h * 10}" '
            'stroke="var(--nock-line)" stroke-width="1"/>'
        )
    for gy in range(1, h):
        out += (
            f'<line x1="0" y1="{gy * 10}" x2="{w * 10}" y2="{gy * 10}" '
            'stroke="var(--nock-line)" stroke-width="1"/>'
        )
    return out + "</svg>"


def floor(v: float) -> int:
    """Return the floor of a number as an int."""
    return math.floor(v)
