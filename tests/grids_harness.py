"""Shared setup of the tests of the domain grids (`specs/content/grids.md`).

Pytest does not collect this module (its name does not start with `test_`). It
holds the grid builders that the tests of more than one domain use: a reference
grid with some answers written another way, for example FX-01 with the compound
words `VI-DE` and `NA-VAL` (grids AC-21, realtime AC-20, board AC-21 and AC-22).
"""

from __future__ import annotations

import json
from typing import Any

from nock.grid import Grid

# Raw JSON can hold anything, so its values are typed Any.
JsonData = dict[str, Any]

# FX-01 with two compound words: VIDE across from (2, 1) breaks after (2, 2),
# NAVAL down from (0, 1) breaks after (1, 1).
FX01_HYPHENS: dict[str, str] = {"VIDE": "VI-DE", "NAVAL": "NA-VAL"}


def with_answers(grid_text: str, answers: dict[str, str]) -> str:
    """Return a grid's JSON text with some of its answers written another way.

    Args:
        grid_text: The JSON text of a grid (the model of `content/grids.md`).
        answers: The new text of each answer, by the answer it replaces.

    Returns:
        The JSON text of the same grid with those answers replaced.

    Raises:
        ValueError: if an answer to replace is not an answer of the grid.
    """
    data: JsonData = json.loads(grid_text)
    replaced: set[str] = set()
    for cell in data["cells"]:
        if cell["type"] != "clue":
            continue
        for clue in cell["clues"]:
            old_answer = clue["answer"]
            if old_answer in answers:
                clue["answer"] = answers[old_answer]
                replaced.add(old_answer)
    missing = set(answers) - replaced
    if missing:
        raise ValueError(f"the grid has no answer {sorted(missing)}")
    return json.dumps(data, ensure_ascii=False)


def grid_with_answers(grid_text: str, answers: dict[str, str]) -> Grid:
    """Return a grid loaded with some of its answers written another way.

    Args:
        grid_text: The JSON text of a grid.
        answers: The new text of each answer, by the answer it replaces.

    Returns:
        The grid, validated by the model (not by the import checks).
    """
    return Grid.model_validate_json(with_answers(grid_text, answers))
