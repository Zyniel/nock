---
name: python-standards
description: Python coding standards for this repository (PEP 8, typing, docstrings, readability, and how uv, ruff, black and pyrefly are used). Use whenever writing, editing or reviewing Python code here.
---

# Python standards

These apply to everything under `src/`, `tests/` and `scripts/`.
The tools enforce the mechanical part; the readability rules are on you.

## Language and tooling

- Target the Python in `.python-version` (currently 3.14); the code must also run
  on the oldest version in `requires-python`.
- Every module starts with its docstring, then `from __future__ import annotations`.
  Ruff adds the import for you with `uv run ruff check --fix .`.
- Run everything through uv: `uv run pytest`, `uv run ruff check .`,
  `uv run black .`, `uv run pyrefly check`. Never call `pip` or a bare `python`.
- Black is the only formatter. Ruff is used as a linter only; do not run
  `ruff format`.
- Lines are at most 88 characters (black's default, inside the limit PEP 8 allows).
- Write invisible characters as `\N{NAME}` escapes, never raw, and keep LF line
  endings.

## Typing

- Annotate every parameter and every return value, including `-> None`.
- Use built-in generics and unions: `list[str]`, `dict[str, int]`, `str | None`.
- Avoid `Any`. When a value really can be anything, say why in a comment.
- No `# type: ignore` and no `# noqa`. If a check is wrong for this code, raise it
  in your report instead of silencing it.

## Readability comes first

People who are still learning Python maintain this code. Write for them.

- Prefer a plain `for` loop with named intermediate variables to a dense
  comprehension, a chain of calls or a clever one-liner. A comprehension is fine
  when it fits on one line and reads like a sentence.
- Use names that say what the value is (`unpaid_invoices`, not `lst` or `x`).
- Keep one job per function, and put work behind small functions with clear names
  rather than behind comments.
- Keep a clear separation of concerns: reading input, the logic itself, and
  writing output live in different functions or modules.
- Raise specific exceptions with a message that says what was wrong and what was
  expected. Never use a bare `except:`.
- Do not add options, parameters or abstractions the spec does not ask for.

## Docstrings

Google style, on every public module, class and function. One summary line, then
`Args:`, `Returns:` and `Raises:` when they apply. Describe what the caller needs
to know, not how the body works.

```python
def count_words(text: str) -> int:
    """Count the words in a text.

    Args:
        text: Text to analyse. Words are separated by whitespace.

    Returns:
        The number of words. An empty text has zero words.
    """
    words = text.split()
    return len(words)
```

## Tests

- pytest, plain `assert`, one behaviour per test.
- Files `tests/test_<name>_<topic>.py` for a domain (`tests/test_spec_NNN_*.py`
  hold the tests of v1.1.0), functions `test_acN_what_it_checks`.
- Use `pytest.raises(ErrorType, match="...")` for errors and
  `@pytest.mark.parametrize` for the same check over several inputs.

## Before handing work over

`uv run python scripts/gate.py` has to pass.
