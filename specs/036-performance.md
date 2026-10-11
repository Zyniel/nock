---
id: "036"
title: Performance
status: approved
---

# 036 - Performance

Epic E10 Quality bar (US-10.2) · Release: MVP · Epic depends on: All

## Goal

As a player on a mid-range phone, I want a responsive grid, so that typing never lags.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

Not defined yet. To write following `specs/_architecture.md` before approval.

## Acceptance criteria

- **AC-1** (AC-10.2.1) FX-02 is interactive within 2.5 seconds on a mid-range phone over 4G.
- **AC-2** (AC-10.2.2) A typed letter shows locally within 50 ms.
- **AC-3** (AC-10.2.3) With 8 players each typing 2 letters a second, spec 015 AC-1, backlog AC-4.1.1 still holds.

## Edge cases and errors

Note from the lead (2026-10-11, from the spec 037 review): the hub's per-room
inbox and per-connection outbound queues are unbounded, so a member flooding
non-edit messages, or a client that never reads its socket, can grow them
without limit; and uvicorn's default `ws_max_size` (16 MiB) receives an
oversized frame fully before spec 037 refuses it. This spec must decide bounds:
a bounded outbound queue that disconnects a stalled client, a per-connection
inbound cap, and a `ws_max_size` close to spec 037's 4096 bytes.

- AC-3 depends on behaviour owned by spec 015; test only this spec's side of it here.

## Out of scope

- Nothing stated in the backlog (epic E10).
- Accessibility: spec 035.
- Integrity: spec 037.
- Privacy and operations: spec 038.

## Work packages

None.

## Open questions

- Public interface not written yet. Write it following `specs/_architecture.md` (stack decided on 2026-10-10), and say for each criterion whether it is tested as a Python test or a browser test with pytest-playwright.
- FX-02, the full-size grid used by AC-1, is still to be chosen.
- What is the reference mid-range phone and the 4G profile for AC-1, and do these run in CI or as a manual benchmark?
- The numeric thresholds above are proposed defaults from the backlog. Confirm or adjust them before approval.
