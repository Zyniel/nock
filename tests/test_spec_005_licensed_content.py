"""Tests of spec 005: licensed content only (credits and withdrawal of grids)."""

from __future__ import annotations

import ast
import contextlib
import json
import queue
import re
import threading
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.testclient import WebSocketTestSession

from nock.catalogue import (
    Catalogue,
    CatalogueEntry,
    CatalogueError,
    GridSummary,
    load_catalogue,
    summarize,
)
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    ErrorMessage,
    Join,
    LetterCellView,
    LetterChanged,
    Snapshot,
    parse_server_message,
)
from nock.room import RoomConfig
from nock.server import create_app
from nock.store import RoomStore

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
WEB_DIR = PROJECT_ROOT / "web"
WEB_SRC_DIR = WEB_DIR / "src"
WEB_INDEX = WEB_DIR / "index.html"

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
NOT_FOUND_BODY = {"detail": "Not Found"}
RECEIVE_TIMEOUT_SECONDS = 5.0
SERVER_CONFIG = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)

AUTHOR = "Équipe Nock"
SOURCE = "Commande Nock 2026"
LICENCE = "Contrat d'auteur Nock n° 1"

# The solution of FX-01 (specs/_reference.md): position -> letter.
SOLUTION: dict[tuple[int, int], str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        SOLUTION[(_row, _offset + 1)] = _letter
assert len(SOLUTION) == 18

FORBIDDEN_PATHS = [
    "httpx",
    "httpx2",
    "requests",
    "urllib.request",
    "aiohttp",
    "urllib3",
    "http.client",
    "socket",
    "ftplib",
    "ssl",
    "smtplib",
    "xmlrpc.client",
    "websockets.client",
    "websockets.sync.client",
    "websockets.connect",
]
ANYIO_CONNECT_PREFIX = "anyio.connect_"
FORBIDDEN_CALL_NAMES = ["create_connection", "open_connection", "open_unix_connection"]
CLIENT_URL_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"wss?://", re.IGNORECASE),
    re.compile(r"""["'`]//[a-z0-9$]""", re.IGNORECASE),
    re.compile(r"""url\( *["']? *//""", re.IGNORECASE),
]


# ---- Fixtures and helpers ---------------------------------------------------


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def write_grid_file(
    directory: Path,
    fx01_text: str,
    drop: tuple[str, ...] = (),
    overrides: dict[str, object] | None = None,
) -> Path:
    """Write `g1.json`: number 1, FX-01 and CREDITS, minus `drop`, plus `overrides`."""
    payload: dict[str, object] = {
        "number": 1,
        "published_on": "2026-10-01",
        "force": 2,
        "published": True,
        **credits(),
        "grid": json.loads(fx01_text),
    }
    for key in drop:
        del payload[key]
    if overrides is not None:
        payload.update(overrides)
    path = directory / "g1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def make_entry(
    grid: Grid, number: int, published: bool = True, withdrawn: bool = False
) -> CatalogueEntry:
    return CatalogueEntry(
        number=number,
        published_on=date(2026, 10, 1),
        force=2,
        published=published,
        **credits(),
        withdrawn=withdrawn,
        grid=grid,
    )


@pytest.fixture
def mixed_catalogue(fx01_grid: Grid) -> Catalogue:
    """Entry 1 published, entry 2 published and withdrawn."""
    entries = (
        make_entry(fx01_grid, 1),
        make_entry(fx01_grid, 2, withdrawn=True),
    )
    return Catalogue(entries=entries)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry(config=SERVER_CONFIG)
    yield room_registry
    room_registry.close()


@pytest.fixture
def client(
    registry: RoomRegistry, mixed_catalogue: Catalogue, dist_dir: Path
) -> Iterator[TestClient]:
    app = create_app(rooms=registry, catalogue=mixed_catalogue, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


def error_text(error: pytest.ExceptionInfo[CatalogueError]) -> ValidationError:
    """Return the pydantic error behind a CatalogueError, failing when absent."""
    cause = error.value.__cause__
    assert isinstance(cause, ValidationError)
    return cause


# ---- AC-1: missing credits refuse the file ----------------------------------


@pytest.mark.parametrize("field", ["author", "source", "licence"])
def test_ac1_a_file_without_a_credit_key_is_refused(
    tmp_path: Path, fx01_text: str, field: str
) -> None:
    write_grid_file(tmp_path, fx01_text, drop=(field,))

    with pytest.raises(CatalogueError, match=r"g1\.json") as error_info:
        load_catalogue(tmp_path)

    cause = error_text(error_info)
    assert field in str(cause)


def test_ac1_the_american_spelling_license_is_an_unknown_key(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(
        tmp_path, fx01_text, drop=("licence",), overrides={"license": LICENCE}
    )

    with pytest.raises(CatalogueError, match=r"g1\.json"):
        load_catalogue(tmp_path)


def test_ac1_a_file_with_none_of_the_credits_is_refused(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, drop=("author", "source", "licence"))

    with pytest.raises(CatalogueError, match=r"g1\.json"):
        load_catalogue(tmp_path)


@pytest.mark.parametrize("field", ["author", "source", "licence"])
def test_ac1_an_entry_built_in_code_without_a_credit_is_refused(
    fx01_grid: Grid, field: str
) -> None:
    values = {"author": AUTHOR, "source": SOURCE, "licence": LICENCE}
    del values[field]

    with pytest.raises(ValidationError, match=field):
        CatalogueEntry(
            number=1,
            published_on=date(2026, 10, 1),
            force=2,
            published=True,
            grid=fx01_grid,
            **values,
        )


# ---- AC-2: blank, null, wrong type or too long ------------------------------


@pytest.mark.parametrize("field", ["author", "source", "licence"])
@pytest.mark.parametrize(
    "bad_value",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="blank"),
        pytest.param("\n\t ", id="whitespace-only"),
        pytest.param("a" * 201, id="201-characters"),
        pytest.param("é" * 201, id="201-code-points"),
        pytest.param(" " + "a" * 201 + " ", id="201-after-stripping"),
        pytest.param(None, id="null"),
        pytest.param(42, id="number"),
        pytest.param(["Équipe Nock"], id="list"),
    ],
)
def test_ac2_a_blank_or_invalid_credit_is_refused(
    tmp_path: Path, fx01_text: str, field: str, bad_value: object
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={field: bad_value})

    with pytest.raises(CatalogueError, match=r"g1\.json") as error_info:
        load_catalogue(tmp_path)

    assert isinstance(error_info.value.__cause__, ValidationError)


def test_ac2_a_credit_is_stripped_at_both_ends(tmp_path: Path, fx01_text: str) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"author": "  Équipe Nock  "})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].author == "Équipe Nock"


@pytest.mark.parametrize("field", ["source", "licence"])
def test_ac2_every_credit_is_stripped(
    tmp_path: Path, fx01_text: str, field: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={field: "\t texte \n"})

    loaded = load_catalogue(tmp_path)

    assert getattr(loaded.entries[0], field) == "texte"


@pytest.mark.parametrize("field", ["author", "source", "licence"])
def test_ac2_a_credit_of_200_characters_is_accepted(
    tmp_path: Path, fx01_text: str, field: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={field: "a" * 200})

    loaded = load_catalogue(tmp_path)

    assert getattr(loaded.entries[0], field) == "a" * 200


def test_ac2_the_limit_counts_the_characters_after_stripping(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"author": "  " + "a" * 200 + "  "})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].author == "a" * 200


def test_ac2_the_limit_counts_code_points_not_bytes(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"source": "é" * 200})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].source == "é" * 200


def test_ac2_a_single_character_credit_is_accepted(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"licence": "x"})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].licence == "x"


def test_ac2_line_breaks_inside_a_credit_are_kept(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"licence": "Contrat\nn° 1"})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].licence == "Contrat\nn° 1"


# ---- AC-3: a complete file loads with its credits ---------------------------


def test_ac3_a_complete_file_loads_with_its_credits_and_is_not_withdrawn(
    tmp_path: Path, fx01_text: str
) -> None:
    write_grid_file(tmp_path, fx01_text)

    loaded = load_catalogue(tmp_path)

    assert len(loaded.entries) == 1
    entry = loaded.entries[0]
    assert entry.author == AUTHOR
    assert entry.source == SOURCE
    assert entry.licence == LICENCE
    assert entry.withdrawn is False


def test_ac3_withdrawn_true_is_read(tmp_path: Path, fx01_text: str) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"withdrawn": True})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].withdrawn is True


def test_ac3_withdrawn_false_is_read(tmp_path: Path, fx01_text: str) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"withdrawn": False})

    loaded = load_catalogue(tmp_path)

    assert loaded.entries[0].withdrawn is False


@pytest.mark.parametrize(
    "bad_value",
    [
        pytest.param("yes", id="string-yes"),
        pytest.param(1, id="number-1"),
        pytest.param(0, id="number-0"),
        pytest.param("true", id="string-true"),
    ],
)
def test_ac3_withdrawn_must_be_a_strict_boolean(
    tmp_path: Path, fx01_text: str, bad_value: object
) -> None:
    write_grid_file(tmp_path, fx01_text, overrides={"withdrawn": bad_value})

    with pytest.raises(CatalogueError, match=r"g1\.json"):
        load_catalogue(tmp_path)


def test_ac3_withdrawn_is_false_by_default_on_an_entry_built_in_code(
    fx01_grid: Grid,
) -> None:
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=fx01_grid,
    )

    assert entry.withdrawn is False


def test_ac3_the_summary_does_not_carry_the_credits(fx01_grid: Grid) -> None:
    entry = make_entry(fx01_grid, 7)

    summary = summarize(entry)

    assert summary == GridSummary(
        number=7,
        published_on=date(2026, 10, 1),
        force=2,
        width=5,
        height=5,
        word_count=8,
    )
    assert set(summary.model_dump()) == {
        "number",
        "published_on",
        "force",
        "width",
        "height",
        "word_count",
    }


# ---- AC-4: no outgoing connection from src/ ---------------------------------


def path_is_forbidden(path: str) -> bool:
    """Tell whether a dotted path is a forbidden module, callable or inside one."""
    if path.startswith(ANYIO_CONNECT_PREFIX):
        return True
    for forbidden in FORBIDDEN_PATHS:
        if path == forbidden or path.startswith(forbidden + "."):
            return True
    return False


def collect_bindings(tree: ast.AST) -> dict[str, str]:
    """Map every name bound by an absolute import statement to its dotted path."""
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is not None:
                    bindings[alias.asname] = alias.name
                else:
                    first_part = alias.name.split(".")[0]
                    bindings[first_part] = first_part
        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 or node.module is None:
                continue
            for alias in node.names:
                bound_name = alias.asname if alias.asname is not None else alias.name
                bindings[bound_name] = node.module + "." + alias.name
    return bindings


def resolve_path(node: ast.expr, bindings: dict[str, str]) -> str | None:
    """Return the dotted path of a name or attribute chain bound by an import."""
    if isinstance(node, ast.Name):
        return bindings.get(node.id)
    if isinstance(node, ast.Attribute):
        base_path = resolve_path(node.value, bindings)
        if base_path is None:
            return None
        return base_path + "." + node.attr
    return None


def string_argument(call: ast.Call, index: int) -> str | None:
    """Return the string literal given as argument `index` of a call, if any."""
    if len(call.args) <= index:
        return None
    argument = call.args[index]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    return None


def find_import_findings(node: ast.stmt) -> list[str]:
    """Apply rules 1 and 2 to an import statement."""
    findings: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            if path_is_forbidden(alias.name):
                findings.append(f"import {alias.name}")
    elif isinstance(node, ast.ImportFrom):
        if node.level > 0 or node.module is None:
            return findings
        for alias in node.names:
            full_path = node.module + "." + alias.name
            if (
                path_is_forbidden(node.module)
                or path_is_forbidden(full_path)
                or alias.name in FORBIDDEN_CALL_NAMES
            ):
                findings.append(f"from {node.module} import {alias.name}")
    return findings


def find_call_findings(call: ast.Call, bindings: dict[str, str]) -> list[str]:
    """Apply rules 5 and 6 to a call."""
    findings: list[str] = []
    function = call.func
    function_path = resolve_path(function, bindings)
    is_import_call = function_path == "importlib.import_module" or (
        isinstance(function, ast.Name) and function.id == "__import__"
    )
    if is_import_call:
        module_name = string_argument(call, 0)
        if module_name is not None and path_is_forbidden(module_name):
            findings.append(f"import by name {module_name}")
    if isinstance(function, ast.Name) and function.id == "getattr":
        attribute_name = string_argument(call, 1)
        if attribute_name is not None and len(call.args) >= 1:
            target_path = resolve_path(call.args[0], bindings)
            if attribute_name in FORBIDDEN_CALL_NAMES:
                findings.append(f"getattr {attribute_name}")
            elif target_path is not None and path_is_forbidden(
                target_path + "." + attribute_name
            ):
                findings.append(f"getattr {target_path}.{attribute_name}")
    return findings


def find_network_use(source: str) -> list[str]:
    """Return what `source` uses to reach a network, by the six rules of AC-4."""
    findings: list[str] = []
    tree = ast.parse(source)
    bindings = collect_bindings(tree)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            findings.extend(find_import_findings(node))
        elif isinstance(node, (ast.Name, ast.Attribute)):
            resolved = resolve_path(node, bindings)
            if resolved is not None and path_is_forbidden(resolved):
                findings.append(f"path {resolved}")
            identifier = node.id if isinstance(node, ast.Name) else node.attr
            if identifier in FORBIDDEN_CALL_NAMES:
                findings.append(f"name {identifier}")
        elif isinstance(node, ast.Call):
            findings.extend(find_call_findings(node, bindings))
    return findings


FLAGGED_SERVER_SAMPLES = [
    "import httpx",
    "import requests as r",
    "from urllib.request import urlopen",
    "from urllib import request",
    "import aiohttp.client",
    "from http import client",
    "import socket",
    'asyncio.open_connection("x", 80)',
    'loop.create_connection(f, "x", 80)',
    "from asyncio import open_connection",
    "from asyncio import open_connection as oc",
    'asyncio.open_unix_connection("/tmp/s")',
    "f = asyncio.open_connection",
    'import urllib\nurllib.request.urlopen("https://x")',
    'import http\nhttp.client.HTTPConnection("x")',
    "import ssl",
    "import smtplib as s",
    "import xmlrpc.client",
    "from xmlrpc import client",
    'import anyio\nanyio.connect_tcp("x", 80)',
    'import anyio\nanyio.connect_unix("/tmp/s")',
    "from anyio import connect_tcp as c",
    'import websockets\nwebsockets.connect("wss://x")',
    'import websockets as ws\nws.connect("wss://x")',
    "from websockets import connect",
    "import websockets.client",
    "from websockets.sync.client import connect",
    "from websockets.sync import client",
    'import importlib\nimportlib.import_module("socket")',
    'from importlib import import_module\nimport_module("http.client")',
    '__import__("urllib.request")',
    'import asyncio\ngetattr(asyncio, "open_connection")',
    'import anyio\ngetattr(anyio, "connect_tcp")',
]

UNFLAGGED_SERVER_SAMPLES = [
    "import sqlite3",
    "sqlite3.connect(path)",
    "from urllib.parse import quote",
    'import urllib\nurllib.parse.quote("a b")',
    "import uvicorn",
    "import asyncio\nasyncio.sleep(1)",
    "import anyio\nanyio.to_thread.run_sync(f)",
    "import websockets",
    'import importlib\nimportlib.import_module("json")',
    "import importlib\nimportlib.import_module(name)",
    'getattr(state, "grid")',
    "getattr(obj, name)",
    "requests = []\nrequests.append(1)",
    "from .room import RoomState",
    "def connect(x): return x\nconnect(1)",
]


@pytest.mark.parametrize("sample", FLAGGED_SERVER_SAMPLES)
def test_ac4_the_checker_flags_network_use(sample: str) -> None:
    assert find_network_use(sample) != []


@pytest.mark.parametrize("sample", UNFLAGGED_SERVER_SAMPLES)
def test_ac4_the_checker_does_not_flag_other_code(sample: str) -> None:
    assert find_network_use(sample) == []


def test_ac4_no_module_of_src_imports_an_http_client_or_opens_a_connection() -> None:
    source_files = sorted(SRC_DIR.rglob("*.py"))
    assert source_files != []

    offences: list[str] = []
    for source_file in source_files:
        text = source_file.read_text(encoding="utf-8")
        for finding in find_network_use(text):
            offences.append(f"{source_file.relative_to(PROJECT_ROOT)}: {finding}")

    assert offences == []


# ---- AC-5: no third-party URL in the web client -----------------------------


def contains_third_party_url(text: str) -> bool:
    """Tell whether `text` is flagged by one of the four rules of AC-5."""
    return any(pattern.search(text) for pattern in CLIENT_URL_PATTERNS)


FLAGGED_CLIENT_SAMPLES = [
    'fetch("https://example.com/grids")',
    "const u = 'HTTP://x'",
    'new WebSocket("wss://example.com/ws")',
    "const u = 'WS://x'",
    "fetch('//example.com/grids')",
    "const u = `//${host}/api`",
    '<script src="//cdn.example.com/a.js"></script>',
    '{"logo": "//cdn.example.com/l.png"}',
    '{"logo": "https://example.com/l.png"}',
    "src: url(//cdn.example.com/f.woff2);",
    'background: url( "//cdn.example.com/b.png" );',
    "@import url('//fonts.example.com/a.css');",
    '@import "//fonts.example.com/a.css";',
    "background: url(HTTPS://example.com/b.png);",
]

UNFLAGGED_CLIENT_SAMPLES = [
    "`${scheme}://${location.host}/api/rooms`",
    "fetch('/api/grids')",
    "// a line comment",
    'const s = "// not a url"',
    "src: url(/fonts/a.woff2);",
    'background: url("data:image/png;base64,AAAA");',
    '@import "./theme.css";',
    '{"title": "Nock"}',
    'const u = "ht" + "tp://example.com"',
]


def read_client_texts() -> dict[Path, str]:
    """Read web/index.html and every UTF-8 file of web/src/ as text."""
    paths: list[Path] = [WEB_INDEX]
    for candidate in sorted(WEB_SRC_DIR.rglob("*")):
        if candidate.is_file():
            paths.append(candidate)
    texts: dict[Path, str] = {}
    for path in paths:
        try:
            texts[path] = path.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
    return texts


@pytest.mark.parametrize("sample", FLAGGED_CLIENT_SAMPLES)
def test_ac5_the_checker_flags_third_party_urls(sample: str) -> None:
    assert contains_third_party_url(sample)


@pytest.mark.parametrize("sample", UNFLAGGED_CLIENT_SAMPLES)
def test_ac5_the_checker_does_not_flag_relative_or_built_urls(sample: str) -> None:
    assert not contains_third_party_url(sample)


def test_ac5_no_file_of_the_web_client_names_a_third_party_url() -> None:
    assert WEB_INDEX.is_file()
    texts = read_client_texts()
    assert len(texts) > 1

    offences: list[str] = []
    for path, text in texts.items():
        if contains_third_party_url(text):
            offences.append(str(path.relative_to(PROJECT_ROOT)))

    assert offences == []


# ---- AC-6: no new room on a withdrawn grid ----------------------------------


def test_ac6_published_summaries_skip_the_withdrawn_entry(
    mixed_catalogue: Catalogue,
) -> None:
    summaries = mixed_catalogue.published_summaries()

    numbers = []
    for summary in summaries:
        numbers.append(summary.number)
    assert numbers == [1]


def test_ac6_published_summaries_with_a_force_skip_the_withdrawn_entry(
    mixed_catalogue: Catalogue,
) -> None:
    summaries = mixed_catalogue.published_summaries(force=2)

    numbers = []
    for summary in summaries:
        numbers.append(summary.number)
    assert numbers == [1]


def test_ac6_find_published_returns_none_for_the_withdrawn_entry(
    mixed_catalogue: Catalogue,
) -> None:
    assert mixed_catalogue.find_published(2) is None


def test_ac6_find_published_still_finds_the_other_entry(
    mixed_catalogue: Catalogue,
) -> None:
    found = mixed_catalogue.find_published(1)

    assert found is not None
    assert found.number == 1


def test_ac6_withdrawn_wins_over_published_true(fx01_grid: Grid) -> None:
    catalogue = Catalogue(entries=(make_entry(fx01_grid, 3, withdrawn=True),))

    assert catalogue.find_published(3) is None
    assert catalogue.published_summaries() == []


def test_ac6_an_unpublished_withdrawn_entry_is_hidden(fx01_grid: Grid) -> None:
    entry = make_entry(fx01_grid, 3, published=False, withdrawn=True)
    catalogue = Catalogue(entries=(entry,))

    assert catalogue.find_published(3) is None
    assert catalogue.published_summaries() == []


def test_ac6_the_list_route_shows_only_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.get("/api/grids")

    assert response.status_code == 200
    numbers = []
    for item in response.json():
        numbers.append(item["number"])
    assert numbers == [1]


def test_ac6_the_list_route_keeps_the_shape_of_spec_004(client: TestClient) -> None:
    response = client.get("/api/grids")

    assert response.json() == [
        {
            "number": 1,
            "published_on": "2026-10-01",
            "force": 2,
            "width": 5,
            "height": 5,
            "word_count": 8,
        }
    ]


def test_ac6_the_detail_route_answers_200_for_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.get("/api/grids/1")

    assert response.status_code == 200
    assert response.json()["number"] == 1


def test_ac6_the_detail_route_answers_404_for_the_withdrawn_entry(
    client: TestClient,
) -> None:
    response = client.get("/api/grids/2")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac6_the_grid_page_answers_200_for_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.get("/g/1")

    assert response.status_code == 200


def test_ac6_the_grid_page_answers_404_for_the_withdrawn_entry(
    client: TestClient,
) -> None:
    response = client.get("/g/2")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac6_a_room_is_created_on_the_entry_that_is_not_withdrawn(
    client: TestClient,
) -> None:
    response = client.post("/api/rooms", json={"grid_number": 1})

    assert response.status_code == 201
    assert re.fullmatch(r"[A-Z0-9]{6}", response.json()["code"]) is not None


def test_ac6_no_room_is_created_on_the_withdrawn_entry(client: TestClient) -> None:
    response = client.post("/api/rooms", json={"grid_number": 2})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac6_a_withdrawn_unpublished_entry_answers_404_everywhere(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    entry = make_entry(fx01_grid, 5, published=False, withdrawn=True)
    app_registry = RoomRegistry(config=SERVER_CONFIG)
    try:
        app = create_app(
            rooms=app_registry, catalogue=Catalogue(entries=(entry,)), dist_dir=dist_dir
        )
        with TestClient(app) as test_client:
            assert test_client.get("/api/grids").json() == []
            assert test_client.get("/api/grids/5").status_code == 404
            assert test_client.get("/g/5").status_code == 404
            posted = test_client.post("/api/rooms", json={"grid_number": 5})
            assert posted.status_code == 404
    finally:
        app_registry.close()


# ---- AC-7: open rooms on a withdrawn grid can finish ------------------------


def receive_text_or_fail(websocket: WebSocketTestSession) -> str:
    """Return the next text of the socket, failing instead of waiting forever."""
    received: queue.Queue[str | BaseException] = queue.Queue()

    def read() -> None:
        try:
            received.put(websocket.receive_text())
        except BaseException as error:  # handed to the test thread, re-raised there
            received.put(error)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        outcome = received.get(timeout=RECEIVE_TIMEOUT_SECONDS)
    except queue.Empty:
        pytest.fail(f"nothing received from the socket in {RECEIVE_TIMEOUT_SECONDS}s")
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome


def join_room(
    stack: contextlib.ExitStack, http_client: TestClient, code: str, nickname: str
) -> WebSocketTestSession:
    """Open a socket on the room, join and check the answer is a snapshot."""
    websocket = stack.enter_context(
        http_client.websocket_connect(f"/api/rooms/{code}/ws")
    )
    websocket.send_text(Join(nickname=nickname).model_dump_json())
    message = parse_server_message(receive_text_or_fail(websocket))
    assert isinstance(message, Snapshot)
    return websocket


def type_and_wait(
    websocket: WebSocketTestSession, row: int, column: int, letter: str
) -> None:
    """Send one letter and read until its letter_changed (other events skipped)."""
    edit = EditLetter(row=row, column=column, letter=letter)
    websocket.send_text(edit.model_dump_json())
    while True:
        message = parse_server_message(receive_text_or_fail(websocket))
        assert not isinstance(message, ErrorMessage), message
        if isinstance(message, LetterChanged) and (message.row, message.column) == (
            row,
            column,
        ):
            assert message.letter == letter
            return


def count_letters(snapshot: Snapshot) -> dict[tuple[int, int], str]:
    """Return the letters written in the cells of a snapshot."""
    letters: dict[tuple[int, int], str] = {}
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and cell.letter is not None:
            letters[(cell.row, cell.column)] = cell.letter
    return letters


def test_ac7_a_room_open_before_the_withdrawal_can_be_finished_and_reloaded(
    tmp_path: Path, fx01_grid: Grid, dist_dir: Path
) -> None:
    store_path = tmp_path / "nock.sqlite3"
    store = RoomStore(store_path)
    shared = RoomRegistry(config=SERVER_CONFIG, store=store)
    before = Catalogue(entries=(make_entry(fx01_grid, 1),))
    after = Catalogue(entries=(make_entry(fx01_grid, 1, withdrawn=True),))
    app_a = create_app(rooms=shared, catalogue=before, dist_dir=dist_dir)
    app_b = create_app(rooms=shared, catalogue=after, dist_dir=dist_dir)
    second_store: RoomStore | None = None
    second_registry: RoomRegistry | None = None
    try:
        created = TestClient(app_a).post("/api/rooms", json={"grid_number": 1})
        assert created.status_code == 201
        code = created.json()["code"]

        with contextlib.ExitStack() as stack:
            client_b = stack.enter_context(TestClient(app_b))
            ana = join_room(stack, client_b, code, "Ana")
            bob = join_room(stack, client_b, code, "Bob")
            sockets = [ana, bob]
            for index, position in enumerate(sorted(SOLUTION)):
                row, column = position
                type_and_wait(sockets[index % 2], row, column, SOLUTION[position])

            refused = client_b.post("/api/rooms", json={"grid_number": 1})
            assert refused.status_code == 404
            assert refused.json() == NOT_FOUND_BODY

        shared.close()
        store.close()

        second_store = RoomStore(store_path)
        second_registry = RoomRegistry(config=SERVER_CONFIG, store=second_store)
        app_again = create_app(
            rooms=second_registry, catalogue=after, dist_dir=dist_dir
        )
        with contextlib.ExitStack() as stack:
            client_again = stack.enter_context(TestClient(app_again))
            websocket = stack.enter_context(
                client_again.websocket_connect(f"/api/rooms/{code}/ws")
            )
            websocket.send_text(Join(nickname="Cleo").model_dump_json())
            message = parse_server_message(receive_text_or_fail(websocket))

        assert isinstance(message, Snapshot)
        assert count_letters(message) == SOLUTION
    finally:
        if second_registry is not None:
            second_registry.close()
        if second_store is not None:
            second_store.close()
        shared.close()
        store.close()


def test_ac7_a_room_page_is_still_served_whatever_the_catalogue_holds(
    client: TestClient,
) -> None:
    response = client.get("/r/ABC123")

    assert response.status_code == 200
