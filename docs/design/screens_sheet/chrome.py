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
YOU = ' <span class="you">(vous)</span>'
URL_ROOM = "https://nock.fr/r/K7QM2X"
URL_RECAP = "https://nock.fr/recap/k7Qm2xTa9LpR4vWd"


def brand() -> str:
    """Return the Nock mark and name."""
    return f'<span class="brand">{NOCK}Nock</span>'


# ---------- phone room ----------
def tb(icon: str, label: str, pressed: bool = False, extra: str = "") -> str:
    """Return a phone top-bar button."""
    return (
        f'<span class="tb" aria-pressed="{str(pressed).lower()}"'
        f">{IC[icon]}{label}{extra}"
        "</span>"
    )


def phone_top(
    timer: str | None = "4:12",
    pressed: set | None = None,
    badge: str | None = None,
    newdot: bool = False,
    aide: bool = True,
) -> str:
    """Return the phone top bar of the room."""
    pressed = pressed or set()
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
    h = '<div class="topbar">' + left + tb("undo", "Annuler")
    if aide:
        h += tb("aide", "Aide", "aide" in pressed)
    h += (
        tb("salon", "Salon", "salon" in pressed, extra)
        + tb("kbd", "Clavier", "kbd" in pressed)
        + tb("menu", "Menu", "menu" in pressed)
    )
    return h + "</div>"


def keys(s: str, pencil: bool = False) -> str:
    """Return a row of letter keys."""
    return "".join(f'<span class="k l">{ch}</span>' for ch in s)


def keyboard(pencil: bool = False) -> str:
    """Return the in-app keyboard."""
    pen = "true" if pencil else "false"
    return (
        f'<div class="kbd{" pencil" if pencil else ""}"><div '
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
) -> str:
    """Return the clue bar."""
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
        f'class="txt">{esc(text)}<i>{glyph}</i></div>'
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


def legend(players: list[int]) -> str:
    """Return the Auteurs legend."""
    names = " ".join(
        (f'<b style="color:var(--player-ink-{p})">{FOUR[p]}' "</b>") for p in players
    )
    return f'<div class="legend">Auteurs : {names}</div>'


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
) -> str:
    """A phone room, 360 x 720 (_design.md section 8, sheet layout)."""
    if pressed is None:
        pressed = {"kbd"} if kbd else set()
    grid_opts = grid_opts or {}
    kb_h = 158 if kbd else 0
    band_h = {"done": 46, "notyet": 35}.get(band or "", 0)
    net_h = 52 if net else 0
    stage_h = 720 - 2 - 54 - 34 - kb_h - band_h - net_h
    leg_h = 38 if authors else 0
    s = floor(min((360 - 2 - 16 - 1) / 5, (stage_h - 16 - leg_h - 1) / 5))
    h = phone_top(timer, pressed, badge, newdot, aide)
    if net:
        h += netband()
    if stage_html is None:
        g = grid(fx_rows(s, authors=authors, **grid_opts), s)
        inner = f'<div class="gwrap">{g}{legend([0, 1, 2, 3]) if authors else ""}</div>'
    else:
        inner = stage_html
    h += f'<div class="stage">{inner}{stage_extra}</div>'
    if stage_html is None or clue is not None:
        if clue_empty:
            h += cluebar("", empty=True)
        else:
            word = grid_opts.get("word", 5)
            text, glyph = clue if clue else (FX_CLUE_TEXT[word], FX_DIR[word])
            h += cluebar(text, glyph, flag_pressed)
    if band == "done":
        h += band_done()
    elif band == "notyet":
        h += band_notyet()
    if kbd:
        h += keyboard(kbd == "pencil")
    h += layer
    return f'<div class="phone">{h}</div>'


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
        box = f'<span class="msgbox">{txt}</span><span class="pill">Envoyer</span>'
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
    """Return the Aide menu's items (_design.md section 8)."""
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
def recap_body(phone: bool = False) -> str:
    """Return the recap's content."""
    rows = [
        (0, "Ana", True, 7, 3),
        (1, "Bruno", False, 6, 2),
        (2, "Céline", False, 3, 1),
        (3, "Dédé", False, 2, 1),
    ]
    plist = "".join(
        f'<li>{dot(p)}<span class="n">{n}</span>{YOU if y else ""}'
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
def dbtn(icon: str | None, label: str, pressed: bool = False, extra: str = "") -> str:
    """Return a computer top-bar button."""
    ic = IC[icon] if icon else ""
    return (
        f'<span class="dbtn" aria-pressed="{str(pressed).lower()}">{ic}{label}{extra}<'
        "/span>"
    )


def desk_top(
    timer: str | None = "12:34",
    pressed: set | None = None,
    badge: str | None = None,
    newdot: bool = False,
    aide: bool = True,
    kbd: bool = False,
    gname: str = "Grille n° 12 · Force 3",
) -> str:
    """Return the computer top bar of the room."""
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
    h = f'<div class="dtop">{brand()}<span class="gname">{gname}</span>{t}'
    h += dbtn("undo", "Annuler") + dbtn("pen", "Crayon", "pen" in pressed)
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
) -> str:
    """A computer room, 1280 x 800 (_design.md section 8, column layout)."""
    col_w = 340 if column else 0
    band_h = 46 if solved else (35 if notyet else 0)
    net_h = 36 if net else 0
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
    h = desk_top(timer, pressed, badge, newdot, aide, kbd)
    if net:
        h += netband()
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
    body: str, right: str = "", layer: str = "", page: bool = True, extra_top: str = ""
) -> str:
    """Return a plain computer page (brand bar, centred column)."""
    bar = (
        f'<div class="dtop">{brand()}<span class="gname">{extra_top}</span>{right}</di'
        "v>"
    )
    cls = "dscreen" if page else "dscreen white"
    return f'<div class="desk">{bar}<div class="{cls}">{body}</div>{layer}</div>'
