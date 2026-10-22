"""The sheet's style: _design.md tokens, fonts and components, and the sheet chrome."""

from __future__ import annotations

from pathlib import Path

FONT_DIR = "../../web/node_modules/@fontsource"


def font_faces() -> str:
    """Return the @font-face rules of the app's own font files."""
    out = []
    faces = [
        ("Source Sans 3", "source-sans-3", 400, "normal"),
        ("Source Sans 3", "source-sans-3", 500, "normal"),
        ("Source Sans 3", "source-sans-3", 600, "normal"),
        ("Source Sans 3", "source-sans-3", 700, "normal"),
        ("Source Sans 3", "source-sans-3", 500, "italic"),
        ("Source Sans 3", "source-sans-3", 700, "italic"),
        ("IBM Plex Sans Condensed", "ibm-plex-sans-condensed", 500, "normal"),
        ("IBM Plex Sans Condensed", "ibm-plex-sans-condensed", 600, "normal"),
    ]
    for fam, pkg, w, style in faces:
        local = fam if style == "normal" else fam + " Italic"
        out.append(
            f'@font-face {{ font-family: "{fam}"; '
            f"font-weight: {w}; font-style: {style}; "
            "font-display: swap; "
            f'src: local("{local}"), url("{FONT_DIR}/{pkg}/files/{pkg}'
            f'-latin-{w}-{style}.woff2") format("woff2"); '
            "}"
        )
    return "\n".join(out)


CSS = (Path(__file__).resolve().parent / "style.css").read_text(encoding="utf-8")
