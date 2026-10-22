"""Tests of spec 041, AC-18 to AC-20: the icon module, and the colour scans of the
built CSS and of the client sources.

They read files with Python only. The built CSS is the one of `web/dist`, which
the gate builds before pytest; without `web/dist/index.html` the test fails with
spec 040's message. The scans follow "Colour scans" of the spec; the samples of
AC-19 and AC-20 check the scan's checker itself. The shared setup is in
`tests/spec041_harness.py`.

Choices where the spec leaves room:

- AC-18 counts the strings "inside quotes" (single, double or backtick quotes)
  in the module's code, comments removed, so a comment that repeats a value (as
  the `NOCK_MARK_POINTS` comment of "Public interface" does) is not counted. The
  numbers of a rectangle or a circle are looked for inside one object literal,
  with any spaces around the colon and the comma.
- AC-19: "declares each custom property ... exactly once" covers the 21 colour
  tokens, the 9 translucent tokens and the 16 player colours and inks, the
  three tables of colours; the font tokens hold no colour.
- AC-20, markup: the attributes that may hold no named colour are those of the
  spec, and Svelte's `style:<property>` directives, which set a style as the
  `style` attribute does. The named colours are looked for in the attribute's
  value, quoted or between braces.
- AC-20, sample `/* #1B2F55 */`: checked as a `.css` file and as a `.ts` file.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from spec041_harness import (
    COLOUR_TOKENS,
    ICONS_PATH,
    TRANSLUCENT_TOKENS,
    WEB_DIST_ASSETS_DIR,
    player_colour_token,
    player_ink_token,
    remove_css_comments,
    remove_script_comments,
    require_build,
    source_files,
    split_svelte,
)

# ---- Colour literals ("Colour scans") ---------------------------------------------

# The 148 named colours of CSS Color Level 4.
NAMED_COLOURS = (
    "aliceblue",
    "antiquewhite",
    "aqua",
    "aquamarine",
    "azure",
    "beige",
    "bisque",
    "black",
    "blanchedalmond",
    "blue",
    "blueviolet",
    "brown",
    "burlywood",
    "cadetblue",
    "chartreuse",
    "chocolate",
    "coral",
    "cornflowerblue",
    "cornsilk",
    "crimson",
    "cyan",
    "darkblue",
    "darkcyan",
    "darkgoldenrod",
    "darkgray",
    "darkgreen",
    "darkgrey",
    "darkkhaki",
    "darkmagenta",
    "darkolivegreen",
    "darkorange",
    "darkorchid",
    "darkred",
    "darksalmon",
    "darkseagreen",
    "darkslateblue",
    "darkslategray",
    "darkslategrey",
    "darkturquoise",
    "darkviolet",
    "deeppink",
    "deepskyblue",
    "dimgray",
    "dimgrey",
    "dodgerblue",
    "firebrick",
    "floralwhite",
    "forestgreen",
    "fuchsia",
    "gainsboro",
    "ghostwhite",
    "gold",
    "goldenrod",
    "gray",
    "green",
    "greenyellow",
    "grey",
    "honeydew",
    "hotpink",
    "indianred",
    "indigo",
    "ivory",
    "khaki",
    "lavender",
    "lavenderblush",
    "lawngreen",
    "lemonchiffon",
    "lightblue",
    "lightcoral",
    "lightcyan",
    "lightgoldenrodyellow",
    "lightgray",
    "lightgreen",
    "lightgrey",
    "lightpink",
    "lightsalmon",
    "lightseagreen",
    "lightskyblue",
    "lightslategray",
    "lightslategrey",
    "lightsteelblue",
    "lightyellow",
    "lime",
    "limegreen",
    "linen",
    "magenta",
    "maroon",
    "mediumaquamarine",
    "mediumblue",
    "mediumorchid",
    "mediumpurple",
    "mediumseagreen",
    "mediumslateblue",
    "mediumspringgreen",
    "mediumturquoise",
    "mediumvioletred",
    "midnightblue",
    "mintcream",
    "mistyrose",
    "moccasin",
    "navajowhite",
    "navy",
    "oldlace",
    "olive",
    "olivedrab",
    "orange",
    "orangered",
    "orchid",
    "palegoldenrod",
    "palegreen",
    "paleturquoise",
    "palevioletred",
    "papayawhip",
    "peachpuff",
    "peru",
    "pink",
    "plum",
    "powderblue",
    "purple",
    "rebeccapurple",
    "red",
    "rosybrown",
    "royalblue",
    "saddlebrown",
    "salmon",
    "sandybrown",
    "seagreen",
    "seashell",
    "sienna",
    "silver",
    "skyblue",
    "slateblue",
    "slategray",
    "slategrey",
    "snow",
    "springgreen",
    "steelblue",
    "tan",
    "teal",
    "thistle",
    "tomato",
    "turquoise",
    "violet",
    "wheat",
    "white",
    "whitesmoke",
    "yellow",
    "yellowgreen",
)
# The system colours of CSS Color Level 4.
SYSTEM_COLOURS = (
    "Canvas",
    "CanvasText",
    "LinkText",
    "VisitedText",
    "ActiveText",
    "ButtonFace",
    "ButtonText",
    "ButtonBorder",
    "Field",
    "FieldText",
    "Highlight",
    "HighlightText",
    "SelectedItem",
    "SelectedItemText",
    "Mark",
    "MarkText",
    "GrayText",
    "AccentColor",
    "AccentColorText",
)

# Longest first, so that no name stops the alternation before a longer one.
_COLOUR_NAMES = sorted([*NAMED_COLOURS, *SYSTEM_COLOURS], key=len, reverse=True)
_WORD_EDGE = "A-Za-z0-9_-"
HEX_COLOUR = re.compile(rf"#([0-9A-Fa-f]+)(?![{_WORD_EDGE}])")
HEX_LENGTHS = (3, 4, 6, 8)
TRANSPARENT_HEX = ("0000", "00000000")
COLOUR_FUNCTION = re.compile(
    rf"(?<![{_WORD_EDGE}])(rgba|rgb|hsla|hsl|hwb|oklab|oklch|lab|lch|color)\(",
    re.IGNORECASE,
)
NAMED_COLOUR = re.compile(
    rf"(?<![{_WORD_EDGE}])({'|'.join(_COLOUR_NAMES)})(?![{_WORD_EDGE}])",
    re.IGNORECASE,
)
QUOTED_STRING = re.compile(r""""(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'""")
URL_VALUE = re.compile(r"url\([^)]*\)", re.IGNORECASE)

TOKEN_PREFIXES = ("--nock-", "--player-colour-", "--player-ink-")


def hex_colours(text: str) -> list[str]:
    """The hex colours of a text, `#0000` and `#00000000` left aside."""
    found: list[str] = []
    for match in HEX_COLOUR.finditer(text):
        digits = match.group(1)
        if len(digits) in HEX_LENGTHS and digits not in TRANSPARENT_HEX:
            found.append(match.group(0))
    return found


def colour_functions(text: str) -> list[str]:
    return [match.group(0) for match in COLOUR_FUNCTION.finditer(text)]


def named_colours(text: str) -> list[str]:
    return [match.group(0) for match in NAMED_COLOUR.finditer(text)]


def colour_literals(value: str) -> list[str]:
    """Every colour literal of a CSS value: hex, colour function, named colour."""
    return [*hex_colours(value), *colour_functions(value), *named_colours(value)]


def css_declarations(css: str) -> list[tuple[str, str]]:
    """The declarations of a CSS text whose comments are removed.

    Quoted strings and `url(...)` are removed first. A declaration is a
    `property: value` ended by `;` or `}`; the text before a `{` is a selector or
    an at-rule prelude, and an at-rule ended by `;` is no declaration.
    """
    without_strings = QUOTED_STRING.sub('""', css)
    plain = URL_VALUE.sub("url()", without_strings)
    declarations: list[tuple[str, str]] = []
    segment_start = 0
    for index, character in enumerate(plain):
        if character not in "{};":
            continue
        segment = plain[segment_start:index]
        segment_start = index + 1
        if character == "{" or ":" not in segment:
            continue
        name, value = segment.split(":", 1)
        name = name.strip()
        if name == "" or name.startswith("@"):
            continue
        declarations.append((name, value.strip()))
    return declarations


def is_token_declaration(name: str) -> bool:
    return name.startswith(TOKEN_PREFIXES)


def css_findings(css: str) -> list[str]:
    """The colour literals outside token declarations of a CSS text."""
    findings: list[str] = []
    for name, value in css_declarations(remove_css_comments(css)):
        if is_token_declaration(name):
            continue
        for literal in colour_literals(value):
            findings.append(f"{name}: {value} ({literal})")
    return findings


# ---- AC-18: the icon module holds the design's shapes -----------------------------

ICON_NAMES = (
    "undo",
    "aide",
    "salon",
    "clavier",
    "menu",
    "crayon",
    "swap",
    "effacer",
    "chrono",
    "flag",
    "chevron-left",
    "chevron-right",
    "smile",
)
PATH_STRINGS = (
    "M9 14 4 9l5-5",
    "M4 9h10a6 6 0 0 1 0 12h-3",
    "M9 18h6M10 22h4",
    "M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z",
    "M21 12a8 8 0 0 1-11.6 7.1L4 21l1.9-5.4A8 8 0 1 1 21 12z",
    "M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10",
    "M4 7h16M4 12h16M4 17h16",
    "M4 20h4L19 9l-4-4L4 16v4z",
    "M13.5 6.5l4 4",
    "M4 8h14l-3-3M20 16H6l3 3",
    "M9 5h11v14H9l-6-7 6-7z",
    "M13 9l4 6M17 9l-4 6",
    "M12 10v3.5l2.5 2M9.5 3h5M12 3v3",
    "M6 21V4",
    "M6 4h12l-3 4.5 3 4.5H6z",
    "M15 5l-7 7 7 7",
    "M9 5l7 7-7 7",
    "M8.5 14.5c1.8 2 5.2 2 7 0",
    "M9 9.5h.01M15 9.5h.01",
    "M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z",
)
POINTS_STRINGS = (
    "5,0.4 9.7,9.3 0.3,9.3",
    "5,0.1 9.9,5 5,9.9 0.1,5",
    "5,0.2 6.3,3.6 9.9,3.7 7.1,6 8.1,9.6 5,7.5 1.9,9.6 2.9,6 0.1,3.7 3.7,3.6",
    "3.3,0.4 6.7,0.4 6.7,3.3 9.6,3.3 9.6,6.7 6.7,6.7 6.7,9.6 3.3,9.6 3.3,6.7 "
    "0.4,6.7 0.4,3.3 3.3,3.3",
    "0.6,0.6 9.4,0.6 5.6,5 9.4,9.4 0.6,9.4 4.4,5",
)
NOCK_MARK = "0,0 10,0 10,14 5,10 0,14"
EXPORTS = ("ICONS", "PLAYER_ICONS", "NOCK_MARK_POINTS")
# Each group of numbers that one object literal of the module holds.
NUMBER_GROUPS = {
    "clavier's rectangle": (
        ("x", "2"),
        ("y", "6"),
        ("width", "20"),
        ("height", "12"),
        ("rx", "2"),
    ),
    "chrono's circle": (("cx", "12"), ("cy", "13.5"), ("r", "7.5")),
    "smile's circle": (("cx", "12"), ("cy", "12"), ("r", "9")),
    "Rond": (("cx", "5"), ("cy", "5"), ("r", "4.4")),
    "Carré": (("x", "0.9"), ("y", "0.9"), ("width", "8.2"), ("height", "8.2")),
}
OBJECT_LITERAL = re.compile(r"\{[^{}]*\}")


def icons_code() -> str:
    """The text of `web/src/lib/icons.ts`, comments removed."""
    if not ICONS_PATH.is_file():
        pytest.fail(f"{ICONS_PATH} does not exist")
    return remove_script_comments(ICONS_PATH.read_text(encoding="utf-8"))


def quoted_count(code: str, text: str) -> int:
    """How often `text` appears between a pair of the same quotes."""
    count = 0
    for quote in ("'", '"', "`"):
        count += code.count(f"{quote}{text}{quote}")
    return count


def holds_number(object_text: str, name: str, number: str) -> bool:
    pattern = rf"(?<![\w$.-]){re.escape(name)}\s*:\s*{re.escape(number)}(?![\w.])"
    return re.search(pattern, object_text) is not None


def object_holds_group(code: str, group: tuple[tuple[str, str], ...]) -> bool:
    for match in OBJECT_LITERAL.finditer(code):
        object_text = match.group(0)
        if all(holds_number(object_text, name, number) for name, number in group):
            return True
    return False


def is_key(code: str, name: str) -> bool:
    pattern = rf"""(?<![\w$'"-])(['"]?){re.escape(name)}\1\s*:"""
    return re.search(pattern, code) is not None


@pytest.mark.parametrize("name", EXPORTS)
def test_ac18_icons_module_exports_the_name(name: str) -> None:
    pattern = rf"\bexport\s+const\s+{name}\b"

    assert re.search(pattern, icons_code()) is not None


@pytest.mark.parametrize("path_string", PATH_STRINGS)
def test_ac18_each_path_string_is_quoted_exactly_once(path_string: str) -> None:
    assert quoted_count(icons_code(), path_string) == 1


@pytest.mark.parametrize("points", POINTS_STRINGS)
def test_ac18_each_player_icon_points_string_is_quoted_exactly_once(
    points: str,
) -> None:
    assert quoted_count(icons_code(), points) == 1


def test_ac18_the_nock_mark_points_are_quoted_exactly_once() -> None:
    assert quoted_count(icons_code(), NOCK_MARK) == 1


@pytest.mark.parametrize("group_name", list(NUMBER_GROUPS))
def test_ac18_one_object_holds_the_numbers_of_the_shape(group_name: str) -> None:
    assert object_holds_group(icons_code(), NUMBER_GROUPS[group_name]), group_name


@pytest.mark.parametrize("name", ICON_NAMES)
def test_ac18_each_icon_name_is_a_key(name: str) -> None:
    assert is_key(icons_code(), name)


def test_ac18_the_checks_read_keys_and_object_numbers_as_written() -> None:
    code = (
        "export const ICONS = {\n"
        "  undo: [{ kind: 'path', d: 'M9 14 4 9l5-5' }],\n"
        "  'chevron-left': [{ kind: 'rect', x: 2, y: 6, width: 20, height: 12,"
        " rx: 2 }],\n"
        "}\n"
        "const other = { rx: 2, cx: 12 }\n"
    )

    assert is_key(code, "undo")
    assert is_key(code, "chevron-left")
    assert not is_key(code, "kind-of")
    assert object_holds_group(code, NUMBER_GROUPS["clavier's rectangle"])
    assert not object_holds_group(code, (("x", "2"), ("cx", "12")))
    assert quoted_count(code, "M9 14 4 9l5-5") == 1


# ---- AC-19: the built CSS holds no colour outside the token block -----------------

TOKEN_PROPERTIES = [
    *COLOUR_TOKENS,
    *TRANSLUCENT_TOKENS,
    *[player_colour_token(index) for index in range(8)],
    *[player_ink_token(index) for index in range(8)],
]

BUILT_FLAGGED = [
    "a{color:#1b2f55}",
    "a{color:#FFF}",
    "a{background:rgb(0 0 0/20%)}",
    "a{border-color:White}",
    "a{box-shadow:0 1px 0 hsl(0 0% 0%)}",
    "a{outline-color:Highlight}",
]
BUILT_ACCEPTED = [
    ":root{--nock-navy:#1b2f55}",
    ":root{--player-ink-1:#4b6a2c}",
    "a{color:var(--nock-navy)}",
    "a{background:transparent}",
    "a{border-color:currentColor}",
    "a{background:#0000}",
    "a{background:color-mix(in srgb,var(--player-colour-1) 16%,var(--nock-white))}",
    'a{font-family:"White Rabbit"}',
    "a{background:url(red.svg)}",
    "a{grid-area:sidebar}",
]


def built_css_files() -> list[Path]:
    require_build()
    return sorted(WEB_DIST_ASSETS_DIR.glob("**/*.css"))


def built_declarations() -> list[tuple[str, str]]:
    declarations: list[tuple[str, str]] = []
    for path in built_css_files():
        css = remove_css_comments(path.read_text(encoding="utf-8"))
        declarations.extend(css_declarations(css))
    return declarations


def test_ac19_the_scan_knows_the_148_named_colours_and_19_system_colours() -> None:
    assert len(set(NAMED_COLOURS)) == 148
    assert len(set(SYSTEM_COLOURS)) == 19


@pytest.mark.parametrize("sample", BUILT_FLAGGED)
def test_ac19_the_checker_flags_the_sample(sample: str) -> None:
    assert css_findings(sample) != []


@pytest.mark.parametrize("sample", BUILT_ACCEPTED)
def test_ac19_the_checker_accepts_the_sample(sample: str) -> None:
    assert css_findings(sample) == []


def test_ac19_the_built_css_exists() -> None:
    assert built_css_files() != [], "no .css file under web/dist/assets"


@pytest.mark.parametrize("token", TOKEN_PROPERTIES)
def test_ac19_the_built_css_declares_the_token_exactly_once(token: str) -> None:
    names = [name for name, _ in built_declarations()]

    assert names.count(token) == 1


def test_ac19_the_built_css_holds_no_colour_literal_outside_token_declarations() -> (
    None
):
    findings: list[str] = []
    for path in built_css_files():
        for finding in css_findings(path.read_text(encoding="utf-8")):
            findings.append(f"{path.name}: {finding}")

    assert findings == []


# ---- AC-20: the client sources hold no colour outside the token block -------------

COLOUR_ATTRIBUTE = re.compile(
    r"(?<![\w:-])(style(?::[\w-]+)?|fill|stroke|color|stop-color|flood-color"
    r"|lighting-color)\s*=\s*(\"[^\"]*\"|'[^']*'|\{[^}]*\})",
)


def script_findings(code: str) -> list[str]:
    """The hex colours and colour functions of a script or of markup."""
    return [*hex_colours(code), *colour_functions(code)]


def attribute_findings(markup: str) -> list[str]:
    """The named colours in the colour attributes of markup."""
    findings: list[str] = []
    for match in COLOUR_ATTRIBUTE.finditer(markup):
        for name in named_colours(match.group(2)):
            findings.append(f"{match.group(0)} ({name})")
    return findings


def source_findings(text: str, suffix: str) -> list[str]:
    """What the source scan of "Colour scans" finds in one file.

    Args:
        text: The file's text.
        suffix: `.css`, `.ts` or `.svelte`.

    Returns:
        A description of each colour literal found, empty when there is none.
    """
    if suffix == ".css":
        return css_findings(text)
    if suffix == ".ts":
        return script_findings(remove_script_comments(text))
    parts = split_svelte(text)
    findings: list[str] = []
    for script in parts.scripts:
        findings.extend(script_findings(script))
    for style in parts.styles:
        findings.extend(css_findings(style))
    findings.extend(script_findings(parts.markup))
    findings.extend(attribute_findings(parts.markup))
    return findings


SOURCE_FLAGGED = [
    (".svelte", "<style>a{color:#1b2f55}</style>"),
    (".svelte", '<rect fill="#1B2F55"/>'),
    (".svelte", '<rect fill="white"/>'),
    (".svelte", '<div style="color: rgb(0 0 0)">'),
    (".ts", "const c = '#14181f'"),
]
SOURCE_ACCEPTED = [
    (".svelte", '<rect fill="currentColor"/>'),
    (".svelte", '<rect fill="none"/>'),
    (".css", "/* #1B2F55 */"),
    (".ts", "/* #1B2F55 */"),
    (".ts", "// #1B2F55"),
    (".ts", "const id = '#cell-1-2'"),
    (".svelte", "<p>white</p>"),
]


@pytest.mark.parametrize(("suffix", "sample"), SOURCE_FLAGGED)
def test_ac20_the_checker_flags_the_sample(suffix: str, sample: str) -> None:
    assert source_findings(sample, suffix) != []


@pytest.mark.parametrize(("suffix", "sample"), SOURCE_ACCEPTED)
def test_ac20_the_checker_accepts_the_sample(suffix: str, sample: str) -> None:
    assert source_findings(sample, suffix) == []


def test_ac20_the_checker_reads_comments_and_blocks_of_a_svelte_file() -> None:
    sample = (
        "<script>\n"
        "  // #1B2F55\n"
        "  const url = 'https://example.org' // #FFFFFF\n"
        "</script>\n"
        '<!-- fill="white" #1B2F55 -->\n'
        '<rect fill="none" stroke="currentColor" data-colour="2"/>\n'
        "<style>\n"
        "  /* color: #1B2F55 */\n"
        "  :root { --nock-navy: #1B2F55; }\n"
        "  a { color: var(--nock-navy); white-space: nowrap; }\n"
        "</style>\n"
    )

    assert source_findings(sample, ".svelte") == []


def test_ac20_the_checker_flags_a_style_directive_with_a_named_colour() -> None:
    assert source_findings('<p style:color="white">x</p>', ".svelte") != []


def test_ac20_web_src_holds_no_colour_literal_outside_the_token_block() -> None:
    findings: list[str] = []
    for path in source_files(".svelte", ".ts", ".css"):
        text = path.read_text(encoding="utf-8")
        for finding in source_findings(text, path.suffix):
            findings.append(f"{path.relative_to(path.parents[2])}: {finding}")

    assert findings == []
