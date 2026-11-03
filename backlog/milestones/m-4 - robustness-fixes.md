---
id: m-4
title: "Robustness fixes"
---

## Description

- Problem: small defects the reviews found and left as drafts: two server slips (DRAFT-027, 028), chat texts that can show reversed (029), grid files the converter or the index accept wrongly (004, 005, 006), « Mes salons » reading dates leniently and an unreachable status still required (057, 020), status regions that keep stale news for screen readers (054).
- Size: M (5 tasks): B-066, B-067, B-068, B-069, B-070.
- In scope: the five tasks as their descriptions say. In a domain spec past the budget of specs/_map.md (chat, hud), a change widens an existing criterion rather than adding one.
- Out of scope: DRAFT-042 (sign-out forgetting grid marks: players notice it, a design first), DRAFT-030 (SMTP thread pool), dependency patches (DRAFT-061).
- Look: none (B-070 changes what a screen reader hears, not what is drawn).
- Risks: none (no stored data, protocol message or dependency).
- Bet: the human, in chat, 2026-11-03 (« Regroup tasks under specific milestones and run those »).
- Questions for you: none.
