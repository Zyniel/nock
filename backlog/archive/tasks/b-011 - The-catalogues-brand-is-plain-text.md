---
id: B-011
title: The catalogue's brand is plain text
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels:
  - domain:shell
  - domain:library
dependencies: []
ordinal: 21000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human approved the brief, its answers and the spec
  change, 2026-10-25; library keeps 21 criteria; review approved in round 1)
- Domains: client/shell, content/library
- Architecture decision: no
- Criteria: library AC-19, AC-20 (changed), AC-21 (new); shell rule 17
  (changed, no criterion)
- Branch: feat/b-011-catalogue-brand · PR: #50 (merged)
- Problem: B-010 made the brand a link to `/` on every top bar that shows it,
  the catalogue included (with `aria-current="page"`). The human decided: the
  Nock mark and « Nock » bring back to the catalogue on any page other than
  the catalogue, the grid page `/g/<n>` and the room included; on the
  catalogue itself they are "simply a plain text + logo".
- In scope: on `/` the brand is the mark and « Nock » as plain text: not a
  link, not a Tab stop, no `aria-current`, no name of its own (it reads
  « Nock »), no hover look. Everywhere else it stays the link « Accueil » to
  `/` (B-010). A criterion that the grid page's brand is that link, which
  B-010 left untested.
- Out of scope: any other page's brand; the name « Accueil ».
- Screens: the catalogue's top bar. The look at rest does not change; only
  the hover and focus states go away there. One option, the human's: the
  brand on `/` as it was before B-010 (`_design/foundation.md` « Brand link »
  no longer applies on the catalogue; `_design/pages.md` « Catalogue »).
- Answers (the human, 2026-10-25): library AC-20 checks the hover look on
  the grid page `/g/<n>`; `/ops` keeps the link, as any page other than `/`.
<!-- SECTION:DESCRIPTION:END -->
