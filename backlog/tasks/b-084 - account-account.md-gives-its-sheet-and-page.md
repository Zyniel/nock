---
id: B-084
title: account/account.md gives its sheet and page
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T21:35:00Z'
labels:
  - domain:account
milestone: m-7
dependencies: []
documentation:
  - specs/account/account.md
  - specs/account/my-account.md
priority: medium
ordinal: 72000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. account is 18.9 KB with 20 criteria (17.6 KB once B-078 is merged); its sheet and page are the next cut. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 account.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 account AC-12, 16-18 and 31-34 move to account/my-account.md as my-account AC-1 to AC-8, with their tests renamed to tests/test_my_account_*.py
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
The new account/my-account.md (domain my-account) takes the client side of the account, the « Compte » sheet and the « Mon compte » page: account rules 13-17 as my-account rules 1-5, and AC-12, 16-18, 31-34 as my-account AC-1..8. The Look section moves. Three test files move to tests/test_my_account_*.py. Repoint _map.md (row, shared list, glossary), _settings.md, product.md, shell.md, hud.md, menus.md, library.md, summaries.md and erasure.md, plus menus_harness.py and the overrides tests. gate.py: RoomMenu.svelte swaps account for my-account.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut 1 (rules 13-17) over Cut 2 (rules 14-17). Rule 17 undoes what rule 13 builds, so they belong together, and the cut keeps CataloguePage.svelte out of the shared-components map. account.md ends a server spec near 10.6 KB with 9 criteria. Domain name: my-account, after « Mon compte », instead of the proposed screens, which says little among the domains; its test prefix my_account_ clashes with none.

Spec-checker APPROVED in one round. Not taken, all optional: adding room to the Look column of my-account's _map.md row, and the account citation in library's Depends on.

Reviewer round 1: APPROVE. Its quick gate passed (account, my-account in Chromium). Not taken, all optional: claude_docs/frontend-review.md is a dated report; the Look column of my-account's _map.md row; window sizes named in AC-2, 4 and 8, copied as they were and recorded for the m-7 close's follow-up drafts.

Full gate here (Chromium): static checks, 8,774 parallel and 162 serial tests, all green. Main then brought B-085, and two files conflicted. In gate.py, RoomMenu.svelte is now authorship, menus, my-account and rules. In _map.md, the shared-criteria list keeps both sides' entries. Traceability, shared components, ruff and black passed again. Firefox and WebKit are left to CI after the merge, since only tests were renamed.

Pull request #150, auto-merge on.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
account/account.md gives its client side to the new account/my-account.md (domain my-account): the « Compte » sheet, the « Mon compte » page, and what the device stores and forgets for the account. Account rules 13-17 become my-account rules 1-5, and account AC-12, 16-18 and 31-34 become my-account AC-1..8. The Look section moves too. account.md is a server spec of 10.4 KB with 9 criteria; my-account.md is 8.9 KB with 8. Three test files move to tests/test_my_account_*.py with renumbered names and unchanged bodies. _map.md (row, shared list, glossary), citations in nine specs and two test docstrings follow, and gate.py's shared-component map gains my-account.
<!-- SECTION:FINAL_SUMMARY:END -->
