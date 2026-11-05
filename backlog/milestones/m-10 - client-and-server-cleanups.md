---
id: m-10
title: "Client and server cleanups"
---

## Description

- Problem: follow-ups of client and server work left by reviews (B-028, B-040, B-041, B-043, B-050, B-066, B-067, spec 029): two copies of one rule, decisions with no criterion, a thread pool a slow mail server could fill, and a shared device that still shows the previous account's grids as started or finished.
- Size: L (7 tasks): B-090, B-092, B-093, B-095, B-102 (moved from « Tidy specs and code » and « Tidy tests and tooling »), B-104, B-105.
- In scope: one helper for refused characters and MAX_PLAYERS named where it lives (DRAFT-067, 069); B-040's cleanups (043); the reconnection and remote-selection follow-ups (044, 046); spec 029's leftovers (015); SMTP sends out of the sync routes' pool (030); a sign-out forgets the account's marks in nock.progress (042); the fonts' preload through a ?url import (050).
- Out of scope: the look drafts and the brand's wording.
- Look: none. B-104 is a change players notice on a shared device: after a sign-out, the catalogue no longer shows the account's grids as started or finished.
- Risks: stored data (B-104 records which marks came from the account's rooms in nock.progress: the device's storage format, the human's call, covered by this bet).
- Bet: the human, in chat, 2026-11-05 (« Queue "Create milestone from Client and server cleanups" »). Queued last, after « Tidy tests and tooling ».
- Questions for you: none.
