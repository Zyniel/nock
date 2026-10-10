---
id: "001"
title: Slugify a text
status: done
---

# 001 - Slugify a text

This is the worked example that ships with the starter kit. It shows what a
finished spec looks like next to its tests (`tests/test_spec_001_slugify.py`) and
its code (`src/nock/text.py`). Delete the three files once you have your own.

## Goal

Other parts of the project need a short, URL-safe identifier derived from a
human-readable title, for example to name a file or build a link.

## Public interface

```python
# src/nock/text.py
def slugify(text: str) -> str: ...
```

## Acceptance criteria

- **AC-1** Given a text with upper-case letters, the result is in lower case:
  `slugify("Hello")` returns `"hello"`.
- **AC-2** Given a text where words are separated by one or more characters that
  are not ASCII letters or digits, each run of such characters becomes a single
  hyphen: `slugify("Hello,   World")` returns `"hello-world"`.
- **AC-3** The result never starts or ends with a hyphen:
  `slugify("  Hello World!  ")` returns `"hello-world"`.
- **AC-4** Given a text with no ASCII letter or digit at all, `slugify` raises
  `ValueError` with a message that contains `"no letter or digit"`.

## Edge cases and errors

- Digits are kept (AC-2): `slugify("Version 2")` returns `"version-2"`.
- The empty string and a string of only spaces or punctuation fall under AC-4.

## Out of scope

- Transliterating accented or non-Latin characters. They are treated as
  separators: `slugify("café")` returns `"caf"`.
- A maximum length.
- A configurable separator.

## Open questions

None.
