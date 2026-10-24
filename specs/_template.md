---
area: area-name
file: file-name
status: draft
---

<!--
How to use this template (the rules are in specs/_map.md, "How domain specs work")
- Copy it to specs/<area>/<file>.md, the path specs/_map.md lists; `file` is the
  file name without .md.
- Say what is true now: no dated notes, no history, no decisions log.
- No look (cite the design file), no test mechanics, no copied code.
- Budget: about 15 KB and 20 criteria.
- Delete this comment in the copy.
-->

# area/file - Short name

## Purpose

Two or three sentences: who it serves and what it lets them do.

## Depends on

At most three files, each with the reason.

## Rules

The behaviour, as short numbered rules grouped by topic.

## New interface

Only while a change is being built: the names the tests must import before the
code exists (module path, names, signatures). Deleted when the change is done.

## Acceptance criteria

- **AC-1** One observable behaviour, with one concrete example. (← NNN AC-n)

## Edge cases

One line each, naming its criterion.

## Out of scope

What this domain deliberately does not do, and which file does it.

## Code

The modules that implement it, and the test files that prove it.
