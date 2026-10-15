"""Tests of spec 005, AC-4 and AC-5: no third-party fetching.

AC-4 scans `src/` for an import of a network client or an outgoing connection, AC-5
scans `web/index.html` and `web/src/` for a URL on another host. Each scan has its
own checker, tested on samples that must and must not be flagged. Nothing in this
file is shared with the other criterion groups of spec 005.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
WEB_DIR = PROJECT_ROOT / "web"
WEB_SRC_DIR = WEB_DIR / "src"
WEB_INDEX = WEB_DIR / "index.html"

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
    "websockets.asyncio.client",
    "websockets.legacy.client",
    "poplib",
    "imaplib",
    "telnetlib",
    "websockets.connect",
]
ANYIO_CONNECT_PREFIX = "anyio.connect_"
FORBIDDEN_CALL_NAMES = [
    "create_connection",
    "open_connection",
    "open_unix_connection",
    "create_unix_connection",
    "create_datagram_endpoint",
    "sock_connect",
]
CLIENT_URL_PATTERNS = [
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"wss?://", re.IGNORECASE),
    re.compile(r"""["'`]//[a-z0-9$]""", re.IGNORECASE),
    re.compile(r"""url\(\s*["']?\s*//""", re.IGNORECASE),
]


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
    "from websockets.asyncio.client import connect",
    'import websockets.asyncio.client as c\nc.connect("wss://x")',
    "from websockets.legacy.client import connect",
    "import poplib",
    'loop.create_unix_connection(f, "/tmp/s")',
    "loop.sock_connect(s, addr)",
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
    "src: url(\t//cdn.example.com/f.woff2);",
    'background: url(\n  "//cdn.example.com/b.png");',
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
