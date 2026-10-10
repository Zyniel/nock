---
id: "NNN"
title: Short feature name
status: draft
---

<!--
How to use this template
- Copy it to specs/NNN-short-name.md (NNN = next free three-digit number).
- status is draft, approved or done. Only a human sets "approved".
- Keep the section headings and the "- **AC-n**" bullet format: the quality gate
  reads them to check that every criterion has a test.
- Delete this comment in the copy.
-->

# NNN - Short feature name

## Goal

One or two sentences: who needs this, and what it lets them do.

## Public interface

The exact module path, names and signatures the tests will import. The tests are
written before the code, so this has to be precise.

```python
# src/nock/<module>.py
def function_name(argument: str) -> str: ...
```

## Acceptance criteria

One observable behaviour per criterion, with a concrete example.

- **AC-1** Given ..., when ..., then ...
- **AC-2** Given ..., when ..., then ...

## Edge cases and errors

Inputs at the limits and what must happen. Say which criterion each one belongs to.

## Out of scope

What this feature deliberately does not do.

## Work packages

Optional, only for a feature large enough for several implementers in an agent
team. Each package lists the files it owns. No file may appear in two packages.

## Open questions

Anything the request left undecided, with the options. Empty once approved.
