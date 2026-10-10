---
id: "033"
title: Optional account
status: approved
---

# 033 - Optional account

Epic E9 Accounts and resume (US-9.2) · Release: V1 · Epic depends on: E3

## Goal

As a regular player, I want an account, so that my history follows me across devices.

The MVP ships with guests only: a guest can do everything needed to finish a grid. Accounts arrive in V1 and only add memory across devices.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-9.2.1) A guest can create an account from inside a room with an emailed link, and keeps the same seat, colour and authorship.
- **AC-2** (AC-9.2.2) No action needed to finish a grid requires an account.
- **AC-3** (AC-9.2.3) Deleting my account removes my personal data within 30 days. Other players' recaps then show "former player".

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- Payments and subscriptions (epic E9).
- Room resume: spec 032.
- Catching up after an absence: spec 034.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- Sign-in by emailed link needs an email provider, which is a new dependency to approve.
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
