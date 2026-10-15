"""Tests of spec 040, AC-22 to AC-26: static checks of the client sources.

They read files under `web/` with Python only: `fr.json`, the markup scan of the
`.svelte` files (AC-23, with its own copy of the scan), the keys that `t(...)`
calls use, `web/index.html` and the removed demo files.

The shared setup is in `tests/spec040_harness.py`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from spec040_harness import (
    FR_JSON_PATH,
    PROJECT_ROOT,
    WEB_DIR,
    WEB_SRC_DIR,
    load_fr,
)

KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$")
REQUIRED_KEYS = [
    "app.title",
    "catalogue.heading",
    "catalogue.empty",
    "room.heading",
    "room.default_nickname",
    "room.status.connecting",
    "room.status.joined",
    "room.status.not_found",
    "room.status.closed",
    "not_found.heading",
]


# ---- Markup scan of AC-23 ---------------------------------------------------

_TEXT_ATTRIBUTE_NAMES = (
    "alt|title|placeholder|label|aria-label|aria-description|aria-placeholder"
    "|aria-roledescription|aria-valuetext"
)
_TEXT_ATTRIBUTE = re.compile(
    rf"(?<![\w:-])(?:{_TEXT_ATTRIBUTE_NAMES})\s*=\s*(?:\"([^\"]*)\"|'([^']*)')"
)
_TAG = re.compile(r"<[^>]*>")


def _remove_braces_groups(text: str) -> str:
    """Remove every {...} group, nested braces included."""
    kept: list[str] = []
    depth = 0
    for character in text:
        if character == "{":
            depth += 1
        elif character == "}" and depth > 0:
            depth -= 1
        elif depth == 0:
            kept.append(character)
    return "".join(kept)


def scan_markup(text: str) -> list[str]:
    """Return the user-visible literal strings found in a .svelte file."""
    violations: list[str] = []
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = _remove_braces_groups(text)
    for tag in _TAG.findall(text):
        for match in _TEXT_ATTRIBUTE.finditer(tag):
            value = match.group(1) if match.group(1) is not None else match.group(2)
            if value.strip():
                violations.append(f"attribute: {match.group(0)}")
    remaining = _TAG.sub("", text)
    if remaining.strip():
        violations.append(f"text: {remaining.strip()}")
    return violations


# ---- AC-22 to AC-26: static -------------------------------------------------


def svelte_files() -> list[Path]:
    return sorted(WEB_SRC_DIR.rglob("*.svelte"))


def test_ac22_fr_json_is_a_flat_catalogue_with_the_required_keys() -> None:
    messages = json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))

    assert isinstance(messages, dict)
    for key, value in messages.items():
        assert KEY_PATTERN.match(key), key
        assert isinstance(value, str), key
        assert value != "", key
    for required_key in REQUIRED_KEYS:
        assert required_key in messages


@pytest.mark.parametrize(
    "markup",
    [
        "<p>Bonjour</p>",
        '<img alt="Logo" />',
        '<button title="Salon {code}">',
        "<svelte:head><title>Nock</title></svelte:head>",
        "{#if ready}<p>Bonjour</p>{/if}",
        "<input placeholder='Pseudo' />",
        '<div aria-label="Fermer"></div>',
        '<p>{t("a.b")}</p> Reste',
    ],
)
def test_ac23_scan_finds_violations(markup: str) -> None:
    assert scan_markup(markup) != []


@pytest.mark.parametrize(
    "markup",
    [
        '<p>{t("a.b")}</p>',
        '<img alt="" />',
        '<img alt={t("a.b")} />',
        "<input placeholder=\"{t('a.b')}\" />",
        "<script lang=\"ts\">const x = 'Bonjour';</script><p>{x}</p>",
        "<!-- Bonjour --><p>{t('a.b')}</p>",
        "<style>p { content: 'Bonjour'; }</style>",
        '{#if ok}<p>{t("a.b")}</p>{:else}<p>{t("a.c")}</p>{/if}',
    ],
)
def test_ac23_scan_accepts_clean_markup(markup: str) -> None:
    assert scan_markup(markup) == []


def test_ac23_svelte_files_hold_no_literal_text() -> None:
    files = svelte_files()
    assert files != []

    violations: dict[str, list[str]] = {}
    for svelte_file in files:
        found = scan_markup(svelte_file.read_text(encoding="utf-8"))
        if found:
            violations[svelte_file.name] = found

    assert violations == {}


def test_ac24_every_translation_key_used_exists() -> None:
    messages = load_fr()
    key_call = re.compile(r"\bt\(\s*[\"']([^\"']+)[\"']")
    used_keys: list[str] = []
    for pattern in ("*.svelte", "*.ts"):
        for source_file in sorted(WEB_SRC_DIR.rglob(pattern)):
            text = source_file.read_text(encoding="utf-8")
            used_keys.extend(key_call.findall(text))

    assert used_keys != []
    unknown_keys = [key for key in used_keys if key not in messages]
    assert unknown_keys == []


def test_ac25_index_html_has_no_text_and_french_lang() -> None:
    html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    html_tag = re.search(r"<html\b[^>]*>", html, flags=re.IGNORECASE)
    assert html_tag is not None
    assert re.search(r"\blang\s*=\s*[\"']fr[\"']", html_tag.group(0))
    title = re.search(r"<title>(.*?)</title>", html, flags=re.DOTALL | re.IGNORECASE)
    assert title is not None
    assert title.group(1).strip() == ""
    body = re.search(r"<body\b[^>]*>(.*)</body>", html, flags=re.DOTALL)
    assert body is not None
    body_text = re.sub(r"<[^>]*>", "", body.group(1))
    assert body_text.strip() == ""
    assert 'id="app"' in body.group(1)


@pytest.mark.parametrize(
    "demo_path",
    [
        "web/src/lib/Counter.svelte",
        "web/src/assets/hero.png",
        "web/src/assets/svelte.svg",
        "web/src/assets/vite.svg",
        "web/public/icons.svg",
    ],
)
def test_ac26_demo_files_are_removed(demo_path: str) -> None:
    assert not (PROJECT_ROOT / demo_path).exists()


def test_ac26_no_demo_text_left_in_web_src() -> None:
    offending: list[str] = []
    for source_file in sorted(WEB_SRC_DIR.rglob("*")):
        if not source_file.is_file():
            continue
        content = source_file.read_bytes()
        if b"Counter" in content or b"svelte.svg" in content:
            offending.append(source_file.name)

    assert offending == []
    assert (WEB_SRC_DIR / "App.svelte").is_file()
