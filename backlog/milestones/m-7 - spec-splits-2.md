---
id: m-7
title: "Spec splits 2"
---

## Description

- Problem: eight domain specs are past the budget of specs/_map.md (about 15 KB and 20 criteria), measured on main 2026-11-05: client/hud.md 22.4 KB and 22 criteria, social/chat.md 21.5 KB and 23, gameplay/results.md 19.4 KB and 23, lobby/host.md 18.5 KB and 22, account/account.md 18.9 KB and 20, social/presence.md 18.1 KB and 20, platform/server.md 17.3 KB and 23, content/library.md 17.0 KB and 25. Every new criterion in them makes an agent read more, and the next tasks of « Tidy specs and code » touch hud and results.
- Size: L (8 tasks): B-080 to B-087, one split per spec, from DRAFT-058.
- In scope: each spec gives one part (its rules, criteria and Code lines) to a new domain spec, numbers kept by moving criteria as they are, as « Spec splits » did (B-056 to B-063); _map.md's domain table and citations follow. The cut of each is an architecture decision: the Plan agent proposes it at the task's start and the lead picks; the spec-writer's earlier proposal for chat is social/stream (rules 18 to 20); account's is its sheet and page.
- Out of scope: any behaviour change; product.md (DRAFT-052: its baselines are the human's); specs at or just under the budget (realtime, co-op, rules, joining, catch-up, overrides, viewport).
- Look: none.
- Risks: architecture (eight new domains; the human's bet covers adding them).
- Bet: the human, in chat, 2026-11-05 (« Create a milestone for all housekeeping tasks and queue it »). Queued after « Owner's calls » and Upkeep; the three housekeeping milestones run in this order: Spec splits 2, Tidy specs and code, Tidy tests and tooling.
- Questions for you: none.
