---
id: doc-003
title: Grid engine and ipuz
type: other
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T16:44:00Z'
---
What the ipuz standard can describe and the grid engine does not use yet is kept
as drafts labelled `idea`. One becomes a task only through a milestone.

To keep the engine free of ipuz, each idea adds a concept to Nock's own model
first (`src/nock/grid.py`), and only `nock.ipuz` maps the ipuz field onto it:
another file format could fill the same concept, and the rooms, the protocol and
the browser never see ipuz.

Not taken from ipuz: its `checksum` (the server needs the answers for check and
reveal), `references` and `continued` (rare in arrowwords), and image clues (the
product serves no third-party content). Arrows stay Nock's own: ipuz has none.
