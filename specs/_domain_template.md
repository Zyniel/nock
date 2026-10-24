---
area: area-name
file: file-name
status: draft
baseline: v1.1.0
---

<!--
How to use this template
- Copy it to specs/<area>/<file>.md, as listed in specs/_map.md.
- status is draft, approved or done. Only a human sets "approved".
- Budget: about 15 KB and 20 criteria. Over that, split the domain.
- Say what is true now. No dated notes, no decisions, no history: those go in the
  commit message, or in <file>.notes.md when a reason must be kept.
- No look: cite the design file and section instead.
- No test mechanics (window sizes, test ids, sample lists): the tests hold them.
- Delete this comment in the copy.
-->

# area/file - Short name

## Purpose

Two or three sentences: who it serves and what it lets them do.

## Depends on

At most three domain files or shared files, each with the reason.

## Rules

The behaviour, as short numbered rules grouped by topic. A rule a criterion
checks names that criterion.

## Acceptance criteria

- **AC-1** One observable behaviour, with one concrete example. (← NNN AC-n)

## Edge cases

One line each, naming its criterion.

## Out of scope

What this domain deliberately does not do, and which file does it.

## Code

The modules and entry points that implement it. The code is the interface: do not
copy signatures here.
