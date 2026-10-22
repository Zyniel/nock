"""Build docs/design/screens-sheet.html, the screens sheet of the visual design.

Run `uv run python docs/design/screens_sheet/build.py` after any change of look
(specs/_design.md section 1, rule 3). The page is static: no script, and the
width switch is CSS. Never edit the HTML by hand.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from string import Template

from cells import FLAG_ICO, esc, fx_rows, generic_thumb, grid, picon
from chrome import (
    account_in,
    account_out,
    aide_menu,
    band_done,
    cluebar,
    compose,
    dbtn,
    desk_dialog,
    desk_page,
    desk_pop,
    desk_room,
    host_settings,
    keyboard,
    low_column_room,
    note,
    note_under_vote,
    phone_dialog_sheet,
    phone_page,
    phone_pop,
    phone_room,
    phone_top,
    picker,
    recap_body,
    room_menu,
    salon_sheet,
    stream,
    vote_banner,
)
from style import CSS, font_faces

HERE = Path(__file__).resolve().parent
SHEET = HERE.parent / "screens-sheet.html"

# ---------------------------------------------------------------- helpers


def marks(ms: list[str]) -> str:
    """Return the labels of a screen: citations, decisions, pending."""
    out = ""
    for m in ms:
        if m.startswith("pending"):
            out += f'<span class="prop">{m}</span>'
        elif m.startswith("decided spec"):
            out += f'<a class="dec" href="#p-pending">{m}</a>'
        elif m == "spec 043 approved":
            out += f'<a class="dec" href="#d-043">{m}</a>'
        elif m[0] in "PD" and m[1:].isdigit():
            out += f'<a class="dec" href="#d-{m}">Decided {m}</a>'
        else:
            out += f'<span class="dec">{m}</span>'
    return out


def screen(
    sid: str,
    title: str,
    ms: list[str],
    caps: list[str],
    frames: list[tuple[str, str, str]],
) -> str:
    """frames: (kind 'ph' or 'pc', label, html)."""
    figs = ""
    for kind, label, body in frames:
        if kind == "pc":
            body = f'<div class="deskwrap">{body}</div>'
        figs += (
            f'<figure class="{kind}">{body}<figcaption>{label}</figcaption></figure>'
        )
    cap = "".join(f'<p class="cap">{c}</p>' for c in caps)
    return (
        f'<article class="scr" id="{sid}"><h3>{title} {marks(ms)}</h3>{cap}<div '
        f'class="pair">{figs}</div></article>'
    )


def part(pid: str, num: str, title: str, lead: str, body: str) -> str:
    """Return one part of the sheet."""
    return (
        f'<section class="part" id="{pid}"><h2 class="ph2"><small>{num}</small>{title}'
        "</h2>"
        f'<p class="lead">{lead}</p>{body}</section>'
    )


def box(inner: str, cap: str) -> str:
    """Return a small specimen with its caption."""
    return f'<div class="box">{inner}<span class="cap">{cap}</span></div>'


PH = "Phone · 360 &times; 720"
PC = "Computer · 1280 &times; 800"

# ---------------------------------------------------------------- catalogue

NOTCH_ON = (
    '<svg viewBox="0 0 10 14" aria-hidden="true"><polygon points="0,0 '
    '10,0 10,14 5,10 0,14" fill="var(--nock-navy)"/></svg>'
)
NOTCH_OFF = (
    '<svg viewBox="0 0 10 14" aria-hidden="true"><polygon points="0,0 '
    '10,0 10,14 5,10 0,14" fill="var(--nock-thumb)"/></svg>'
)
ITEMS = [
    (12, "16 octobre 2026", 3, "started", 13, 17, 54),
    (11, "15 octobre 2026", 2, "", 13, 17, 52),
    (10, "14 octobre 2026", 4, "done", 13, 17, 55),
    (9, "13 octobre 2026", 1, "done", 9, 12, 28),
    (8, "12 octobre 2026", 3, "", 13, 17, 53),
    (7, "11 octobre 2026", 2, "started", 11, 15, 41),
]


def cat_card(it: tuple, phone: bool, failed: bool = False) -> str:
    """Return one catalogue card."""
    num, date, force, st, w, h, words = it
    notches = "".join(NOTCH_ON if i <= force else NOTCH_OFF for i in range(1, 5))
    pill = {
        "started": '<span class="status-pill started">Commencée</span>',
        "done": '<span class="status-pill done">Terminée</span>',
    }.get(st, "")
    thumb = "" if phone else generic_thumb(w, h, 51)
    err = (
        '<span class="errtxt">Impossible de lancer la partie. Réessayez.</span>'
        if failed
        else ""
    )
    return (
        f'<div class="citem">{thumb}<div class="cinfo"><div class="cnum">Grille '
        f"n° {num}{pill}</div>"
        f'<div class="cmeta">Publiée le {date}</div>'
        f'<div class="cmeta"><span class="notches">{notches}</span>Force '
        f"{force} · {w} &times; {h} · {words} mots</div>{err}</div>"
        '<span class="btn primary">Jouer</span></div>'
    )


def filters(sel: str = "Toutes") -> str:
    """Return the force filter chips."""
    out = '<div class="filters"><span class="lab">Force</span>'
    for f in ["Toutes", "Force 1", "Force 2", "Force 3", "Force 4"]:
        out += (
            f'<span class="fbtn" aria-pressed="{"true" if f == sel else "false"}'
            f'">{f}</spa'
            "n>"
        )
    return out + "</div>"


MINE = (
    '<h2 class="sec-h">Mes salons</h2><div class="rlist">'
    '<div class="ritem"><div class="grow"><span class="t">Grille '
    'n° 12 · 13 &times; 17</span><span class="m">Joueurs : Ana, '
    "Bruno, Céline, Dédé</span>"
    '<span class="m">Dernière activité : 22 octobre 2026 à 21:14</span></div><spa'
    'n class="btn primary">Reprendre</span></div>'
    '<div class="ritem"><div class="grow"><span class="t">Grille '
    'n° 10 · 13 &times; 17 <span class="status-pill done">Terminée</span></span>'
    '<span class="m">Joueurs : Ana, Éloïse</span><span class="m">Dernière '
    "activité : 14 octobre 2026 à 18:02</span></div>"
    '<span class="btn secondary">Reprendre</span></div></div>'
)
HIST = (
    '<h2 class="sec-h">Grilles terminées</h2><div class="rlist">'
    '<div class="ritem"><div class="grow"><span class="t">Grille '
    "n° 10 · 13 &times; 17</span>"
    '<span class="m">Terminée le 14 octobre 2026 · en 34 min '
    '12 s · Avec Éloïse</span></div><span class="btn secondary">Rejouer</span></d'
    "iv>"
    '<div class="ritem"><div class="grow"><span class="t">Grille '
    "n° 9 · 9 &times; 12</span>"
    '<span class="m">Terminée le 13 octobre 2026 · en 1 h 02 '
    'min 40 s · En solo</span></div><span class="btn secondary">Rejouer</span></d'
    "iv></div>"
)


def catalogue(
    phone: bool, n_items: int = 6, state: str = "ready", failed_first: bool = False
) -> str:
    """Return the catalogue page in one of its states."""
    body = '<h1 class="cat-h">Grilles</h1>'
    if state == "loading":
        body += '<p class="loadline" style="margin:0">Chargement…</p>'
    elif state == "error":
        body += (
            '<p class="errtxt" style="margin:0">Impossible de charger les grilles.</p>'
        )
    elif state == "empty":
        body += '<p class="loadline" style="margin:0">Aucune grille pour le moment.</p>'
    elif state == "filtered":
        body += (
            filters("Force 4")
            + '<p class="loadline" style="margin:0">Aucune grille de cette force.</p>'
        )
    else:
        body += MINE + filters()
        cards = "".join(
            cat_card(it, phone, failed_first and i == 0)
            for i, it in enumerate(ITEMS[:n_items])
        )
        body += f'<div class="clist">{cards}</div>' + HIST
    main = f'<main class="cat-main">{body}</main>'
    if phone:
        right = '<span class="dbtn small">Compte</span>'
        return (
            f'<div class="phone" style="height:auto">'
            f'<div class="dtop">{_brand()}<span '
            f'class="gname"></span>{right}</div>{main}</'
            "div>"
        )
    return (
        '<div class="desk" style="height:auto;min-height:800px"><div '
        f'class="dtop">{_brand()}<span class="gname"></span>{dbtn(None, "Compte")}</di'
        f"v>{main}</div>"
    )


def _brand() -> str:
    from chrome import brand

    return brand()


def cat_with_sheet(phone: bool, inner: str) -> str:
    """Return the catalogue with the account sheet or dialog open."""
    body = (
        f'<main class="cat-main"><h1 class="cat-h">Grilles</h1>{MINE}{filters()}<div '
        f'class="clist">{"".join(cat_card(it, phone) for it in ITEMS[:4])}</div></main'
        ">"
    )
    if phone:
        return (
            f'<div class="phone"><div class="dtop">{_brand()}<span '
            'class="gname"></span><s'
            'pan class="dbtn small" aria-pressed="true">Compte</span></div>'
            f'{body}<div class="ov bottom" style="top:56px;backgroun'
            'd:var(--nock-scrim)"><'
            f'div class="dialog">{inner}</div></div></div>'
        )
    return (
        f'<div class="desk"><div class="dtop">{_brand()}<span '
        f'class="gname"></span>{dbtn(None, "Compte", True)}'
        "</div>"
        f"{body}{desk_dialog(inner)}</div>"
    )


def sec_catalogue() -> str:
    """Return part 1, the catalogue."""
    s = screen(
        "s-cat",
        "Catalogue: « Mes salons », the grids, « Grilles terminées »",
        ["§10", "specs 004, 029, 032, 033"],
        [
            "The home page <code>/</code>. Drawn unrolled: the page scrolls "
            "as a whole. « Mes salons » appears only when the device "
            "or the account has open rooms; « Grilles terminées » only "
            "when the history holds finished grids. "
            "The generic grid drawing shows on wide windows only (two "
            "cards per row); a phone has one card per row and no drawing "
            "(decided 2026-10-17).",
            (
                '<span class="m">« Jouer » opens a room of one at once (spec '
                "010); « Reprendre » is secondary once the room is solved; "
                "« Rejouer » starts the same grid in a new room. Nothing "
                "else is on this page: no credits (decision D2).</span>"
            ),
        ],
        [
            ("ph", PH + " (unrolled)", catalogue(True)),
            ("pc", PC + " (unrolled)", catalogue(False)),
        ],
    )
    states = (
        '<div class="mini">'
        + box(
            f'<div style="width:330px">{_cat_strip("loading")}</div>',
            "Loading: one muted line under the heading, no spinner, no skeleton.",
        )
        + box(
            f'<div style="width:330px">{_cat_strip("error")}</div>',
            "Error: the same place, red error line.",
        )
        + box(
            f'<div style="width:330px">{_cat_strip("empty")}</div>',
            "No grid at all: muted line; the chips are not shown.",
        )
        + box(
            f'<div style="width:330px">{_cat_strip("filtered")}</div>',
            "No grid of this force: the chips stay, a muted line replaces the cards.",
        )
        + box(
            f'<div style="width:400px">{cat_card(ITEMS[1], True, True)}</div>',
            (
                "« Jouer » failed: red line inside the card that was pressed; "
                "the button stays usable."
            ),
        )
        + box(
            (
                '<div style="width:330px"><h2 class="sec-h" style="margin:0">Mes '
                'salons</h2><p class="errtxt" style="margin:6px 0 0">Impossible '
                "de charger vos salons.</p></div>"
            ),
            (
                "« Mes salons » could not load: heading and red line; while "
                "loading, nothing (the section appears when ready); with "
                "no room, no section."
            ),
        )
        + "</div>"
    )
    s2 = (
        (
            '<article class="scr" id="s-cat-states"><h3>Catalogue: loading, '
            "empty and error "
        )
        + marks(["P4"])
        + (
            '</h3><p class="cap">Strings are fr.json\'s (<code>catalogue.*</code>, '
            "<code>my_rooms.*</code>). The rule for every page of Nock: "
            "a state is one line of text where the content will be; muted "
            "while waiting or empty, red when something failed.</p>"
        )
        + states
        + "</article>"
    )
    extra = specs_cat()
    return part(
        "p-cat",
        "1 · Catalogue",
        "The list of grids",
        (
            "The page players open first. A computer gets the 920 px "
            "column; a phone the same content in one column."
        ),
        s + s2 + extra,
    )


def _cat_strip(state: str) -> str:
    inner = '<h1 class="cat-h" style="font-size:1.4rem">Grilles</h1>'
    if state == "loading":
        inner += '<p class="loadline" style="margin:0">Chargement…</p>'
    elif state == "error":
        inner += (
            '<p class="errtxt" style="margin:0">Impossible de charger les grilles.</p>'
        )
    elif state == "empty":
        inner += (
            '<p class="loadline" style="margin:0">Aucune grille pour le moment.</p>'
        )
    else:
        inner += (
            filters("Force 4")
            + '<p class="loadline" style="margin:0">Aucune grille de cette force.</p>'
        )
    return f'<div style="display:grid;gap:12px">{inner}</div>'


# ---------------------------------------------------------------- entry pages


def entry_card(
    title: str,
    line: str = "",
    button: str = "secondary",
    code: bool = True,
    extra: str = "",
) -> str:
    """Return an entry status card with its room code line."""
    c = '<div class="codeline">Salon K7QM2X</div>' if code else ""
    ln = f'<p class="muted">{line}</p>' if line else ""
    return (
        f'{c}<div class="card"><h1>{title}</h1>{ln}{extra}<span class="btn '
        f'{button}">Voir les grilles</span></div>'
    )


NICK = (
    '<div class="codeline">Salon K7QM2X</div><div class="card"><h1>Choisissez '
    "un pseudo</h1>"
    '<div class="field">Pseudo<span class="input err caps">A</span></div>'
    '<span class="errtxt" style="margin-top:-6px">Le pseudo doit '
    "faire de 2 à 20 caractères.</span>"
    '<span class="btn primary">Entrer dans le salon</span></div>'
)
NICK_OK = (
    '<div class="codeline">Salon K7QM2X</div><div class="card"><h1>Choisissez '
    "un pseudo</h1>"
    '<div class="field">Pseudo<span class="input caps">Bruno</span></div>'
    '<span class="btn primary">Entrer dans le salon</span></div>'
)


def sec_entry() -> str:
    """Return part 2, the entry pages."""
    a = screen(
        "s-nick",
        "Nickname form",
        ["§8 Entry pages", "spec 012", "P1"],
        [
            (
                "Shown on <code>/r/K7QM2X</code> to a player the room does "
                "not know yet. The input shows capitals as typed (spec 012); "
                "the error replaces nothing, it sits under the field with "
                "the red border."
            ),
            (
                '<span class="m">On a computer, the phone\'s column is centred, '
                "420 px wide, 48 px under the top bar: _design.md draws these "
                "pages on a phone only.</span>"
            ),
        ],
        [("ph", PH + " · error", phone_page(NICK)), ("pc", PC, desk_page(NICK_OK))],
    )
    statuses = [
        ("Ce salon est complet (8 joueurs).", ""),
        ("Ce salon est verrouillé.", ""),
        ("Vous avez été retiré de ce salon.", ""),
        ("Ce salon est ouvert dans un autre onglet.", ""),
        ("Trop de codes erronés. Réessayez dans une minute.", ""),
    ]
    mini = '<div class="mini">'
    for t, ln in statuses:
        mini += box(
            (
                '<div style="width:330px;display:grid;gap:14px;backgrou'
                "nd:var(--nock-page);pa"
                f'dding:16px;border-radius:6px">{entry_card(t, ln)}</div>'
            ),
            "Same card, status text as its title.",
        )
    mini += "</div>"
    b = (
        screen(
            "s-status",
            "A room that refuses entry",
            ["§8 Entry pages", "specs 011, 012, 040"],
            [
                (
                    "Every refusal uses one card: the status text as its title "
                    "and « Voir les grilles » (secondary). The room code line "
                    "stays above it. The full room is drawn large; the others "
                    "below."
                ),
            ],
            [
                (
                    "ph",
                    PH + " · full",
                    phone_page(entry_card("Ce salon est complet (8 joueurs).")),
                ),
                (
                    "pc",
                    PC + " · locked",
                    desk_page(entry_card("Ce salon est verrouillé.")),
                ),
            ],
        )
        + mini
    )
    gone = entry_card(
        "Ce salon n'existe pas.",
        "Un salon est effacé 30 jours après sa dernière modification.",
        button="primary",
    )
    c = screen(
        "s-gone",
        "A room that is not found or has expired",
        ["spec 032", "P3"],
        [
            (
                "An expired room is deleted (spec 032) and reads as not found, "
                "so both share one card. Decided: one muted line explaining "
                "expiry (a new string), and « Voir les grilles » primary "
                "since it is the only way on."
            ),
        ],
        [("ph", PH, phone_page(gone)), ("pc", PC, desk_page(gone))],
    )
    nf = (
        '<div class="card"><h1>Page introuvable</h1><span class="btn '
        'primary">Voir les grilles</span></div>'
    )
    d = screen(
        "s-404",
        "Page not found",
        ["§8 Entry pages", "spec 040"],
        [
            (
                "Any other path. No room code line. « Voir les grilles » "
                "is the addition _design.md already decided."
            )
        ],
        [("ph", PH, phone_page(nf)), ("pc", PC, desk_page(nf))],
    )
    extra = specs_entry()
    return part(
        "p-entry",
        "2 · Entry pages",
        "Before the room",
        (
            "Pages shown instead of the room, on the page grey behind "
            "one white card (§8 « Entry and not-found pages »)."
        ),
        a + b + c + d + extra,
    )


# ---------------------------------------------------------------- room

NOTE_MSG = "Bruno : AMEN, je pense 👍"
NOTE_LONG = (
    "Céline : Je crois que le mot du bas à droite est faux, on le reprend ensemble ?"
)


def sec_room() -> str:
    """Return part 3, the room."""
    out = ""
    out += screen(
        "s-room",
        "The room in play",
        ["§8", "§6 cells"],
        [
            "Phone: top bar (timer, Annuler, Aide, Salon with its unread "
            "badge, Clavier pressed, Menu), the grid as large as fits, "
            "the clue bar, the keyboard. A 3-second note from Bruno sits "
            "over the top of the grid. "
            "Computer: the brand and the grid name, the timer, the buttons "
            "with their labels; the Salon side column open by default, "
            "on Discussion.",
            (
                '<span class="m">On the grid: my word in word blue and my '
                "cell selected, Bruno (Vert) and Dédé (Violet) on the same "
                "cell, Céline (Sarcelle) with her word tinted, a locked M, "
                "a pencil D, a wrong O struck in red, a revealed N with its "
                "notch, Dédé's flag on « Flaire ».</span>"
            ),
        ],
        [
            ("ph", PH, phone_room(stage_extra=note(esc(NOTE_MSG)))),
            ("pc", PC, desk_room()),
        ],
    )
    out += screen(
        "s-salon",
        "Salon: Discussion",
        ["§8 Salon", "spec 022", "spec 013"],
        [
            (
                "Phone: a bottom sheet over a scrim, 62 % of the height, "
                "with its handle; « Salon » pressed. Progress, the two tabs, "
                "one stream oldest first (messages with a player dot, events "
                "as muted lines with their pictogram: → joined, the flag, "
                "▲ reveal in orange-red, ✓ check in green when nothing was "
                "wrong), then the message box."
            ),
            (
                '<span class="m">Computer: the same content is the side column '
                "(drawn in the room above). Here, the column with Bruno typing "
                "a message, and the phone with the chat paced (« Patientez "
                "avant d'envoyer. », P5).</span>"
            ),
        ],
        [
            (
                "ph",
                PH,
                phone_room(pressed={"salon", "kbd"}, badge=None, layer=salon_sheet()),
            ),
            (
                "ph",
                PH + " · paced",
                phone_room(
                    pressed={"salon", "kbd"},
                    badge=None,
                    layer=salon_sheet(wait=True, typed="ENCORE ?"),
                ),
            ),
            ("pc", PC, desk_room(col_kw={"typed": "Le bas est presque fini"})),
        ],
    )
    out += screen(
        "s-players",
        "Salon: Joueurs, invitation, host's moderation",
        ["§8 Salon", "specs 011, 013, 014", "P5", "spec 043 approved"],
        [
            (
                "Each row: dot, name (mine bold with « (vous) »), the « hôte "
                "» tag; under it the state and the player's current "
                "clue; « inactif » italic, « déconnecté » italic and struck. "
                "Then « Lien d'invitation », the URL box, « Copier le lien "
                "» and, after a copy, the green « Lien copié ». « Inviter "
                "» in the Menu opens this tab."
            ),
            (
                "Host only: « Retirer » and « Couper » / « Rétablir » (spec "
                "022's chat mute, until now a separate « Sourdine » block "
                "in the chat panel) as small secondary buttons (P5). A muted "
                "player sees the message box disabled and « L'hôte a coupé "
                "votre discussion. »"
            ),
            (
                '<span class="m">The row on two lines (state and clue under '
                "the name, buttons on the right) is spec 043's, decided by "
                "the human's approval of spec 043 on 2026-10-22; the sheet's "
                "P5 had the buttons on a second line (_design.md §15 « Where "
                "the screens sheet met spec 043 »).</span>"
            ),
        ],
        [
            (
                "ph",
                PH + " · host",
                phone_room(
                    pressed={"salon", "kbd"},
                    badge=None,
                    layer=salon_sheet(tab="players", muted_bruno=True),
                ),
            ),
            (
                "ph",
                PH + " · muted player",
                phone_room(
                    pressed={"salon", "kbd"}, badge=None, layer=salon_sheet(muted=True)
                ),
            ),
            ("pc", PC + " · host", desk_room(column="players")),
        ],
    )
    out += screen(
        "s-aide",
        "Aide (help menu)",
        ["§8 Aide menu", "specs 020, 023, 024", "P7"],
        [
            (
                "A popover under « Aide ». The pencil confirm heads the menu "
                "only while my cell holds a pencil letter. « Vérifier » then "
                "« Révéler » with the budget left as the detail."
            ),
            (
                "An item whose budget is spent stays in place, muted, with "
                "« Plus de lettre » / « Plus de mot » as the detail and does "
                "nothing (P7). In « par vote » mode the items are the same "
                "and start a vote; in « désactivée » mode the menu holds "
                "the pencil confirm or one muted line (section 4)."
            ),
        ],
        [
            (
                "ph",
                PH + " · pencil letter selected",
                phone_room(
                    pressed={"aide", "kbd"},
                    grid_opts={"sel": (2, 3)},
                    layer=phone_pop(aide_menu(pencil=True), left=60),
                ),
            ),
            (
                "pc",
                PC + " · reveal budget spent",
                desk_room(
                    pressed={"salon", "aide"},
                    layer=desk_pop(aide_menu(letters=0, words=1), left=980),
                ),
            ),
        ],
    )
    out += screen(
        "s-menu",
        "Menu",
        ["§8 Menu", "specs 019, 027, 033"],
        [
            (
                "Anchored to the right. The three switches with their state "
                "as the detail (« Auteurs », « Mots des autres », « Accessibilité "
                "»), « Inviter », « Réglages de l'hôte » for the host only, "
                "« Compte », a separator, « Masquer le chrono » and « Retour "
                "aux grilles ». The hovered item takes word blue."
            ),
            (
                '<span class="m">« Compte » after « Réglages de l\'hôte '
                "» : the lead's decision of 2026-10-22 (_design.md §15).</span>"
            ),
        ],
        [
            (
                "ph",
                PH + " · host",
                phone_room(
                    pressed={"menu", "kbd"},
                    layer=phone_pop(room_menu(hover="Inviter"), right=6),
                ),
            ),
            (
                "pc",
                PC + " · guest",
                desk_room(
                    pressed={"salon", "menu"},
                    layer=desk_pop(room_menu(host=False, authors=True), right=16),
                ),
            ),
        ],
    )
    out += screen(
        "s-host",
        "Host settings",
        ["§8 Room sheets", "spec 014"],
        [
            (
                "Menu « Réglages de l'hôte ». Phone: a sheet from under the "
                "top bar (radius 16 px, no handle). Computer: the 440 px "
                "dialog. A switch for the lock, a three-way segmented control "
                "for help, two number fields, « Enregistrer »."
            ),
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    pressed={"menu", "kbd"}, layer=phone_dialog_sheet(host_settings())
                ),
            ),
            (
                "pc",
                PC,
                desk_room(
                    pressed={"salon", "menu"},
                    layer=desk_dialog(host_settings("par vote")),
                ),
            ),
        ],
    )
    out += screen(
        "s-react",
        "Reactions and 3-second notes",
        ["§8 Reactions", "§8 3-second notes", "spec 022"],
        [
            (
                "« Réagir » in the clue bar opens the picker above the clue "
                "bar; a shown reaction is a white pill over its clue for "
                "3 s (on a two-clue cell, over its own half: decided 2026-10-22). "
                "Notes: one line on ink, over the top of the grid, 3 s, never "
                "while the stream is visible. A long note ends with an ellipsis "
                "on its one line, never wider than the grid's viewport (spec 043 "
                "WP-2, 2026-10-22). A tap on a note opens the Salon on "
                "Discussion, the focus in the message box."
            ),
        ],
        [
            (
                "ph",
                PH + " · picker open",
                phone_room(
                    grid_opts={"reaction": ((0, 2), 0, "🤔")}, stage_extra=picker()
                ),
            ),
            (
                "ph",
                PH + " · notes",
                phone_room(
                    grid_opts={"reaction": ((0, 0), 1, "👏")},
                    stage_extra=note(f"{FLAG_ICO} Dédé bloque sur « Flaire »"),
                ),
            ),
            (
                "ph",
                PH + " · long note",
                phone_room(stage_extra=note(esc(NOTE_LONG))),
            ),
            (
                "pc",
                PC + " · column closed",
                desk_room(
                    column=None,
                    badge="2",
                    main_extra=note("Céline : Je prends le bas à gauche."),
                ),
            ),
        ],
    )
    out += screen(
        "s-timer",
        "Timer hidden, new events",
        ["§8 top bar", "spec 027"],
        [
            (
                "« Masquer le chrono » puts « Chrono » in the timer's slot; "
                "a press shows the timer again. With the Salon closed, new "
                "events with no unread message light the 8 px red dot on "
                "« Salon » (on a computer at the badge's place, decided 2026-10-22)."
            ),
        ],
        [
            ("ph", PH, phone_room(timer=None, badge=None, newdot=True)),
            (
                "pc",
                PC + " · column closed",
                desk_room(column=None, timer=None, newdot=True),
            ),
        ],
    )
    out += screen(
        "s-net",
        "Connection lost",
        ["§8 Connection lost", "spec 017"],
        [
            (
                "A band under the top bar pushes the grid down; the grid "
                "stays usable and letters wait to be sent. It goes when the "
                "room is back."
            )
        ],
        [("ph", PH, phone_room(net=True)), ("pc", PC, desk_room(net=True))],
    )
    out += screen(
        "s-final",
        "A final status after the room showed",
        ["§8 Connection lost", "spec 043", "specs 014, 040"],
        [
            (
                "Removed by the host, opened in another tab, or the connection "
                "closed for good, once the room has shown: the status text in a "
                "band under the top bar, the connection band's look without its "
                "red dot. The room stays drawn under it. A refusal before the "
                "room showed is the card of section 2 instead."
            ),
        ],
        [
            (
                "ph",
                PH + " · removed",
                phone_room(final_status="Vous avez été retiré de ce salon."),
            ),
            (
                "pc",
                PC + " · another tab",
                desk_room(final_status="Ce salon est ouvert dans un autre onglet."),
            ),
        ],
    )
    out += focus_rings()
    catch_items = [
        ("evt", "Ana a rejoint le salon", ""),
        ("evt", "✓ Bruno a vérifié la grille", ""),
        ("evt", "▲ Dédé a révélé un mot", "rev"),
        ("msg", 2, "On a bien avancé cette nuit !"),
        (
            "evt",
            (
                "Céline a modifié les réglages : aide par vote, 4 lettres "
                "et 1 mots à révéler"
            ),
            "",
        ),
    ]
    catch_items[0] = ("evt", "→ Ana a rejoint le salon", "")
    out += screen(
        "s-catch",
        "Catch-up after being away",
        ["§6 catch-up ring", "§8 stream", "spec 034"],
        [
            (
                "Cells changed while I was away get a 3 px ink ring for 5 "
                "s; the matching lines are in the stream, with the same look "
                "as live lines."
            ),
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    grid_opts={"caught": [(1, 3), (2, 4), (3, 4), (4, 2)]},
                    stage_extra=note("Céline : On a bien avancé cette nuit !"),
                ),
            ),
            ("pc", PC, desk_room(col_kw={"items": catch_items})),
        ],
    )
    loading_ph = phone_room(
        timer="",
        badge=None,
        kbd=None,
        pressed=set(),
        stage_html='<p class="loadline">Entrée dans le salon…</p>',
        clue=None,
    )
    loading_pc = desk_room_loading()
    out += screen(
        "s-loading",
        "Opening the room",
        ["P2"],
        [
            (
                "Decided: while the room connects or joins (« Connexion… "
                "», « Entrée dans le salon… », the <code>room-status</code> "
                "strings), the top bar is in place, the grid area holds one "
                "muted line, no clue bar and no keyboard yet. No spinner, "
                "no skeleton grid. A refusal then becomes the card of section "
                "2."
            ),
        ],
        [("ph", PH, loading_ph), ("pc", PC, loading_pc)],
    )
    extra = specs_room()
    return part(
        "p-room",
        "3 · The room",
        "Top bar, grid, clue bar, Salon, menus",
        (
            "The core of the game. Nothing but the grid and its bars "
            "is permanently on screen; the rest opens on demand (§8)."
        ),
        out + extra,
    )


def focus_rings() -> str:
    """Return the focus rings drawn inside a container (_design.md section 11)."""
    items = (
        '<div class="pop static"><span class="mi">Auteurs <em>désactivé</em></span>'
        '<span class="mi ring-in">Mots des autres <em>teintés</em></span>'
        '<span class="mi">Accessibilité <em>désactivée</em></span></div>'
    )
    tabs = (
        '<div style="width:330px"><div class="tabs"><span aria-selected="true" '
        'class="ring-in">Discussion</span><span aria-selected="false">Joueurs '
        "(4)</span></div></div>"
    )
    lines = [
        ("evt", "→ Bruno a rejoint le salon", ""),
        ("msg", 1, "AMEN, je pense 👍"),
        ("evt", "✓ Ana a vérifié le mot", "ok"),
    ]
    listed = stream(items=lines).replace('class="stream"', 'class="stream ring-in"', 1)
    stream_box = f'<div style="width:330px;display:grid">{listed}</div>'
    seg_on = (
        '<span class="seg"><span class="on ring-in4">libre</span><span>par '
        "vote</span><span>désactivée</span></span>"
    )
    seg_off = (
        '<span class="seg"><span class="on">libre</span><span class="ring-in4">par '
        "vote</span><span>désactivée</span></span>"
    )
    boxes = (
        box(items, "A popover's item: navy ring inside, -2 px; the popover scrolls.")
        + box(tabs, "The Salon's tab: navy ring inside, -2 px.")
        + box(stream_box, "The stream list, a Tab stop while it scrolls: -2 px.")
        + box(
            seg_on + seg_off,
            "Segmented control: -4 px, white on the chosen (navy) option, navy on "
            "another.",
        )
    )
    return (
        '<article class="scr" id="s-rings"><h3>Focus rings drawn inside '
        + marks(["§11 Focus ring", "spec 043", "spec 035 AC-2"])
        + '</h3><p class="cap">The ring is 2 px navy, 2 px outside the control '
        "(§11), except where a container that scrolls or clips would cut it: "
        "there it is drawn inside. On the navy clue bar it is white at -4 px "
        "(drawn with the clue bar).</p>"
        f'<div class="mini">{boxes}</div></article>'
    )


def desk_room_loading() -> str:
    """Return the computer room while it opens."""
    from chrome import desk_top

    return (
        f'<div class="desk">{desk_top(timer="", pressed=set(), gname="")}'
        '<div class="dbody"><div class="dmain"><p class="loadline">Connexion…</p></di'
        "v></div></div>"
    )


# ---------------------------------------------------------------- help

CHECK_L = {
    (0, 1): {"l": "N", "a": 0},
    (1, 0): {"l": "T", "a": 0},
    (1, 1): {"l": "A", "a": 0},
    (1, 2): {"l": "M", "a": 1, "locked": True},
    (1, 3): {"l": "I", "a": 1},
    (1, 4): {"l": "S", "a": 3},
    (2, 1): {"l": "V", "a": 0},
    (2, 3): {"l": "D", "a": 1, "pencil": True},
    (2, 4): {"l": "E", "a": 3},
    (3, 1): {"l": "A", "a": 1, "locked": True},
    (3, 2): {"l": "M", "a": 2, "locked": True},
    (3, 3): {"l": "O", "a": 0, "wrong": True},
    (3, 4): {"l": "N", "a": 3, "locked": True, "rev": True},
    (4, 1): {"l": "L", "a": 1},
    (4, 2): {"l": "E", "a": 2},
    (4, 3): {"l": "S", "a": 1},
}


def sec_help() -> str:
    """Return part 4, help."""
    out = ""
    check_items = [
        ("evt", "→ Bruno a rejoint le salon", ""),
        ("msg", 1, "On vérifie « Fin de prière » ?"),
        ("evt", "Ana a vérifié le mot", ""),
        ("evt", "✓ Bruno a vérifié la grille", "ok"),
    ]
    out += screen(
        "s-check",
        "Check",
        ["§6 letter marks", "§8 stream", "spec 023"],
        [
            (
                "Aide &rsaquo; Vérifier &rsaquo; Le mot on « Fin de prière "
                "»: the right letters lock (bold on locked grey), the wrong "
                "O is struck in red. The stream says who checked; the line "
                "is green only when the check found nothing wrong. Others "
                "get a 3-second note."
            ),
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    grid_opts={"word": 6, "sel": (3, 3), "letters": CHECK_L},
                    stage_extra=note("✓ Bruno a vérifié la grille"),
                ),
            ),
            ("pc", PC, desk_room(col_kw={"items": check_items})),
        ],
    )
    rev_items = [
        ("msg", 3, "Je sèche sur « Flaire »."),
        ("evt", FLAG_ICO + " Dédé bloque sur « Flaire »", ""),
        ("evt", "▲ Dédé a révélé une lettre", "rev"),
        ("evt", "▲ Ana a révélé un mot", "rev"),
    ]
    out += screen(
        "s-reveal",
        "Reveal",
        ["§6 revealed notch", "§8 stream", "spec 024"],
        [
            (
                "A revealed letter is locked (bold, grey) with the orange-red "
                "notch at the bottom centre; the stream line is orange-red "
                "with ▲. The budget left shows in the Aide menu (section "
                "3)."
            ),
        ],
        [
            ("ph", PH, phone_room(stage_extra=note("▲ Dédé a révélé une lettre"))),
            ("pc", PC, desk_room(col_kw={"items": rev_items})),
        ],
    )
    out += screen(
        "s-vote",
        "Help by vote",
        ["§9 Vote", "spec 025", "P6"],
        [
            (
                "A banner over the top of the grid area, with « Oui » / « "
                "Non », the seconds left and a draining bar. No layout shift; "
                "notes wait until it goes."
            ),
            (
                "Decided: once I have voted, the two buttons give way to "
                "a muted « Vote enregistré. En attente des autres joueurs… "
                "»; the player who asked sees only « En attente des autres "
                "joueurs… ». The result (« Vote accepté. », « Vote refusé. "
                "», « Temps écoulé, vote annulé. ») comes as a 3-second note "
                "when the banner goes."
            ),
            (
                "« Rien à annuler. » does not wait: during a vote it sits 8 px "
                "under the banner's bottom edge, same look, layer 6, so the "
                "banner never covers it (spec 043 Decision 25, the lead, "
                "2026-10-22)."
            ),
        ],
        [
            ("ph", PH + " · asked", phone_room(stage_extra=vote_banner())),
            (
                "ph",
                PH + " · voted",
                phone_room(stage_extra=vote_banner("cast", secs="11 s", pct=55)),
            ),
            (
                "ph",
                PH + " · undo during the vote",
                phone_room(
                    stage_extra=note_under_vote(
                        vote_banner("cast", secs="9 s", pct=45), "Rien à annuler."
                    )
                ),
            ),
            (
                "pc",
                PC + " · I asked",
                desk_room(
                    main_extra=vote_banner(
                        "wait", "Ana propose de vérifier la grille.", "16 s", 80
                    )
                ),
            ),
        ],
    )
    out += screen(
        "s-nohelp",
        "Help switched off",
        ["spec 025", "spec 043 approved"],
        [
            (
                "Host setting « Aide : désactivée ». « Aide » stays in the "
                "top bar; its menu holds the pencil confirm when it applies, "
                "otherwise one muted line « L'aide est désactivée dans ce "
                "salon. ». Spec 043's version, decided by its approval on "
                "2026-10-22: the sheet's P7 hid the button, which would leave no way "
                "to confirm a pencil letter on a computer (_design.md §15). "
                "The vote result notes are drawn here too."
            ),
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    pressed={"aide", "kbd"},
                    stage_extra=note("Vote refusé."),
                    layer=phone_pop(aide_menu(none=True), left=60),
                ),
            ),
            (
                "pc",
                PC,
                desk_room(
                    pressed={"salon", "aide"},
                    main_extra=note("Temps écoulé, vote annulé."),
                    layer=desk_pop(aide_menu(none=True), left=980),
                ),
            ),
        ],
    )
    extra = specs_help()
    return part(
        "p-help",
        "4 · Help",
        "Check, reveal, the vote",
        "Help lives in one menu; its effects show on the cells and in the stream.",
        out + extra,
    )


# ---------------------------------------------------------------- completion


def share_card(error: bool = False) -> str:
    """Return the shared recap card, or its unavailable state."""
    if error:
        return (
            '<div class="card"><h1>Ce bilan n\'est pas disponible.</h1><span '
            'class="btn primary">Voir les grilles</span></div>'
        )
    return (
        '<div class="card"><h1>Grille terminée</h1><p class="muted">Grille n° 12</p>'
        '<div class="bigtime">Temps : 12:34</div><p>Équipe : Ana, '
        "Bruno, Céline, Dédé</p>"
        '<span class="btn primary">Voir les grilles</span></div>'
    )


def sec_end() -> str:
    """Return part 5, completion."""
    out = ""
    out += screen(
        "s-full",
        "Full but not right",
        ["§9 End of grid", "spec 026"],
        [
            (
                "A neutral band between the clue bar and the keyboard, which "
                "stays. No red, no cell changes look: players look for the "
                "mistake themselves."
            )
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    grid_opts={"full": True, "sel": (3, 3), "word": 6}, band="notyet"
                ),
            ),
            ("pc", PC, desk_room(notyet=True)),
        ],
    )
    out += screen(
        "s-done",
        "Grid solved",
        ["§9 End of grid", "spec 026"],
        [
            (
                "A green band under the clue bar with « Voir le bilan ». "
                "The keyboard goes; the timer stops."
            )
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    timer="12:34",
                    grid_opts={"solved": True},
                    off={"undo", "kbd"},
                    band="done",
                    kbd=None,
                    badge=None,
                    pressed=set(),
                    clue=("Alourdit le ballon", "→"),
                ),
            ),
            ("pc", PC, desk_room(solved=True)),
        ],
    )
    low = "Phone sideways · 568 &times; 320"
    out += screen(
        "s-rowstat",
        "The status in the clue bar's row",
        ["§9 End of grid", "spec 026", "spec 043", "until spec 044"],
        [
            (
                "On a touch screen in the sheet layout at most 500 px high, the "
                "keyboard shows and a band would take the grid's last height: the "
                "status sits in the navy clue bar, after the clue and before « "
                "Réagir », in white on one line; the clue gives it its width."
            ),
            (
                '<span class="m">Solved, until spec 044 is built: the keyboard '
                "still shows on a solved page in spec 043's build, so the solved "
                "status takes the row too, with « Voir le bilan » secondary; « "
                "Crayon » holds the fourth slot, disabled. From spec 044 on, the "
                "keyboard leaves a solved page and the status is the band; only "
                "the full-but-wrong row stays.</span>"
            ),
        ],
        [
            (
                "ph",
                low + " · full but wrong",
                phone_room(
                    size=(568, 320),
                    grid_opts={"full": True, "sel": (3, 3), "word": 6},
                    row_state="notyet",
                ),
            ),
            (
                "ph",
                low + " · solved (spec 043's build)",
                phone_room(
                    size=(568, 320),
                    timer="12:34",
                    grid_opts={"solved": True},
                    off={"undo", "pen"},
                    slot4="pen",
                    pressed=set(),
                    badge=None,
                    clue=("Alourdit le ballon", "→"),
                    row_state="done",
                ),
            ),
        ],
    )
    out += screen(
        "s-recap",
        "Recap",
        ["§9 Recap", "spec 028", "P16"],
        [
            (
                "Opens only when asked. Phone: a sheet over the whole window; "
                "computer: the 440 px dialog. Time, checks and reveals, « "
                "Qui a fait quoi » (no ranking: join order), the share link."
            ),
            (
                "Decided: after « Copier le lien » the button keeps its label "
                "and the green « Lien copié » line appears under it, as in "
                "the Joueurs tab (spec 028 today changes the button's text)."
            ),
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    timer="12:34",
                    grid_opts={"solved": True},
                    off={"undo", "kbd"},
                    band="done",
                    kbd=None,
                    badge=None,
                    pressed=set(),
                    clue=("Alourdit le ballon", "→"),
                    layer=phone_dialog_sheet(recap_body(True), recap=True),
                ),
            ),
            (
                "pc",
                PC,
                desk_room(solved=True, layer=desk_dialog(recap_body(), recap=True)),
            ),
        ],
    )
    rl = (
        '<h3>Bilan de la partie</h3><p class="dmuted">Chargement '
        'du bilan…</p><div class="end"><span class="btn primary">Fermer</span></div>'
    )
    re = (
        '<h3>Bilan de la partie</h3><span class="errtxt">Le bilan '
        'n\'est pas disponible.</span><div class="end"><span class="btn '
        'primary">Fermer</span></div>'
    )
    mini = (
        '<div class="mini">'
        + box(
            (
                '<div class="dialog" style="width:330px;box-shadow:none;border:1px '
                f'solid var(--nock-line)">{rl}</div>'
            ),
            "Recap loading (P10).",
        )
        + box(
            (
                '<div class="dialog" style="width:330px;box-shadow:none;border:1px '
                f'solid var(--nock-line)">{re}</div>'
            ),
            "Recap unavailable (P10).",
        )
        + "</div>"
    )
    out += mini
    out += screen(
        "s-share",
        "Shared recap page",
        ["spec 028", "P11"],
        [
            (
                "<code>/recap/&lt;token&gt;</code>, opened by anyone with "
                "the link; no room, no socket. Decided: an entry page (page "
                "grey, one card) with the time in the recap's large style "
                "and the team; « Voir les grilles » leads to the catalogue. "
                "The unavailable recap uses the same card."
            ),
        ],
        [
            ("ph", PH, phone_page(share_card())),
            ("ph", PH + " · unavailable", phone_page(share_card(True))),
            ("pc", PC, desk_page(share_card())),
        ],
    )
    extra = specs_end()
    return part(
        "p-end",
        "5 · Completion",
        "The end of a grid and the recap",
        "Finishing is the reward: one green band, one recap, one link to share.",
        out + extra,
    )


# ---------------------------------------------------------------- account


def account_page(state: str) -> str:
    """Return the account page's card in one of its states."""
    h = '<div class="card"><h1>Mon compte</h1>'
    if state == "in":
        h += (
            '<p>Connecté avec ana@exemple.fr</p><span class="tlink">Retourner '
            "au salon K7QM2X</span>"
            '<div class="row2"><span class="btn secondary">Se déconnecter</span><span '
            'class="btn secondary">Supprimer mon compte</span></div>'
        )
    elif state == "delete":
        h += (
            "<p>Connecté avec ana@exemple.fr</p>"
            '<div class="row2"><span class="btn secondary">Se déconnecter</span><span '
            'class="btn quiet">Supprimer mon compte</span></div>'
            '<p style="border-top:1px solid var(--nock-line);padding-top:12px">Votre '
            "adresse et la liste de vos salons seront effacées. Dans "
            "vos salons, votre pseudo deviendra « Ancien joueur ».</p>"
            '<div class="row2"><span class="btn '
            'primary">Supprimer définitivement</span><'
            'span class="btn secondary">Garder mon compte</span></div>'
        )
    elif state == "signing":
        h += '<p class="dmuted">Connexion…</p>'
    elif state == "invalid":
        h += (
            '<span class="errtxt">Ce lien n\'est plus valable. '
            "Demandez-en un nouveau.</span>"
            '<div class="field">Adresse e-mail<span '
            'class="input">ana@exemple.fr</span></'
            'div><span class="btn primary">Recevoir le lien</span>'
        )
    elif state == "out":
        h += (
            "<p>Recevez par e-mail un lien pour vous connecter.</p>"
            '<div class="field">Adresse e-mail<span '
            'class="input ph">nom@exemple.fr</span'
            '></div><span class="btn primary">Recevoir le lien</span>'
        )
    elif state == "deleted":
        h += (
            '<span class="okline">Votre compte a été supprimé.</span><span '
            'class="btn primary">Voir les grilles</span>'
        )
    elif state == "error":
        h += '<span class="errtxt">Une erreur est survenue. Réessayez.</span>'
    return h + "</div>"


def sec_account() -> str:
    """Return part 6, the account."""
    out = ""
    out += screen(
        "s-acc-room",
        "Sign-in link, from the room",
        ["§8 Room sheets", "spec 033"],
        [
            (
                "Menu « Compte ». Signed out: e-mail field, « Recevoir le "
                "lien », then the green confirmation; signed in: the address "
                "and « Gérer mon compte ». A phone sheet, a computer dialog."
            ),
        ],
        [
            (
                "ph",
                PH + " · link sent",
                phone_room(
                    pressed={"menu", "kbd"},
                    layer=phone_dialog_sheet(account_out("sent")),
                ),
            ),
            (
                "pc",
                PC + " · signed in",
                desk_room(pressed={"salon", "menu"}, layer=desk_dialog(account_in())),
            ),
        ],
    )
    out += screen(
        "s-acc-cat",
        "Sign-in link, from the catalogue",
        ["§10", "spec 033", "P13"],
        [
            (
                "« Compte » in the catalogue's top bar, pressed while open. "
                "Decided: outside a room the intro "
                "is <code>account.signed_out_intro</code> "
                "(« Recevez par e-mail un lien pour vous connecter. »), since "
                "<code>account.dialog_intro</code> speaks of « ce salon ». "
                "The field error is drawn on the phone."
            ),
        ],
        [
            (
                "ph",
                PH + " · invalid address",
                cat_with_sheet(True, account_out("error", in_room=False)),
            ),
            ("pc", PC, cat_with_sheet(False, account_out("idle", in_room=False))),
        ],
    )
    out += screen(
        "s-acc-page",
        "Account page and deletion",
        ["spec 033", "P12"],
        [
            (
                "<code>/account</code>, reached by « Gérer mon compte » or "
                "the e-mailed link. Decided: an entry page with one card "
                "« Mon compte ». Signed in: the address, a link back to the "
                "last room, « Se déconnecter » and « Supprimer mon compte "
                "», both secondary."
            ),
            (
                "Deletion asks once more in the same card: the warning in "
                "ink, then « Supprimer définitivement » (primary) and « Garder "
                "mon compte » (secondary). No red button: red means « look "
                "here », not « danger » (decision D1)."
            ),
        ],
        [
            ("ph", PH, phone_page(account_page("in"))),
            ("ph", PH + " · deleting", phone_page(account_page("delete"))),
            ("pc", PC + " · deleting", desk_page(account_page("delete"))),
        ],
    )
    mini = '<div class="mini">'
    for st, cap in [
        ("signing", "Opening the e-mailed link."),
        ("invalid", "Expired or used link: red line, then the form again."),
        ("out", "Signed out."),
        ("deleted", "After deletion: green line and a way out."),
        ("error", "Anything else failed."),
    ]:
        mini += box(
            (
                '<div style="width:330px;background:var(--nock-page);pa'
                "dding:16px;border-radi"
                f'us:6px">{account_page(st)}</div>'
            ),
            cap,
        )
    out += mini + "</div>"
    extra = specs_account()
    return part(
        "p-acc",
        "6 · Account",
        "Optional: a sign-in link by e-mail, no password",
        (
            "Guests can do everything; an account only remembers rooms "
            "and history across devices (spec 033)."
        ),
        out + extra,
    )


# ---------------------------------------------------------------- ops


REPLAY_STEPS = [
    "21:02:11 · Ana écrit T en (1, 0)",
    "21:02:13 · Ana écrit A en (1, 1)",
    "21:02:20 · Bruno écrit M en (1, 2)",
    "21:02:31 · Bruno écrit D au crayon en (2, 3)",
    "21:02:40 · Dédé écrit S en (1, 4)",
    "21:03:02 · Ana efface (1, 1)",
    "21:03:05 · Ana annule sa dernière modification en (1, 1)",
    "21:03:30 · (1, 2) verrouillée par une vérification",
    "21:04:12 · N révélée en (3, 4)",
    "21:04:20 · Céline écrit M en (3, 2)",
]


def ops_body(phone: bool) -> str:
    """Return the operator page's content."""
    seg = (
        '<div class="filters"><span class="fbtn" aria-pressed="false">Dernières '
        '24 heures</span><span class="fbtn" aria-pressed="true">7 '
        'derniers jours</span><span class="fbtn" aria-pressed="false">30 '
        "derniers jours</span></div>"
    )
    metrics = [
        "Salons créés : 42",
        "Joueurs par salon : 2,6",
        "Grilles terminées : 61 %",
        "Temps médian de résolution : 38 min 10 s",
        "Latence du serveur : 24 ms (médiane), 61 ms (95e centile)",
        "Coupures par joueur : aucune donnée",
    ]
    m = '<ul class="ops-metrics">' + "".join(f"<li>{x}</li>" for x in metrics) + "</ul>"
    letters = {
        (0, 1): {"l": "N"},
        (1, 0): {"l": "T"},
        (1, 1): {"l": "A"},
        (1, 2): {"l": "M", "locked": True},
        (1, 4): {"l": "S"},
        (2, 3): {"l": "D", "pencil": True},
        (3, 4): {"l": "N", "locked": True, "rev": True},
    }
    s = 36 if phone else 44
    g = grid(
        fx_rows(
            s, letters=letters, sel=None, others=[], flagged=set(), blank_clues=True
        ),
        s,
    )
    steps = "".join(
        f'<li class="{"now" if i == 8 else ("after" if i > 8 else "")}">{esc(t)}</li>'
        for i, t in enumerate(REPLAY_STEPS)
    )
    rng = (
        '<div class="field" style="width:100%">Étape<div class="range"><i '
        'style="width:90%"></i><b style="left:90%"></b></div></div><p '
        'class="muted" style="margin:0">Étape 9 sur 10</p>'
    )
    replay_form = (
        '<div class="row2" style="align-items:end;width:100%"><div '
        'class="field" style="flex:1;min-width:140px">Code du salon<span '
        'class="input">K7QM2X</span></div>'
        '<span class="btn primary">Relire</span></div>'
    )
    if phone:
        rep = (
            f'<div class="card"><h1>Relecture d\'un salon</h1>{replay_form}{g}{rng}<ol '
            f'class="edits">{steps}</ol></div>'
        )
    else:
        rep = (
            f'<div class="card"><h1>Relecture d\'un salon</h1>{replay_form}'
            '<div class="opsgrid" style="width:100%"><ol '
            f'class="edits">{steps}</ol><div '
            f'style="display:grid;gap:10px;justify-items:start">{g}{rng}'
            "</div></div></div>"
        )
    return (
        '<h1 class="cat-h">Exploitation</h1>'
        f'<div class="card"><h1>Tableau de bord</h1><div class="field">Période{seg}</d'
        f"iv>{m}</div>{rep}"
    )


def sec_ops() -> str:
    """Return part 7, the operator page."""
    token = (
        '<h1 class="cat-h">Exploitation</h1><div class="card">'
        '<div class="field">Jeton d\'opérateur'
        '<span class="input err">••••••••••••••••••••••</span></div>'
        '<span class="errtxt" style="margin-top:-6px">Jeton refusé.</span><span '
        'class="btn primary">Ouvrir</span></div>'
    )
    dash_ph = (
        f'<div class="phone" style="height:auto"><div class="dtop">{_brand()}<span '
        'class="gname"></span></div><main class="cat-main" style="background:var(--no'
        f'ck-page)">{ops_body(True)}</main></div>'
    )
    dash_pc = (
        '<div class="desk" style="height:auto;min-height:800px"><div '
        f'class="dtop">{_brand()}<span class="gname"></span></div><main '
        'class="cat-main" style="background:var(--nock-page);max-width:none;padding:2'
        f'4px max(24px, calc(50% - 460px))">{ops_body(False)}</main></div>'
    )
    out = screen(
        "s-ops",
        "Operator dashboard and room replay",
        ["spec 038", "P14", "P15"],
        [
            (
                "<code>/ops</code>, for the operator only, with the operator "
                "token. Decided: the catalogue's frame (top bar with the "
                "brand only, 920 px column) on the page grey. The token form "
                "is one card (password field, « Ouvrir », « Jeton refusé. "
                "» in red)."
            ),
            (
                "Dashboard: the three periods as the catalogue's filter chips "
                "(they wrap on a phone, where a segmented control would not "
                "fit), then one tile per figure, each fr.json line as it "
                "is (no split into label and number, so no new strings). "
                "Replay: the room code, then the edits in time order next "
                "to the grid at the chosen step and a step slider. The current "
                "step is in word blue, later steps muted. The grid reuses "
                "the playing grid's cells, without clue text."
            ),
        ],
        [
            ("ph", PH + " · token refused", phone_page(token, height=720)),
            ("ph", PH + " (unrolled)", dash_ph),
            ("pc", PC + " (unrolled)", dash_pc),
        ],
    )
    extra = specs_ops()
    return part(
        "p-ops",
        "7 · Operator",
        "The operator dashboard (spec 038)",
        "Not a player screen: kept plain, built only from the same components.",
        out + extra,
    )


# ---------------------------------------------------------------- keyboard


def sec_keyboard() -> str:
    """Return part 8, the keyboard."""
    out = screen(
        "s-kbd",
        "The in-app keyboard",
        ["§8 keyboard", "specs 009, 020"],
        [
            (
                "AZERTY, three rows: ✎ (pencil), W X C V B N, ⇄ (switch direction), "
                "⌫. Pressed ✎ turns navy and every letter key goes italic "
                "in pencil grey. « Clavier » hides the keyboard and the grid "
                "takes the space back; the choice is kept per browser."
            ),
        ],
        [
            (
                "ph",
                PH + " · pencil on",
                phone_room(kbd="pencil", grid_opts={"sel": (2, 3)}),
            ),
            ("ph", PH + " · keyboard hidden", phone_room(kbd=None, pressed=set())),
            ("pc", PC + " · touch screen", desk_room(kbd=True, column="stream")),
        ],
    )
    extra = specs_kbd()
    return part(
        "p-kbd",
        "8 · Keyboard",
        "Typing on a touch screen",
        (
            "Shown on touch screens only; a computer with a physical "
            "keyboard never sees it."
        ),
        out + extra,
    )


# ---------------------------------------------------------------- modes


def sec_modes() -> str:
    """Return part 9, the two modes."""
    out = screen(
        "s-authors",
        "« Auteurs » mode",
        ["§7", "spec 019"],
        [
            (
                "Menu « Auteurs ». Each letter in its finder's ink; revealed "
                "letters and letters of departed players stay ink; the wrong "
                "strike turns ink. The legend sits under the grid, which "
                "shrinks by 38 px so nothing else moves."
            ),
        ],
        [("ph", PH, phone_room(authors=True)), ("pc", PC, desk_room(authors=True))],
    )
    access_items = [
        ("evt", "→ Bruno a rejoint le salon", ""),
        ("msg", 0, "Quelqu'un a une idée pour « Fin de prière » ?"),
        ("msg", 1, "AMEN, je pense 👍"),
        ("msg", 2, "Je prends le bas à gauche."),
        ("msg", 3, "Et moi « Flaire »."),
    ]
    out += screen(
        "s-access",
        "« Accessibilité » mode",
        ["§6 player icons", "spec 035"],
        [
            (
                "Menu « Accessibilité ». Each corner triangle becomes the "
                "player's own icon (Rond, Carré, Triangle, Losange…) in their "
                "colour, in the same corners; the icon replaces the player "
                "dot in the stream, the Joueurs list and the recap. Colour "
                "is then never the only sign."
            ),
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    grid_opts={
                        "access": True,
                        "others": [
                            (1, (4, 4), 7),
                            (3, (4, 4), 4),
                            (2, (3, 2), 2),
                            (0, (4, 4), 5),
                        ][:3],
                    }
                ),
            ),
            (
                "ph",
                PH + " · Joueurs",
                phone_room(
                    pressed={"salon", "kbd"},
                    badge=None,
                    grid_opts={"access": True},
                    layer=salon_sheet(tab="players", access=True),
                ),
            ),
            ("pc", PC, desk_room(col_kw={"access": True, "items": access_items})),
        ],
    )
    icons = (
        '<div class="mini">'
        + box(
            '<div style="display:flex;flex-wrap:wrap;gap:10px 18px">'
            + "".join(
                (
                    '<span style="display:inline-flex;align-items:center;ga'
                    'p:6px;font-size:.9rem"'
                    f">{picon(i, 18)}<b>{n}</b></span>"
                )
                for i, n in enumerate(
                    [
                        "Ana · Rond",
                        "Bruno · Carré",
                        "Céline · Triangle",
                        "Dédé · Losange",
                        "Éloïse · Étoile",
                        "Farid · Croix",
                        "Gus · Cœur",
                        "Hugo · Sablier",
                    ]
                )
            )
            + "</div>",
            "One icon per join index, in the player's colour (§6 « Player icons »).",
        )
        + "</div>"
    )
    extra = specs_modes()
    return part(
        "p-modes",
        "9 · Modes",
        "« Auteurs » and « Accessibilité »",
        "Two switches of the Menu, off by default, remembered per browser.",
        out + icons + extra,
    )


# ---------------------------------------------------------------- states gallery


def sec_states() -> str:
    """Return part 10, the small states."""

    def notebox(t: str) -> str:
        return f'<div class="toast" style="position:static;transform:none">{t}</div>'

    notes = "".join(
        box(notebox(t), c)
        for t, c in [
            (esc("Bruno : AMEN, je pense 👍"), "Another player's message."),
            (f"{FLAG_ICO} Dédé bloque sur « Flaire »", "Je bloque."),
            ("▲ Dédé a révélé une lettre", "A reveal."),
            ("→ Bruno a rejoint le salon", "A join; departures with ←."),
            ("Rien à annuler.", "Annuler with nothing to undo (P9)."),
            ("Vote accepté.", "A vote's result (P6)."),
        ]
    )
    bars = box(
        f'<div style="width:330px">{cluebar("", empty=True)}</div>',
        (
            "No cell selected yet (P8): the hint; Réagir and Je bloque "
            "disabled in rule grey (spec 043, approved 2026-10-22)."
        ),
    ) + box(
        f'<div style="width:330px">{cluebar("Flaire", "↓", pressed=True)}</div>',
        "Je bloque pressed: white button, navy filled flag.",
    )
    buttons = (
        box(
            (
                '<div class="row2"><span class="btn primary">Jouer</span><span '
                'class="btn secondary">Rejouer</span><span class="btn quiet">Supprimer '
                "mon compte</span></div>"
            ),
            "Primary, secondary, quiet (pressed).",
        )
        + box(
            (
                '<div class="row2"><span class="btn off">Envoyer</span><span '
                'class="btn primary focus">Entrer dans le salon</span></div>'
            ),
            "Disabled (still 4.5:1), and the keyboard focus ring.",
        )
        + box(
            '<div style="display:grid;gap:10px;width:300px"><div '
            'class="switchrow">Verrou'
            'iller le salon<span class="tog"></span></div>'
            '<span class="seg"><span>libre</span><span class="on">par '
            "vote</span><span>désactivée</span></span></div>",
            "Switch off, segmented control.",
        )
        + box(
            '<div style="width:330px;display:grid;gap:8px"><div '
            'class="field">Pseudo<span'
            ' class="input caps">Ana</span></div>'
            '<div class="field">Adresse e-mail<span '
            'class="input err">ana@</span></div><s'
            'pan class="errtxt">Adresse e-mail non valide.</span></div>',
            "Fields: normal and in error.",
        )
        + box(
            '<div style="width:330px;display:grid;gap:10px"><div class="range"><i '
            'style="width:40%"></i><b style="left:40%"></b></div>'
            '<div class="prog" style="padding:0"><span>31 / 54 mots</span><div '
            'class="bar"><i style="width:57%"></i></div></div></div>',
            "The slider (P15) next to the progress bar it is built from.",
        )
    )
    return part(
        "p-states",
        "10 · Small states",
        "Notes, bars, controls",
        (
            "The pieces the screens above use, one by one. All from _design.md "
            "§11 and §8 « States »."
        ),
        (
            f'<div class="mini">{notes}</div><div class="mini">{bars}</div><div '
            f'class="mini">{buttons}</div>'
        ),
    )


# ---------------------------------------------------------------- later + decisions


DECISIONS = [
    (
        "P1",
        "Plain pages on a computer (entry, not found, account page, shared recap)",
        "_design.md draws these pages at phone width only.",
        (
            "The phone's column, centred, at most 420 px wide, 48 px "
            "under a 56 px top bar (the catalogue's), on the page grey. "
            "One layout, no new breakpoint."
        ),
        "A wide two-column page (more design, more edge cases).",
    ),
    (
        "P2",
        "The room while it connects and joins",
        (
            "<code>room-status</code> strings exist (« Connexion… », "
            "« Entrée dans le salon… ») but no look."
        ),
        (
            "Top bar in place, one muted line where the grid will be, "
            "no clue bar or keyboard yet; no spinner, no skeleton."
        ),
        "A skeleton grid (would need the grid's size before the snapshot).",
    ),
    (
        "P3",
        "A room that has expired",
        "Spec 032 deletes it, so it reads « Ce salon n'existe pas. ».",
        (
            "Same card as not found, plus one muted line « Un salon est "
            "effacé 30 jours après sa dernière modification. » (a new "
            "fr.json key), with « Voir les grilles » primary."
        ),
        "No extra line (no new string; the player may think the link is wrong).",
    ),
    (
        "P4",
        "Loading, empty and error states of the catalogue and « Mes salons »",
        (
            "Strings exist (<code>catalogue.*</code>, <code>my_rooms.*</code>), "
            "looks do not."
        ),
        (
            "One line where the content will be: muted while loading "
            "or empty, red on error; a failed « Jouer » puts the red "
            "line inside its card. « Mes salons » shows nothing while "
            "it loads and has no section when there is no room."
        ),
        "Skeleton cards (more motion, more states to test).",
    ),
    (
        "P5",
        "Chat moderation and chat notes",
        (
            "Spec 022's « Sourdine » block (Couper / Rétablir per player) "
            "and the notes « Patientez avant d'envoyer. », « L'hôte a "
            "coupé votre discussion. » have no place in _design.md."
        ),
        (
            "Host's « Couper » / « Rétablir » as small secondary buttons "
            "beside « Retirer », on a line under each other player's "
            "row in Joueurs; the notes as one muted line under the message "
            "box; a muted player's box disabled (clue blue-grey, muted). "
            "Spec 022 is refined to drop the Sourdine block."
        ),
        (
            "Keep a « Sourdine » block at the bottom of the Discussion "
            "tab (two places for host tools)."
        ),
    ),
    (
        "P6",
        "The vote after one has voted, and its result",
        "§9 draws the question only.",
        (
            "After my vote, « Oui » / « Non » give way to a muted « Vote "
            "enregistré. En attente des autres joueurs… »; the asker "
            "sees « En attente des autres joueurs… »; the result is a "
            "3-second note when the banner goes, and a line in the stream."
        ),
        (
            "Keep the buttons with the chosen one pressed (needs a pressed "
            "style for buttons)."
        ),
    ),
    (
        "P7",
        "Help with no budget left, and help switched off",
        "_design.md §12 says « Aide » is hidden in « désactivée » mode « to confirm ».",
        (
            "Spent items stay, muted and inert, with « Plus de lettre "
            "» / « Plus de mot » as the detail; in « désactivée » mode "
            "the Aide button is not drawn."
        ),
        (
            "Hide spent items (the menu changes shape); show Aide disabled "
            "(a button that does nothing)."
        ),
    ),
    (
        "P8",
        "The clue bar before any cell is selected",
        "<code>clue_bar.empty</code> exists, no look.",
        (
            "White hint text « Touchez une case ou une définition. », "
            "the &lsaquo; &rsaquo; chevrons only; Réagir and Je bloque "
            "are not drawn until a word is selected."
        ),
        "Show them disabled (needs a disabled look on navy, which _design.md lacks).",
    ),
    (
        "P9",
        "« Rien à annuler. »",
        "No place for it.",
        "A 3-second note, as every short message of the room.",
        "Disable « Annuler » (the top bar would need a disabled look).",
    ),
    (
        "P10",
        "Recap loading and unavailable",
        "Strings exist, no look.",
        (
            "Inside the sheet or dialog: the title, then a muted « Chargement "
            "du bilan… », or the red « Le bilan n'est pas disponible. "
            "», and « Fermer »."
        ),
        "",
    ),
    (
        "P11",
        "The shared recap page <code>/recap/&lt;token&gt;</code>",
        "Not drawn.",
        (
            "An entry page with one card: « Grille terminée », « Grille "
            "n° 12 » muted, the time in the recap's large style, « Équipe "
            ": … », primary « Voir les grilles ». The unavailable recap "
            "uses the same card."
        ),
        "",
    ),
    (
        "P12",
        "Account page <code>/account</code> and deletion",
        "Not drawn; no « danger » button exists.",
        (
            "An entry page with one card « Mon compte »; « Se déconnecter "
            "» and « Supprimer mon compte » both secondary; the confirmation "
            "in the same card with « Supprimer définitivement » primary "
            "and « Garder mon compte » secondary. No red button: red "
            "keeps its one job (« look here »)."
        ),
        (
            "A red « danger » button variant (a new component and a second "
            "meaning for red)."
        ),
    ),
    (
        "P13",
        "Account sheet outside a room",
        "<code>account.dialog_intro</code> says « dans ce salon ».",
        (
            "On the catalogue, use <code>account.signed_out_intro</code> "
            "as the intro; keep the dialog's title."
        ),
        "",
    ),
    (
        "P14",
        "Operator page <code>/ops</code>",
        "Not drawn.",
        (
            "The catalogue's frame and column; token form in one card; "
            "periods as the catalogue's filter chips; one tile per figure "
            "with fr.json's line as it is; the replay as a list of edits "
            "beside the grid (reusing the cell styles, no clue text) "
            "and a step slider."
        ),
        "Leave it with browser defaults (it is for one operator).",
    ),
    (
        "P15",
        "A slider (the replay's step)",
        "No range control in §11.",
        (
            "Built from the progress bar: word-blue track 6 px, navy "
            "fill, 18 px navy knob, the focus ring of §11. Added to §11 "
            "as a component."
        ),
        "",
    ),
    (
        "P16",
        "« Lien copié » in the recap",
        (
            "Spec 028 changes the button's text; §8 uses a green line "
            "under the invite button."
        ),
        (
            "One pattern: the button keeps « Copier le lien » and the "
            "green line « Lien copié » appears, as in Joueurs (spec 028 "
            "refined)."
        ),
        "",
    ),
]

OTHER_DECISIONS = [
    ("D1", "Is a destructive action ever red?", "No. See P12.", ""),
    (
        "D2",
        "Grid credits (spec 005)",
        (
            "Credits are not sent to players today, and _design.md §12 "
            "lists the gap. Recommended: leave them out of the screens "
            "until a spec sends them; then one muted line on the catalogue "
            "card (« Auteur : Équipe Nock »)."
        ),
        "",
    ),
    (
        "D3",
        "The sheet's fonts",
        (
            "This sheet loads the app's own font "
            "files from <code>web/node_modules/@fonts"
            "ource</code> once spec 041's packages are installed, else "
            "a local copy, else the fallback stack (Segoe UI). Recommended: "
            "keep it so, never Google."
        ),
        "",
    ),
]


# ---------------------------------------------------------------- specs 044 to 048
# Screens specs 044 to 048 decide (approved by the human on 2026-10-22, with the
# recommended answer of each open question). Each answer carries a « decided spec
# NNN OQn » label and an item in part 13.

FX02 = HERE.parent.parent.parent / "tests" / "fixtures" / "fx02.json"
LONG_NAMES = [
    "Jean-Luc",
    "D'Artagnan",
    "Anne-Sophie",
    "Maximilien",
    "Bérénice",
    "Guillaume",
    "Marie-Ange",
    "Christophe",
]


def specs_cat() -> str:
    """Return the catalogue screens of spec 046."""
    card = cat_card(ITEMS[0], True)
    ph = (
        '<div class="phone" style="height:auto"><div class="dtop">'
        f'{_brand()}<span class="gname"></span></div><main class="cat-main">'
        f'<div class="clist">{card}</div></main></div>'
    )
    pc = (
        f'<div class="desk"><div class="dtop">{_brand()}<span class="gname"></span>'
        f'</div><main class="cat-main bare"><div class="clist">'
        f"{cat_card(ITEMS[0], False)}</div></main></div>"
    )
    out = screen(
        "s-gridpage",
        "Grid page <code>/g/12</code>",
        ["§10", "spec 046", "spec 004"],
        [
            "One grid's card in the catalogue's frame: the 56 px brand bar with no "
            "« Compte », no heading, the card alone. On a computer the list keeps "
            "its two columns, so the lone card keeps its drawing.",
            '<span class="m">States, in the card\'s place: « Chargement… » muted, '
            "« Impossible de charger les grilles. » as an error line, « Page "
            "introuvable » muted.</span>",
        ],
        [("ph", PH, ph), ("pc", PC, pc)],
    )
    wide = catalogue(False).replace(
        'style="height:auto;min-height:800px"',
        'style="width:1024px;height:auto;min-height:768px"',
    )
    tall = (
        catalogue(True)
        .replace(
            '<div class="phone" style="height:auto">',
            '<div class="desk" style="width:768px;height:auto;min-height:1024px">',
        )
        .replace(
            '<main class="cat-main">', '<main class="cat-main" style="padding:16px">'
        )
    )
    out += screen(
        "s-cat-tablets",
        "Catalogue on tablets",
        ["§10", "spec 046", "decided spec 046 OQ1"],
        [
            "A landscape tablet (1024 &times; 768) is a wide window: two cards per "
            "row, with their drawings, 24 px padding. A portrait tablet (768 &times; "
            "1024) is narrow: one card per row, no drawing, 16 px padding, « Compte » "
            "34 px high.",
            '<span class="m">Decided (spec 046 Open question 1): « wide » is the '
            "room's threshold for its computer top bar (landscape, at least 900 px "
            "wide, more than 500 px high), so a portrait tablet takes the phone's "
            "form.</span>",
        ],
        [
            ("pc", "Tablet, landscape · 1024 &times; 768 (unrolled)", wide),
            ("pc", "Tablet, portrait · 768 &times; 1024 (unrolled)", tall),
        ],
    )
    return out


def specs_entry() -> str:
    """Return the entry page of a portrait tablet (spec 046)."""
    return screen(
        "s-portrait",
        "Entry pages on a portrait tablet",
        ["§8 Entry pages", "spec 046", "decided spec 046 OQ1"],
        [
            "768 &times; 1024 is a narrow window: the phone's 54 px bar (padding "
            "0 14 px) and the phone's page padding (20 px 16 px), the card in a "
            "centred column of at most 420 px.",
        ],
        [
            (
                "pc",
                "Tablet, portrait · 768 &times; 1024",
                desk_page(NICK_OK, size=(768, 1024), narrow=True),
            ),
            (
                "pc",
                "Tablet, landscape · 1024 &times; 768",
                desk_page(NICK_OK, size=(1024, 768)),
            ),
        ],
    )


def specs_room() -> str:
    """Return the message box states of spec 047."""
    boxes = (
        box(
            (
                '<div style="width:330px;border:1px '
                f'solid var(--nock-line)">{compose()}</div>'
            ),
            "Empty input: « Envoyer » disabled (spec 041's disabled look).",
        )
        + box(
            '<div style="width:330px;border:1px solid var(--nock-line)">'
            f'{compose(typed="Je prends le bas")}</div>',
            "Text typed: « Envoyer » enabled.",
        )
        + box(
            (
                '<div style="width:330px;border:1px '
                f'solid var(--nock-line)">{compose(muted=True)}</div>'
            ),
            "Muted by the host: input and « Envoyer » disabled, the note under them.",
        )
    )
    return (
        '<article class="scr" id="s-send"><h3>Message box '
        + marks(["§8 Salon", "spec 047"])
        + '</h3><p class="cap">« Envoyer » takes the disabled look whenever spec 022 '
        "disables it: an empty input, pacing, a page not joined, a muted player.</p>"
        f'<div class="mini">{boxes}</div></article>'
    )


VOTE_CLOSED = [
    ("evt", "→ Bruno a rejoint le salon", ""),
    ("msg", 1, "On révèle une lettre ?"),
    ("msg", 0, "D'accord."),
    ("evt", "Vote accepté.", ""),
    ("evt", "▲ Bruno a révélé une lettre", "rev"),
]


def specs_help() -> str:
    """Return the vote screens of spec 047."""
    return screen(
        "s-vote-end",
        "A vote learned from a snapshot, and the end of a vote",
        [
            "§9 Vote",
            "spec 047",
            "decided spec 047 OQ1",
            "decided spec 047 OQ2",
            "decided spec 047 OQ4",
        ],
        [
            "After a reload or a late join, the page knows the vote but not when it "
            "opened: the banner has no seconds and no bar (Open question 2).",
            "When the vote closes, the banner leaves at once and never shows the "
            "result (Open question 1). The result is a muted stream line with no "
            "pictogram, whatever the outcome (Open question 4), and a 3-second note "
            "when the stream is not shown.",
        ],
        [
            (
                "ph",
                PH + " · vote from a snapshot",
                phone_room(stage_extra=vote_banner("snap")),
            ),
            (
                "ph",
                PH + " · vote closed",
                phone_room(stage_extra=note("Vote accepté.")),
            ),
            (
                "pc",
                PC + " · vote closed",
                desk_room(col_kw={"items": VOTE_CLOSED}),
            ),
        ],
    )


def specs_end() -> str:
    """Return the end band and recap screens of spec 047."""
    band = box(
        f'<div style="width:320px">{band_done()}</div>',
        "Solved at 320 px: the text wraps, « Voir le bilan » stays whole on the "
        "right (spec 047 Decision 7).",
    )
    solved = {"grid_opts": {"solved": True}, "band": "done", "kbd": None, "badge": None}
    out = (
        '<article class="scr" id="s-band320"><h3>The end band on the narrowest '
        "window " + marks(["§9 End of grid", "spec 047"]) + "</h3>"
        f'<div class="mini">{band}</div></article>'
    )
    out += screen(
        "s-recap-left",
        "Recap with a player who left",
        ["§9 Recap", "spec 047", "decided spec 047 OQ3"],
        [
            "A player the page no longer knows keeps their row, name and counts, with "
            "no dot: an empty slot keeps the names aligned (Open question 3; spec "
            "028's hatching goes). On a phone the URL box takes the full width and "
            "« Copier le lien » goes under it, on the left (Decision 9).",
        ],
        [
            (
                "ph",
                PH,
                phone_room(
                    timer="12:34",
                    pressed=set(),
                    off={"undo", "kbd"},
                    clue=("Alourdit le ballon", "→"),
                    layer=phone_dialog_sheet(
                        recap_body(True, departed=True), recap=True
                    ),
                    **solved,
                ),
            ),
            (
                "pc",
                PC,
                desk_room(
                    solved=True,
                    layer=desk_dialog(recap_body(departed=True), recap=True),
                ),
            ),
        ],
    )
    return out


def specs_account() -> str:
    """Return the loading states of spec 048."""
    acc = '<div class="card"><h1>Mon compte</h1></div>'
    share = '<div class="card"><p class="loadline">Chargement du bilan…</p></div>'
    boxes = box(
        (
            '<div style="width:330px;background:var(--nock-page);pa'
            f'dding:16px;border-radius:6px">{acc}</div>'
        ),
        "Account page while its first request runs: the title only (decided, spec "
        "048 Open question 1).",
    ) + box(
        (
            '<div style="width:330px;background:var(--nock-page);pa'
            f'dding:16px;border-radius:6px">{share}</div>'
        ),
        "Shared recap page while it loads: the card holds one waiting line.",
    )
    return (
        '<article class="scr" id="s-loading-pages"><h3>Plain pages while they load '
        + marks(["§8 States", "spec 048", "decided spec 048 OQ1"])
        + f'</h3><div class="mini">{boxes}</div></article>'
    )


def fx02_grid(s: int) -> str:
    """Return FX-02 at a step of a replay: letters, a pencil, locks, a reveal."""
    import json

    data = json.loads(FX02.read_text(encoding="utf-8"))
    rows: list[list[dict]] = [
        [{} for _ in range(data["width"])] for _ in range(data["height"])
    ]
    n = 0
    for c in data["cells"]:
        r, col = c["row"], c["column"]
        if c["type"] == "empty":
            rows[r][col] = {"type": "empty"}
        elif c["type"] == "clue":
            rows[r][col] = {
                "type": "clue",
                "clues": [{"text": ""}],
                "blank": True,
            }
        else:
            n += 1
            o: dict = {"cls": []}
            if n % 3 != 0:
                o["letter"] = "ESARINTULOMDPCGBVHFQ"[(r * 7 + col * 3) % 20]
                if n in (4, 5, 6):
                    o["cls"].append("locked")
                if n == 11:
                    o["cls"] += ["locked", "rev"]
                if n == 17:
                    o["cls"].append("pencil")
            rows[r][col] = o
    return grid(rows, s)


def specs_ops() -> str:
    """Return the replay's one-column form and states (spec 048)."""
    steps = "".join(
        f'<li class="{"now" if i == 8 else ("after" if i > 8 else "")}">{esc(t)}</li>'
        for i, t in enumerate(REPLAY_STEPS)
    )
    rng = (
        '<div class="field" style="width:100%">Étape<div class="range"><i '
        'style="width:90%"></i><b style="left:90%"></b></div></div><p class="muted" '
        'style="margin:0">Étape 9 sur 10</p>'
    )
    form = (
        '<div class="row2" style="align-items:end;width:100%"><div class="field" '
        'style="flex:1;min-width:140px">Code du salon<span class="input">K7QM2X</span>'
        '</div><span class="btn primary">Relire</span></div>'
    )
    rep = (
        f'<div class="card"><h1>Relecture d\'un salon</h1>{form}{fx02_grid(22)}{rng}'
        f'<ol class="edits">{steps}</ol></div>'
    )
    ph = (
        f'<div class="phone" style="height:auto"><div class="dtop">{_brand()}<span '
        'class="gname"></span></div><main class="cat-main" '
        'style="background:var(--nock-page)">'
        f'<h1 class="cat-h">Exploitation</h1>{rep}</main></div>'
    )
    out = screen(
        "s-ops-fx02",
        "Replay of a full-size grid, one column",
        [
            "§8 Plain pages",
            "spec 048",
            "decided spec 048 OQ3",
            "decided spec 048 OQ4",
            "decided spec 048 OQ5",
        ],
        [
            "Under 900 px wide the replay is one column: the grid, the slider, the "
            "step, then the edits (Open question 3). FX-02's 13 columns get 22 px "
            "cells at 360 px. The cells show pencil, locked and revealed marks (Open "
            "question 4); the slider is drawn under a transparent native input (Open "
            "question 5).",
        ],
        [("ph", PH + " (unrolled)", ph)],
    )
    states = (
        box(
            f'<div style="width:330px" class="card">{form}<span class="errtxt">'
            "Salon introuvable.</span></div>",
            "Unknown code: an error line under the form.",
        )
        + box(
            f'<div style="width:330px" class="card">{form}<p class="loadline" '
            'style="margin:0">Aucune modification dans ce salon.</p></div>',
            "A room with no edit: the muted line only, no grid, no slider (decided, "
            "spec 048 Open question 2).",
        )
        + box(
            '<div style="width:300px;padding:8px"><div class="range focus"><i '
            'style="width:40%"></i><b style="left:40%"></b></div></div>',
            "The slider focused with the keyboard: §11's focus ring on the knob.",
        )
    )
    out += (
        '<article class="scr" id="s-ops-states"><h3>Replay states '
        + marks(["spec 048", "decided spec 048 OQ2"])
        + f'</h3><div class="mini">{states}</div></article>'
    )
    return out


def specs_kbd() -> str:
    """Return the keyboard screens of spec 044."""
    out = screen(
        "s-kbd-low",
        "A phone held sideways, keyboard shown",
        ["§8 keyboard", "spec 044", "decided spec 044 OQ1"],
        [
            "A window at most 500 px high with the keyboard shown keeps the sheet "
            "layout; its keys are 28 px high instead of 44 px, so the grid keeps "
            "about 106 px at 740 &times; 360 (Open question 1). Hidden, the keyboard "
            "gives the window to the column layout.",
        ],
        [
            (
                "ph",
                "Phone sideways · 740 &times; 360",
                phone_room(size=(740, 360), grid_opts={"sel": (2, 3)}),
            )
        ],
    )
    out += screen(
        "s-low-column",
        "A phone held sideways, keyboard hidden",
        ["§8 column layout", "spec 043", "spec 044 Decision 8"],
        [
            "With the keyboard hidden, a window at most 500 px high is in the column "
            "layout, but keeps the phone top bar: the computer bar's brand and "
            "labelled buttons need about 650 px. « Salon » is pressed while the "
            "340 px column is open (open by default); the menus open 58 px from the "
            "top, as on a phone. The clue bar is as wide as the smaller of 320 px "
            "and the play area (about 203 px at 568 &times; 320).",
            '<span class="m">The same frame is drawn for a low desktop window '
            "(568 &times; 320), with « Crayon » in the fourth slot.</span>",
        ],
        [
            (
                "ph",
                "Phone sideways · 740 &times; 360 · keyboard hidden",
                low_column_room(),
            ),
            (
                "ph",
                "Low desktop window · 568 &times; 320",
                low_column_room((568, 320), touch=False),
            ),
        ],
    )
    bars = (
        box(
            (
                '<div style="width:360px;border:1px '
                f'solid var(--nock-line)">{phone_top(slot4="pen")}</div>'
            ),
            "A narrow window without touch: no keyboard, « Crayon » in the fourth "
            "slot (decided, spec 044 Open question 2).",
        )
        + box(
            '<div style="width:360px;border:1px solid var(--nock-line)">'
            f'{phone_top(timer="12:34", off={"undo", "kbd"})}</div>',
            "Solved: « Annuler » and « Clavier » disabled, not removed (decided, "
            "spec 044 Open question 4).",
        )
        + box(
            f'<div style="width:360px">{keyboard()}</div>',
            "The keys: ✎ « Crayon », ⇄ « Changer de sens » (decided, spec 044 Open "
            "question 5), ⌫ « Effacer ».",
        )
    )
    out += (
        '<article class="scr" id="s-kbd-slots"><h3>The fourth slot and the keys '
        + marks(["spec 044", "decided spec 044 OQ2", "decided spec 044 OQ4"])
        + f'</h3><div class="mini">{bars}</div></article>'
    )
    return out


def specs_modes() -> str:
    """Return the wrapped Auteurs legend (spec 045)."""
    return screen(
        "s-legend-wrap",
        "« Auteurs » with eight long names",
        ["§7", "spec 045", "decided spec 045 OQ2"],
        [
            "The legend wraps onto more lines, each centred, never wider than the "
            "grid area; the grid gives it the room of each further line, so nothing "
            "else moves (Open question 2). Spec 045 Open question 1 (no sign of "
            "authorship beyond colour and the legend) changes nothing drawn.",
        ],
        [
            (
                "ph",
                PH,
                phone_room(authors=True, legend_names=LONG_NAMES, legend_lines=3),
            )
        ],
    )


DRAFT_OQS = [
    ("044", "1", "Keys 28 px high on a window at most 500 px high.", "s-kbd-low"),
    (
        "044",
        "2",
        "Off a touch screen, « Crayon » in the phone top bar's fourth slot.",
        "s-kbd-slots",
    ),
    (
        "044",
        "3",
        "A phone held sideways goes to the column layout once solved.",
        "s-kbd-low",
    ),
    ("044", "4", "« Clavier » disabled, not removed, once solved.", "s-kbd-slots"),
    ("044", "5", "⇄ is named « Changer de sens ».", "s-kbd-slots"),
    (
        "045",
        "1",
        (
            "No sign of authorship beyond the inks "
            "and the legend (the design of 2026-10-16)."
        ),
        "s-legend-wrap",
    ),
    (
        "045",
        "2",
        "A long legend wraps, and the grid gives it each further line.",
        "s-legend-wrap",
    ),
    (
        "046",
        "1",
        (
            "« Wide » is the room's computer threshold; "
            "a portrait tablet takes the phone's "
            "form."
        ),
        "s-portrait",
    ),
    (
        "046",
        "2",
        "The catalogue's « Compte » opens the account sheet or dialog (P13).",
        "s-acc-cat",
    ),
    (
        "046",
        "3",
        "The room's top bar while it opens is drawn as once joined, inert.",
        "s-loading",
    ),
    (
        "047",
        "1",
        (
            "The banner leaves when the vote closes; "
            "the result is a note and a stream "
            "line."
        ),
        "s-vote-end",
    ),
    (
        "047",
        "2",
        "No seconds and no bar for a vote known only from a snapshot.",
        "s-vote-end",
    ),
    (
        "047",
        "3",
        "A player who left has no dot in the recap, an empty slot kept.",
        "s-recap-left",
    ),
    ("047", "4", "The vote's stream line is muted for every outcome.", "s-vote-end"),
    (
        "048",
        "1",
        "The account page shows its title only while it loads.",
        "s-loading-pages",
    ),
    ("048", "2", "A replay with no edit shows its muted line only.", "s-ops-states"),
    (
        "048",
        "3",
        "The replay goes to two columns at a window 900 px wide.",
        "s-ops-fx02",
    ),
    (
        "048",
        "4",
        "The replay's cells show pencil, locked and revealed marks.",
        "s-ops-fx02",
    ),
    (
        "048",
        "5",
        "The slider is drawn by three parts under a transparent native input.",
        "s-ops-fx02",
    ),
]


def sec_pending() -> str:
    """Return part 13: the open questions of specs 044 to 048, decided."""
    items = "".join(
        f'<li><span class="q"><span class="dec">decided spec {spec} OQ{q}</span> '
        f'{text}</span><span class="alt">Drawn: '
        f'<a href="#{where}">{where}</a></span></li>'
        for spec, q, text, where in DRAFT_OQS
    )
    return part(
        "p-pending",
        "13 · Specs 044 to 048",
        "Their open questions, decided",
        "The human approved specs 044 to 048 on 2026-10-22 with the recommended "
        "answer of each open question; each answer is drawn as decided "
        "(_design.md section 15).",
        f'<ol class="decisions">{items}</ol>',
    )


def sec_later() -> str:
    """Return part 11, the competitive modes to come."""
    return part(
        "p-later",
        "11 · Later",
        "Competitive modes (specs 030 and 031)",
        "Race mode and team mode are approved but queued after the "
        "design (human, 2026-10-22). They are not drawn here. When "
        "they come, they reuse the same pieces: "
        "the room's top bar and Salon, a team's colour taken from "
        "the player colours of §3 (never a new hue), and the recap. "
        "Their new screens (choosing a mode before « Jouer », a score "
        "or "
        "progress per team) will need a page of their own in this sheet.",
        "",
    )


def sec_decisions() -> str:
    """Return the record of the decisions, with the three spec 043 settled."""
    items = ""
    for pid, title, now, rec, alt in DECISIONS:
        a = f'<span class="alt">Not chosen: {alt}</span>' if alt else ""
        items += (
            f'<li id="d-{pid}"><span class="q"><span class="dec">{pid}</span> '
            f"{title}</span>"
            f'<span class="alt">Before: {now}</span><span class="rec"><b>Decided:</b> '
            f"{rec}</span>{a}</li>"
        )
    for pid, title, rec, _ in OTHER_DECISIONS:
        items += (
            f'<li id="d-{pid}"><span class="q"><span class="dec">{pid}</span> '
            f'{title}</span><span class="rec"><b>Decided:</b> {rec}</span></li>'
        )
    pending = ""
    for title, sheet, spec in MEETS_043:
        pending += (
            '<li><span class="q"><span class="dec">spec 043 approved</span> '
            f"{title}</span>"
            f'<span class="alt">Set aside: {sheet}</span><span class="rec">'
            f"<b>Decided:</b> {spec}</span></li>"
        )
    return part(
        "p-decisions",
        "12 · Decisions",
        "What this sheet added to _design.md",
        (
            "The human accepted every recommended answer of version 1.0 "
            "on 2026-10-22; _design.md §15 lists them and the sections "
            "that now carry them."
        ),
        f'<ol class="decisions">{items}</ol>'
        '<h3 id="d-043" style="margin:8px 0 0;font:700 1.1rem/1.3 '
        'var(--nock-font-ui)">Where the sheet met spec 043</h3>'
        '<p class="lead">The sheet was drawn from <code>main</code>, before '
        "spec 043 (room layout) was drafted. On three points the accepted "
        "answer and spec 043's pick differed; the human approved spec 043 on "
        "2026-10-22, so its version is decided on all three.</p>"
        f'<ol class="decisions">{pending}</ol>',
    )


MEETS_043 = [
    (
        "The Joueurs row",
        (
            "P5: the state and clue on the right of the name, the host's "
            "buttons on a second line."
        ),
        (
            "spec 043's: the state and clue on a second line under the "
            "name, the buttons on the right of the first, so the current "
            "clue never ends in an ellipsis at 340 px."
        ),
    ),
    (
        "Help mode « désactivée »",
        "P7: the « Aide » button is not drawn.",
        (
            "spec 043's: « Aide » stays and its menu holds the pencil "
            "confirm or « L'aide est désactivée dans ce salon. »; hiding "
            "it would leave no way to confirm a pencil letter on a computer."
        ),
    ),
    (
        "Réagir and Je bloque while nothing is selected",
        "P8: not drawn.",
        (
            "spec 043's: drawn disabled, the icon in rule grey (5.22:1 "
            "on navy), so the clue bar keeps its shape."
        ),
    ),
]


# ---------------------------------------------------------------- page


def header() -> str:
    """Return the sheet's header, width switch and summary."""
    nav = "".join(
        f'<a href="#{i}">{t}</a>'
        for i, t in [
            ("p-cat", "Catalogue"),
            ("p-entry", "Entry"),
            ("p-room", "Room"),
            ("p-help", "Help"),
            ("p-end", "End"),
            ("p-acc", "Account"),
            ("p-ops", "Ops"),
            ("p-kbd", "Keyboard"),
            ("p-modes", "Modes"),
            ("p-states", "States"),
            ("p-decisions", "Decisions"),
        ]
    )
    routes = [
        (
            "<code>/</code>",
            "Catalogue, « Mes salons », « Grilles terminées », account sheet",
            "1, 6",
        ),
        (
            "<code>/r/&lt;code&gt;</code>",
            "Nickname form, refusal cards, the room and everything in it, recap",
            "2 to 5, 8, 9",
        ),
        ("<code>/recap/&lt;token&gt;</code>", "Shared recap page", "5"),
        ("<code>/account</code>", "Account page, deletion", "6"),
        ("<code>/ops</code>", "Operator dashboard and replay", "7"),
        ("any other", "Page introuvable", "2"),
    ]
    rt = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td></tr>" for a, b, c in routes)
    tmpl = Template((HERE / "header.html").read_text(encoding="utf-8"))
    return tmpl.substitute(nav=nav, rt=rt)


def build_page() -> str:
    """Return the whole sheet as one HTML page."""
    body = (
        header()
        + sec_catalogue()
        + sec_entry()
        + sec_room()
        + sec_help()
        + sec_end()
        + sec_account()
        + sec_ops()
        + sec_keyboard()
        + sec_modes()
        + sec_states()
        + sec_later()
        + sec_decisions()
        + sec_pending()
    )
    page = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Nock Screens Sheet</title>\n<style>\n"
        + font_faces()
        + CSS
        + '</style>\n</head>\n<body>\n<div class="wrap">\n'
        + body
        + "\n</div>\n</body>\n</html>\n"
    )
    return page


def main() -> int:
    """Write the sheet, or with --check, report whether it is up to date.

    Returns:
        The exit code: 0 when written or up to date, 1 when the committed sheet
        differs from what the sources build.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare docs/design/screens-sheet.html with the sources, write nothing",
    )
    arguments = parser.parse_args()
    page = build_page()
    if arguments.check:
        # Line endings may differ on a Windows checkout; the content may not.
        on_disk = SHEET.read_bytes().decode("utf-8") if SHEET.is_file() else ""
        if on_disk.replace("\r\n", "\n") == page:
            print("screens sheet: up to date")
            return 0
        print(
            "screens sheet: docs/design/screens-sheet.html is not what its sources "
            "build. Run: uv run python docs/design/screens_sheet/build.py"
        )
        return 1
    SHEET.write_bytes(page.encode("utf-8"))
    print(f"wrote {SHEET} ({len(page) // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
