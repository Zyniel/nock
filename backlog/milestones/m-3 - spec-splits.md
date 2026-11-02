---
id: m-3
title: "Spec splits"
---

## Description

- Problem: eight domain specs are past the budget of `specs/_map.md` (about 15 KB and 20 criteria): account 34 criteria, board 29, shell 28, hints 25, operations 25, realtime 24, grid-files 21, joining 21. Every role reads the whole domain file of its task, so each of these costs every later agent more tokens, and `_map.md` asks for a split before their next criterion.
- Size: L (8 tasks), in this order: B-056 grid-files, B-057 realtime, B-058 shell, B-059 joining, B-060 hints, B-061 board, B-062 account, B-063 operations.
- In scope: each task moves one coherent part of one file into a new domain file (the Plan agent's options, the lead's picks):

  | Task | From | New file | What moves | Criteria after (old / new) |
  | --- | --- | --- | --- | --- |
  | B-056 | `content/grid-files.md` | `content/ipuz.md` | the file format and its reader and writer | 7 / 14 |
  | B-057 | `platform/realtime.md` | `platform/reconnection.md` | stale edits, the resume window, the page's connection, retries, resends | 19 / 5 |
  | B-058 | `client/shell.md` | `client/foundation.md` | state lines, motion, tokens, fonts, icons, components, the focus ring, what a frame redraws | 14 / 14 |
  | B-059 | `lobby/joining.md` | `lobby/summaries.md` | the summaries route and « Mes salons » | 18 / 3 |
  | B-060 | `gameplay/hints.md` | `gameplay/votes.md` | the vote and its banner | 16 / 9 |
  | B-061 | `gameplay/board.md` | `gameplay/viewport.md` | the grid's drawing, cursors, fit, zoom, following the selection, hyphen edges | 12 / 18 |
  | B-062 | `account/account.md` | `account/erasure.md` | erasure, what is kept, history records, grid progress | 20 / 14 |
  | B-063 | `admin/operations.md` | `admin/ops-page.md` | the replay's edits and the `/ops` page | 15 / 10 |

  A moved criterion takes the next free number of its new file and its tests are renamed and moved; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps are allowed, as account's rules 26 to 28 already are), so `_settings.md` and `product.md`'s baselines stay as they are. Each task adds its row and glossary line to `_map.md` and repoints the one other file that cites what moved by number.
- Out of scope: any change of behaviour or code; the files at the budget but not past it (chat, results, presence, hud, host); account's sheet and page, the next cut if account grows again; the one-line citations by name the splits leave in host, lifetime, results, library, hud, chat and room, which one Upkeep chore repoints after the last split (B-064).
- Look: none.
- Risks: architecture: eight new domains, which this merge approves. No stored data, protocol message, close code or baseline changes. The spec-writer runs on Fable at high effort; no implementer (the code does not change).
- Questions for you:
  1. `product.md`'s routes table names `lobby/joining.md` as the owner of `POST /api/rooms/summaries`, which B-059 moves to `lobby/summaries.md`. A (lead's pick): B-059 updates that one cell, no behaviour change. B: leave it, joining's Out of scope pointing to summaries.
