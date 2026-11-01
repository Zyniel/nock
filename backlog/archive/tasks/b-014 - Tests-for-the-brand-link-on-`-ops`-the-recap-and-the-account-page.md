---
id: B-014
title: Tests for the brand link on `/ops`, the recap and the account page
status: Done
assignee: []
created_date: '2026-11-01T16:43:00Z'
labels:
  - domain:shell
  - domain:operations
dependencies: []
ordinal: 24000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done (the human picked option A and one state per page, and
  approved the spec change, 2026-10-25; review approved in round 1; no
  implementation step: the tests passed as written)
- Domains: client/shell, admin/operations
- Architecture decision: no (criteria and tests only; no behaviour, code or
  look changes)
- Criteria: shell AC-10 (changed), operations AC-13 (changed)
- Branch: feat/b-014-brand-link-tests · PR: none yet
- Problem: `client/shell.md` rule 17 makes the brand the link « Accueil » to
  `/` on every top bar that shows it but the catalogue's. Criteria prove it on
  the entry frame of a room (shell AC-10), the room's computer top bar (hud
  AC-2) and the grid page (library AC-21), but not on the shared recap
  `/recap/<token>`, the account page `/account` or the operator page `/ops`.
  All use `TopBarBrand` today, so nothing is broken, but a brand drawn another
  way there would go unseen.
- In scope: the link, its name « Accueil », its target `/` and no
  `aria-current`, on those three pages, at a computer and a phone window. The
  recap and account pages share the entry frame (shell rule 9), whose page
  frame `gameplay/results.md` and `account/account.md` leave to
  `client/shell.md`; `/ops` uses the catalogue's frame, and its page belongs
  to `admin/operations.md`.
- Out of scope: any change of behaviour or look; the brand's name (the
  label-in-name follow-up); following the link (B-010 and B-011 test that it
  loads `/`).
- Screens: none.
- Options (the three files are at 20 criteria and over 15 KB, so no new
  criterion is wanted):
  - A. Extend two criteria in place: shell AC-10 names the recap and account
    pages besides `/r/ZZZZZZ`; operations AC-13 says the `/ops` bar's brand is
    the link « Accueil » to `/`. The tests behind their pointers (046 AC-1,
    048 AC-6) are edited in place.
  - B. One new criterion per page's domain (results, account, operations).
    Puts each check by its page, but takes all three files over their budget.
  - C. One new criterion in `client/shell.md`, rule 17's owner, for all
    three pages. Puts shell at 21 criteria and over 16 KB.
  - Lead's pick: A. The checks sit with the criteria that already prove each
    frame, and no file grows.
- Answers (the human, 2026-10-25): option A; one state per page: the recap
  loaded, the account page signed out, `/ops` locked.
<!-- SECTION:DESCRIPTION:END -->
