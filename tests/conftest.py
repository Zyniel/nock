"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fx01_text() -> str:
    """Return the JSON text of the FX-01 reference grid."""
    return (FIXTURES_DIR / "fx01.json").read_text(encoding="utf-8")
