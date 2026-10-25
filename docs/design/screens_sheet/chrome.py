"""Screen chrome for the screens sheet: bars, keyboard, Salon, menus, dialogs."""

from __future__ import annotations

from cells import (
    BH,
    BW,
    FLAG_ICO,
    FX_CLUE_TEXT,
    FX_DIR,
    IC,
    NOCK,
    big_rows,
    dot,
    esc,
    floor,
    fx_rows,
    grid,
)

FOUR = ["Ana", "Bruno", "Céline", "Dédé"]
NODOT = '<i class="pdot none"></i>'
YOU = ' <span class="you">(vous)</span>'
URL_ROOM = "https://nock.fr/r/K7QM2X"
URL_RECAP = "https://nock.fr/recap/k7Qm2xTa9LpR4vWd"


def brand(state: str = "") -> str:
    """Return the brand link: the Nock mark and name (foundation.md, « Components »).

    Args:
        state: "hover" or "focus" draws that state; empty, the brand at rest.
    """
    cls = f"brand {state}" if state else "brand"
    return f'<span class="{cls}">{NOCK}Nock</span>'


# ---------- phone room ----------
def tb(
    icon: str, label: str, pressed: bool = False, extra: str = "", off: bool = False
) -> str:
    """Return a phone top-bar button, muted when disabled (spec 043)."""
    cls = "tb off" if off else "tb"
    return (
        f'<span class="{cls}" aria-pressed="{str(pressed).lower()}"'
        f">{IC[icon]}{label}{extra}"
        "</span>"
    )


def phone_top(
    timer: str | None = "4:12",
    pressed: set | None = None,
    badge: str | None = None,
    newdot: bool = False,
    aide: bool = True,
    off: set | None = None,
    slot4: str = "kbd",
) -> str:
    """Return the phone top bar of the room."""
    pressed = pressed or set()
    off = off or set()
    left = (
        f'<span class="timer">{timer}</span>'
        if timer is not None
        else (
            f'<span class="tb chrono">{IC["chrono"]}Chrono</span><span '
            'class="spacer"></span>'
        )
    )
    extra = ""
    if badge:
        extra = f'<span class="badge">{badge}</span>'
    elif newdot:
        extra = '<span class="dot8"></span>'
    h = '<div class="topbar">' + left + tb("undo", "Annuler", off="undo" in off)
    if aide:
        h += tb("aide", "Aide", "aide" in pressed)
    fourth = (
        tb("kbd", "Clavier", "kbd" in pressed, off="kbd" in off)
        if slot4 == "kbd"
        else tb("pen", "Crayon", "pen" in pressed, off="pen" in off)
    )
    h += (
        tb("salon", "Salon", "salon" in pressed, extra)
        + fourth
        + tb("menu", "Menu", "menu" in pressed)
    )
    return h + "</div>"


def keys(s: str, pencil: bool = False) -> str:
    """Return a row of letter keys."""
    return "".join(f'<span class="k l">{ch}</span>' for ch in s)


def keyboard(pencil: bool = False, low: bool = False) -> str:
    """Return the in-app keyboard; low: 28 px keys (spec 044)."""
    pen = "true" if pencil else "false"
    cls = "kbd" + (" pencil" if pencil else "") + (" low" if low else "")
    return (
        f'<div class="{cls}"><div '
        f'class="krow">{keys("AZERTYUIOP")}'
        "</div>"
        f'<div class="krow">{keys("QSDFGHJKLM")}</div>'
        f'<div class="krow"><span class="k wide pen" aria-pressed="{pen}">{IC["pen"]}<'
        f'/span>{keys("WXCVBN")}'
        f'<span class="k">{IC["swap"]}</span><span class="k wide">{IC["del"]}</span></'
        "div></div>"
    )


def cluebar(
    text: str,
    glyph: str = "→",
    pressed: bool = False,
    width: int | None = None,
    empty: bool = False,
    status: str = "",
) -> str:
    """Return the clue bar; status: the completion status in its row, if any."""
    st = f' style="width:{width}px"' if width else ""
    if empty:
        return (
            f'<div class="cluebar"{st}><span class="cb">{IC["chev_l"]}</span>'
            '<div class="txt">Touchez une case ou une définition.</div><span '
            f'class="cb pin off">{IC["smile"]}</span>'
            f'<span class="cb pin off">{IC["flag"]}</span><span '
            f'class="cb">{IC["chev_r"]}<'
            "/span></div>"
        )
    return (
        f'<div class="cluebar"{st}><span class="cb">{IC["chev_l"]}</span><div '
        f'class="txt">{esc(text)}<i>{glyph}</i></div>{status}'
        f'<span class="cb pin">{IC["smile"]}</span><span class="cb '
        f'pin" aria-pressed="{str(pressed).lower()}">{IC["flag"]}</span>'
        f'<span class="cb">{IC["chev_r"]}</span></div>'
    )


def netband() -> str:
    """Return the connection band."""
    return (
        '<div class="netband"><span class="d"></span><span>Connexion '
        "perdue. Vous pouvez continuer : "
        "vos lettres seront envoyées au retour du réseau.</span></div>"
    )


def status_band(text: str) -> str:
    """Return the status band: a final status after the room showed (spec 043)."""
    return f'<div class="netband">{esc(text)}</div>'


def row_status() -> str:
    """Return the full-but-wrong status in the clue bar's row (spec 043).

    A solved page has no row status since spec 044 (no in-app keyboard, so the
    status is the band).
    """
    return '<span class="rowstat">Grille complète, mais pas encore juste.</span>'


def band_done(width: int | None = None) -> str:
    """Return the finished-grid band."""
    st = f' style="width:{width}px"' if width else ""
    return (
        f'<div class="gstat"{st}>✓ Grille terminée, bravo !<span class="btn '
        'primary">Voir le bilan</span></div>'
    )


def band_notyet(width: int | None = None) -> str:
    """Return the full-but-wrong band."""
    st = f' style="width:{width}px"' if width else ""
    return (
        f'<div class="gstat notyet"{st}>Grille complète, mais pas encore juste.</div>'
    )


def note(text: str) -> str:
    """Return a 3-second note."""
    return f'<div class="toast">{text}</div>'


def note_under_vote(banner: str, text: str) -> str:
    """Return the vote banner with a 3-second note 8 px under it (spec 043)."""
    return f'<div class="vstack">{banner}{note(text)}</div>'


def legend(
    players: list[int], names_of: list[str] | None = None, over: bool = False
) -> str:
    """Return the Auteurs legend; it wraps onto more lines (spec 045).

    over: True lays it over the bottom of the grid's viewport, where its room
    would leave the grid under 100 px (cells.md, « Auteurs mode »).
    """
    who = names_of or FOUR
    names = " ".join(
        (f'<b style="color:var(--player-ink-{p})">{who[p]}' "</b>") for p in players
    )
    cls = "legend over" if over else "legend"
    return f'<div class="{cls}">Auteurs : {names}</div>'


def phone_room(
    timer: str | None = "4:12",
    pressed: set | None = None,
    badge: str | None = "2",
    newdot: bool = False,
    aide: bool = True,
    net: bool = False,
    grid_opts: dict | None = None,
    stage_extra: str = "",
    clue: tuple | None = None,
    flag_pressed: bool = False,
    clue_empty: bool = False,
    band: str | None = None,
    kbd: str | None = "on",
    layer: str = "",
    authors: bool = False,
    stage_html: str | None = None,
    size: tuple[int, int] = (360, 720),
    legend_names: list[str] | None = None,
    legend_lines: int = 1,
    legend_over: bool = False,
    off: set | None = None,
    slot4: str = "kbd",
    band_lines: int = 1,
    final_status: str | None = None,
    row_state: bool = False,
) -> str:
    """Return a phone room, 360 x 720 by default (sheet layout).

    final_status: the text of the status band under the top bar (spec 043);
    row_state: True shows the full-but-wrong status in the clue bar's row;
    legend_over: True lays the Auteurs legend over the grid's bottom and gives
    it no room (cells.md, « Auteurs mode »).
    """
    width, height = size
    low = height <= 500
    if pressed is None:
        pressed = {"kbd"} if kbd else set()
    grid_opts = grid_opts or {}
    kb_h = (110 if low else 158) if kbd else 0
    band_h = {"done": 46, "notyet": 35}.get(band or "", 0) + 19 * (band_lines - 1)
    net_h = (52 if net else 0) + (35 if final_status else 0)
    stage_h = height - 2 - 54 - 34 - kb_h - band_h - net_h
    leg_h = (38 + 15 * (legend_lines - 1)) if authors and not legend_over else 0
    s = floor(min((width - 2 - 16 - 1) / 5, (stage_h - 16 - leg_h - 1) / 5))
    h = phone_top(timer, pressed, badge, newdot, aide, off, slot4)
    if net:
        h += netband()
    if final_status:
        h += status_band(final_status)
    if stage_html is None:
        g = grid(fx_rows(s, authors=authors, **grid_opts), s)
        if authors and legend_names:
            leg = legend(list(range(len(legend_names))), legend_names, legend_over)
        else:
            leg = legend([0, 1, 2, 3], over=legend_over) if authors else ""
        if legend_over:
            inner = f'<div class="gwrap">{g}</div>{leg}'
        else:
            inner = f'<div class="gwrap">{g}{leg}</div>'
    else:
        inner = stage_html
    h += f'<div class="stage">{inner}{stage_extra}</div>'
    if stage_html is None or clue is not None:
        if clue_empty:
            h += cluebar("", empty=True)
        else:
            word = grid_opts.get("word", 5)
            text, glyph = clue if clue else (FX_CLUE_TEXT[word], FX_DIR[word])
            status = row_status() if row_state else ""
            h += cluebar(text, glyph, flag_pressed, status=status)
    if band == "done":
        h += band_done()
    elif band == "notyet":
        h += band_notyet()
    if kbd:
        h += keyboard(kbd == "pencil", low)
    h += layer
    st = f' style="width:{width}px;height:{height}px"' if size != (360, 720) else ""
    return f'<div class="phone"{st}>{h}</div>'


# ---------- Salon (sheet or column) ----------
STREAM = [
    ("evt", "→ Bruno a rejoint le salon", ""),
    ("msg", 0, "Quelqu'un a une idée pour « Fin de prière » ?"),
    ("evt", FLAG_ICO + " Dédé bloque sur « Flaire »", ""),
    ("evt", "▲ Dédé a révélé une lettre", "rev"),
    ("msg", 1, "AMEN, je pense 👍"),
    ("evt", "✓ Ana a vérifié le mot", "ok"),
    ("evt", "Ana a verrouillé le salon", ""),
    ("msg", 2, "Je prends le bas à gauche."),
]


def stream(access: bool = False, items: list | None = None) -> str:
    """Return the Discussion stream."""
    out = '<div class="stream">'
    for kind, a, b in items or STREAM:
        if kind == "evt":
            cls = {"rev": " rev", "ok": " ok"}.get(b, "")
            out += f'<div class="evt{cls}">{a}</div>'
        else:
            name = ["Ana", "Bruno", "Céline", "Dédé"][a]
            out += (
                f'<div class="msg"><span class="who">{dot(a, access)}{name}'
                f"</span><span>{esc(b)}"
                "</span></div>"
            )
    return out + "</div>"


def compose(muted: bool = False, wait: bool = False, typed: str = "") -> str:
    """Return the message box with its chat note."""
    if muted:
        box = (
            '<span class="msgbox off">Écrire au salon</span><span class="pill '
            'off">Envoyer</span>'
        )
        line = '<div class="chatnote">L\'hôte a coupé votre discussion.</div>'
    else:
        txt = (
            f'<span style="color:var(--nock-ink)">{esc(typed)}</span>'
            if typed
            else "Écrire au salon"
        )
        pill = "pill" if typed and not wait else "pill off"
        box = f'<span class="msgbox">{txt}</span><span class="{pill}">Envoyer</span>'
        line = '<div class="chatnote">Patientez avant d\'envoyer.</div>' if wait else ""
    return f'<div class="compose"><div class="crow">{box}</div>{line}</div>'


PLAYERS = [
    # (index, name, you, host, state, clue)
    (0, "Ana", True, True, "actif", "Sans contenu"),
    (1, "Bruno", False, False, "actif", "Alourdit le ballon"),
    (2, "Céline", False, False, "inactif", "Artiste muet"),
    (3, "Dédé", False, False, "actif", "Flaire"),
]


def players(
    host: bool = True,
    access: bool = False,
    copied: bool = True,
    muted_bruno: bool = False,
    gone: bool = False,
) -> str:
    """Return the Joueurs tab: rows, host tools, invitation."""
    out = '<div class="players">'
    rows = list(PLAYERS)
    if gone:
        rows.append((4, "Éloïse", False, False, "déconnecté", "Fin de prière"))
    for p, name, you, is_host, state, clue in rows:
        cls = {"inactif": " idle", "déconnecté": " gone"}.get(state, "")
        nm = f'<b>{name}</b> <span class="you">(vous)</span>' if you else name
        tag = ' <span class="tag">hôte</span>' if is_host else ""
        btns = ""
        if host and not you:
            mute = "Rétablir" if (muted_bruno and p == 1) else "Couper"
            btns = (
                '<span class="hostbtns"><span class="btn '
                f'secondary small">{mute}</span><span '
                'class="btn secondary small">Retirer</span></span>'
            )
        out += (
            f'<div class="prow{cls}">{dot(p, access)}<span '
            f'class="pname">{nm}{tag}</span>{btns}'
            "</div>"
            f'<div class="pst2">{state} · {clue}</div>'
        )
    out += '<h4 class="dh">Lien d\'invitation</h4>'
    out += f'<span class="urlbox">{URL_ROOM}</span>'
    out += '<div class="sharerow"><span class="btn primary">Copier le lien</span>'
    if copied:
        out += '<span class="okline">Lien copié</span>'
    return out + "</div></div>"


def salon(
    tab: str = "stream",
    host: bool = True,
    access: bool = False,
    prog: tuple = ("5 / 8 mots", 62),
    muted: bool = False,
    wait: bool = False,
    typed: str = "",
    items: list | None = None,
    count: int = 4,
    copied: bool = True,
    muted_bruno: bool = False,
) -> str:
    """Return the Salon's content (progress, tabs, the chosen tab)."""
    sel_s = "true" if tab == "stream" else "false"
    sel_p = "false" if tab == "stream" else "true"
    h = (
        f'<div class="prog"><span>{prog[0]}</span><div class="bar"><i '
        f'style="width:{prog[1]}%"></i></div></div>'
        f'<div class="tabs"><span aria-selected="{sel_s}">Discussion</span><span '
        f'aria-selected="{sel_p}">Joueurs ({count})</span></div>'
    )
    if tab == "stream":
        h += stream(access, items) + compose(muted, wait, typed)
    else:
        h += players(host, access, copied, muted_bruno)
    return h


def salon_sheet(**kw: object) -> str:
    """Return the Salon as a phone bottom sheet over its scrim."""
    return (
        '<div class="scrim"></div><div class="sheet"><div '
        f'class="grab"></div>{salon(**kw)}'
        "</div>"
    )


# ---------- menus ----------
def aide_menu(
    pencil: bool = False, letters: int = 4, words: int = 1, none: bool = False
) -> str:
    """Return the Aide menu's items (room.md, « Aide menu »)."""
    h = ""
    if pencil:
        h += (
            '<span class="mi strong">Confirmer '
            "la lettre au crayon <em>✎</em></span><hr>"
        )
    if none:
        return h or '<p class="aide-empty">L\'aide est désactivée dans ce salon.</p>'
    h += (
        '<h4>Vérifier</h4><span class="mi">La lettre</span><span '
        'class="mi">Le mot</span><span class="mi">La grille</span><hr><h4>Révéler</h4'
        ">"
    )
    if letters > 0:
        h += (
            f'<span class="mi">La lettre <em>{letters} '
            f'restante{"s" if letters > 1 else ""}'
            "</em></span>"
        )
    else:
        h += '<span class="mi off">La lettre <em>Plus de lettre</em></span>'
    if words > 0:
        h += (
            f'<span class="mi">Le mot <em>{words} '
            f'restant{"s" if words > 1 else ""}</em></'
            "span>"
        )
    else:
        h += '<span class="mi off">Le mot <em>Plus de mot</em></span>'
    return h


def room_menu(
    host: bool = True,
    authors: bool = False,
    tint: bool = True,
    access: bool = False,
    timer_hidden: bool = False,
    hover: str = "",
) -> str:
    """Return the Menu's items."""

    def mi(label: str, detail: str = "") -> str:
        cls = " hover" if label == hover else ""
        d = f" <em>{detail}</em>" if detail else ""
        return f'<span class="mi{cls}">{label}{d}</span>'

    h = mi("Auteurs", "activé" if authors else "désactivé")
    h += mi("Mots des autres", "teintés" if tint else "sans teinte")
    h += mi("Accessibilité", "activée" if access else "désactivée")
    h += mi("Inviter", "lien")
    if host:
        h += mi("Réglages de l'hôte")
    h += mi("Compte") + "<hr>"
    h += mi("Afficher le chrono" if timer_hidden else "Masquer le chrono")
    h += mi("Retour aux grilles")
    return h


def phone_pop(inner: str, left: int | None = None, right: int | None = None) -> str:
    """Return a phone popover over its scrim."""
    pos = f"left:{left}px" if left is not None else f"right:{right}px"
    return f'<div class="scrim"></div><div class="pop" style="{pos}">{inner}</div>'


# ---------- dialogs and sheets ----------
def recap_body(phone: bool = False, departed: bool = False) -> str:
    """Return the recap's content; departed adds a player who left (no dot)."""
    rows = [
        (0, "Ana", True, 7, 3),
        (1, "Bruno", False, 6, 2),
        (2, "Céline", False, 3, 1),
        (3, "Dédé", False, 2, 1),
    ]
    if departed:
        rows.append((-1, "Éloïse", False, 2, 0))
    plist = "".join(
        f'<li>{dot(p) if p >= 0 else NODOT}<span class="n">{n}</span>'
        f'{YOU if y else ""}'
        f'<span class="v">{a} lettres · {w} mots complétés</span></li>'
        for p, n, y, a, w in rows
    )
    return (
        '<h3>Bilan de la partie</h3><div class="bigtime">Temps : 12:34</div>'
        '<div class="rstats"><span>Vérifications : 2</span><span>Révélations '
        ": 1 lettres et 0 mots</span>"
        "<span>Lettres révélées : 1</span></div>"
        f'<h4 class="dh">Qui a fait quoi</h4><ul class="plist">{plist}</ul>'
        '<h4 class="dh">Lien à partager</h4><div class="sharebox"><span '
        f'class="urlbox">{URL_RECAP}</span>'
        '<span class="btn secondary" style="padding:8px 12px">Copier '
        'le lien</span></div><span class="okline" style="margin-top:-6px">Lien '
        "copié</span>"
        '<div class="end"><span class="btn primary">Fermer</span></div>'
    )


def phone_dialog_sheet(inner: str, top: int = 54, recap: bool = False) -> str:
    """Return a room sheet from under the top bar, or the recap over all."""
    cls = "ov bottom recap" if recap else "ov bottom"
    st = "" if recap else f' style="top:{top}px"'
    return f'<div class="{cls}"{st}><div class="dialog">{inner}</div></div>'


def desk_dialog(inner: str, recap: bool = False) -> str:
    """Return a computer dialog over its scrim."""
    cls = "ov recap" if recap else "ov"
    return f'<div class="{cls}"><div class="dialog">{inner}</div></div>'


def host_settings(mode: str = "libre") -> str:
    """Return the host settings' content."""
    seg = "".join(
        f'<span class="{"on" if m == mode else ""}">{m}</span>'
        for m in ("libre", "par vote", "désactivée")
    )
    return (
        "<h3>Réglages de l'hôte</h3>"
        '<div class="switchrow">Verrouiller le salon<span class="tog on"></span></div>'
        f'<div class="field">Aide<span class="seg">{seg}</span></div>'
        '<div style="display:flex;gap:16px"><div class="field">Lettres '
        'à révéler<span class="input num">4</span></div>'
        '<div class="field">Mots à révéler<span class="input num">1</span></div></div>'
        '<div class="end"><span class="btn primary">Enregistrer</span></div>'
    )


def account_out(state: str = "sent", in_room: bool = True) -> str:
    """Return the signed-out account sheet's content."""
    intro = (
        (
            "Recevez par e-mail un lien de connexion. Vous gardez votre "
            "place, votre couleur et vos lettres dans ce salon."
        )
        if in_room
        else "Recevez par e-mail un lien pour vous connecter."
    )
    err = state == "error"
    address = "ana@exemple" if err else "ana@exemple.fr"
    inp = f'<span class="input{" err" if err else ""}">{address}' "</span>"
    h = (
        "<h3>Retrouver vos parties sur tous vos appareils</h3><p "
        f'class="intro">{intro}</p>'
        f'<div class="field">Adresse e-mail{inp}</div>'
    )
    if err:
        h += '<span class="errtxt">Adresse e-mail non valide.</span>'
    h += '<div><span class="btn primary">Recevoir le lien</span></div>'
    if state == "sent":
        h += (
            '<span class="okline">Lien envoyé à ana@exemple.fr. Il est '
            "valable 30 minutes.</span>"
        )
    h += '<div class="end"><span class="btn secondary">Fermer</span></div>'
    return h


def account_in() -> str:
    """Return the signed-in account sheet's content."""
    return (
        "<h3>Votre compte</h3><p>Connecté avec ana@exemple.fr</p>"
        '<span class="tlink">Gérer mon compte</span><div class="end"><span '
        'class="btn secondary">Fermer</span></div>'
    )


def vote_banner(
    state: str = "ask",
    question: str = "Bruno propose de révéler une lettre.",
    secs: str = "18 s",
    pct: int = 90,
) -> str:
    """Return the vote banner in one of its states."""
    if state == "ask":
        row = (
            '<span class="btn primary">Oui</span><span '
            'class="btn secondary">Non</span><s'
            f'pan class="t">{secs}</span>'
        )
    elif state == "snap":
        row = (
            '<span class="btn primary">Oui</span><span class="btn secondary">Non</span>'
        )
        return (
            f'<div class="vote"><div class="q">{question}</div>'
            f'<div class="row">{row}</div></div>'
        )
    elif state == "cast":
        row = (
            '<span class="vmuted">Vote enregistré. En attente des autres '
            f'joueurs…</span><span class="t">{secs}</span>'
        )
    else:
        row = (
            '<span class="vmuted">En attente des autres joueurs…</span><span '
            f'class="t">{secs}</span>'
        )
    return (
        f'<div class="vote"><div class="q">{question}</div><div class="row">{row}</div'
        f'><div class="bar"><i style="width:{pct}%"></i></div></div>'
    )


def picker() -> str:
    """Return the reaction picker."""
    return (
        '<div class="picker"><span>👍</span><span>👏</span>'
        "<span>😂</span><span>😮</span>"
        "<span>🤔</span></div>"
    )


# ---------- computer room ----------
def dbtn(
    icon: str | None,
    label: str,
    pressed: bool = False,
    extra: str = "",
    off: bool = False,
) -> str:
    """Return a computer top-bar button, muted when disabled (spec 043)."""
    ic = IC[icon] if icon else ""
    cls = "dbtn off" if off else "dbtn"
    pressed = pressed and not off
    return (
        f'<span class="{cls}" aria-pressed="{str(pressed).lower()}">{ic}{label}{extra}<'
        "/span>"
    )


def desk_top(
    timer: str | None = "12:34",
    pressed: set | None = None,
    badge: str | None = None,
    newdot: bool = False,
    aide: bool = True,
    kbd: bool = False,
) -> str:
    """Return the computer top bar of the room: no grid name (room.md)."""
    pressed = pressed if pressed is not None else {"salon"}
    extra = (
        f'<span class="badge">{badge}</span>'
        if badge
        else ('<span class="dot8 d"></span>' if newdot else "")
    )
    t = (
        f'<span class="dtimer">{timer}</span>'
        if timer is not None
        else dbtn("chrono", "Chrono")
    )
    h = f'<div class="dtop">{brand()}<span class="spacer"></span>{t}'
    h += dbtn("undo", "Annuler", off="undo" in pressed) + dbtn(
        "pen", "Crayon", "pen" in pressed, off="pen-off" in pressed
    )
    if aide:
        h += dbtn("aide", "Aide ▾", "aide" in pressed)
    h += dbtn("salon", "Salon", "salon" in pressed, extra)
    if kbd:
        h += dbtn("kbd", "Clavier", "kbd" in pressed)
    h += dbtn("menu", "Menu", "menu" in pressed)
    return h + "</div>"


def desk_room(
    column: str | None = "stream",
    timer: str | None = "12:34",
    pressed: set | None = None,
    badge: str | None = None,
    newdot: bool = False,
    aide: bool = True,
    net: bool = False,
    solved: bool = False,
    notyet: bool = False,
    layer: str = "",
    main_extra: str = "",
    authors: bool = False,
    col_kw: dict | None = None,
    kbd: bool = False,
    clue: tuple = ("Fin de journée", "→"),
    final_status: str | None = None,
) -> str:
    """A computer room, 1280 x 800 (room.md, column layout).

    final_status: the text of the status band under the top bar (spec 043).
    """
    col_w = 340 if column else 0
    band_h = 46 if solved else (35 if notyet else 0)
    net_h = (36 if net else 0) + (35 if final_status else 0)
    kb_h = 168 if kbd else 0
    leg = 38 if authors else 0
    s = floor(
        min(
            (800 - 56 - 34 - band_h - net_h - kb_h - leg - 24 - 1) / BH,
            (1280 - col_w - 24 - 1 - 40) / BW,
        )
    )
    gw = s * BW + 1
    if pressed is None:
        pressed = {"salon"} if column else set()
        if kbd:
            pressed.add("kbd")
    if solved:
        pressed = set(pressed) | {"undo", "pen-off"}
    h = desk_top(timer, pressed, badge, newdot, aide, kbd)
    if net:
        h += netband()
    if final_status:
        h += status_band(final_status)
    g = grid(big_rows(s, solved=solved, authors=authors), s)
    if authors:
        g = f'<div class="gwrap">{g}{legend([0, 1, 2, 3])}</div>'
    main = f'<div class="dmain"><div class="dstage">{g}{main_extra}</div>'
    main += (
        cluebar(clue[0], clue[1], width=gw)
        if not solved
        else cluebar("Fin de journée", "→", width=gw)
    )
    if solved:
        main += band_done(gw)
    elif notyet:
        main += band_notyet(gw)
    if kbd:
        main += keyboard()
    main += "</div>"
    col = ""
    if column:
        kw = {"prog": ("31 / 54 mots", 57)}
        kw.update(col_kw or {})
        col = f'<aside class="dcol">{salon(tab=column, **kw)}</aside>'
    return f'<div class="desk">{h}<div class="dbody">{main}{col}</div>{layer}</div>'


def low_column_room(size: tuple[int, int] = (740, 360), touch: bool = True) -> str:
    """Return the column layout on a window at most 500 px high (spec 044 D8).

    The phone top bar, then the play area (12 px padding) and the 340 px Salon
    column, open by default. The clue bar is as wide as the grid but never
    narrower than the smaller of 320 px and the play area (spec 043).

    Args:
        size: The window's width and height.
        touch: A touch screen with the keyboard hidden (« Clavier » in the
            fourth slot), else a desktop window (« Crayon »).
    """
    width, height = size
    col_w = 340
    play_w = width - 2 - col_w - 1 - 24
    s = floor(min((play_w - 1) / 5, (height - 2 - 54 - 34 - 24 - 1) / 5))
    bar_w = max(s * 5 + 1, min(320, play_w))
    top = phone_top(pressed={"salon"}, slot4="kbd" if touch else "pen")
    bar = cluebar(FX_CLUE_TEXT[5], FX_DIR[5], width=bar_w)
    main = (
        f'<div class="dmain"><div class="dstage">{grid(fx_rows(s), s)}</div>'
        f"{bar}</div>"
    )
    col = f'<aside class="dcol">{salon()}</aside>'
    return (
        f'<div class="phone" style="width:{width}px;height:{height}px">{top}'
        f'<div class="dbody">{main}{col}</div></div>'
    )


def desk_pop(
    inner: str, left: int | None = None, right: int | None = None, top: int = 50
) -> str:
    """Return a computer popover."""
    pos = f"left:{left}px" if left is not None else f"right:{right}px"
    return f'<div class="pop" style="{pos};top:{top}px">{inner}</div>'


# ---------- plain pages (catalogue, entry, account, share, ops) ----------
def phone_page(
    body: str,
    right: str = "",
    layer: str = "",
    page: bool = True,
    height: int | None = 720,
) -> str:
    """Return a plain phone page (brand bar, page grey)."""
    st = f' style="height:{height}px"' if height else ' style="height:auto"'
    bar = (
        f'<div class="topbar brandbar">{brand()}<span class="right">{right}</span></di'
        "v>"
    )
    cls = "screen" if page else "screen white"
    return f'<div class="phone"{st}>{bar}<div class="{cls}">{body}</div>{layer}</div>'


def desk_page(
    body: str,
    right: str = "",
    layer: str = "",
    page: bool = True,
    size: tuple[int, int] = (1280, 800),
    narrow: bool = False,
) -> str:
    """Return a plain page at a computer or tablet size.

    Args:
        body: The page column's content.
        right: The top bar's right side.
        layer: An overlay over the page.
        page: The page grey (else white).
        size: The frame's width and height.
        narrow: The narrow form (54 px bar, phone padding), spec 046.
    """
    if narrow:
        bar = (
            f'<div class="topbar brandbar">{brand()}<span '
            f'class="right">{right}</span></div>'
        )
        st = f' style="width:{size[0]}px;height:{size[1]}px"'
        return (
            f'<div class="desk"{st}>{bar}<div class="dscreen narrow">{body}</div>'
            f"{layer}</div>"
        )
    bar = f'<div class="dtop">{brand()}<span class="spacer"></span>{right}</div>'
    cls = "dscreen" if page else "dscreen white"
    st = f' style="width:{size[0]}px;height:{size[1]}px"' if size != (1280, 800) else ""
    return f'<div class="desk"{st}>{bar}<div class="{cls}">{body}</div>{layer}</div>'
