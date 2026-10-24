# Nock agentic development model for a public app

This document applies the safe, product-first operating model we discussed to the current `Zyniel/nock` repository.

The repository already contains many of the right ingredients:
- a spec-first workflow
- a design reference (`specs/_design.md`, `docs/design/`)
- a test-driven gate (`scripts/gate.py`)
- review-oriented agent roles in `.claude/agents/`
- strong quality gates through Python, TypeScript, Svelte and browser tests

The missing layer is not more tooling. It is a clear separation between:
- product ideas
- design proposals
- approved design contracts
- spec behavior
- implementation
- release validation

Without that boundary, Claude can drift, broaden scope, or subtly change the live product while trying to be helpful.

## 1. The key design choice

For a public app that you will not maintain yourself, the repo must act like a controlled production system, not a living sandbox.

The AI is allowed to:
- propose ideas
- create specs from approved directions
- write tests
- implement within a defined contract

The AI is not allowed to:
- mutate the live UX without human approval
- broaden the scope of a feature casually
- redesign the app from a vague requirement
- silently change the approved design contract

## 2. Product layers

We want four layers, each with different responsibilities.

### 2.1 Product contract
This is the stable “what this app is” layer.

It should answer:
- what problem the app solves
- what user flows are core
- which routes and flows are stable
- what is out of scope
- what browser and accessibility standards are required
- what release criteria are required

This is not a design doc; it is a product guarantee.

### 2.2 UX / design contract
This is the approved visual and interaction contract.

It should answer:
- which screens and states are approved
- what the layout hierarchy is
- which design tokens are fixed
- which flows are not allowed to drift
- which routes, states and actions are protected

This layer is the real barrier against “Claude redesigns the app while implementing a feature.”

### 2.3 Feature/spec contract
This is the behavior contract.

It should answer:
- what the feature does
- what is in scope
- what is out of scope
- acceptance criteria
- edge cases and failure modes
- expected public interface

This layer should continue to live in `specs/`.

### 2.4 Implementation
This is the code layer.

It includes:
- `src/nock/`
- `web/src/`
- tests
- scripts
- automation

Implementation must never move outside the approved design and spec contract.

## 3. The current Nock repo already has the right raw ingredients

This repo already has important strengths:
- spec-first process
- design references and visual documentation
- strong tests and gate scripts
- role separation between spec, tests, implementation and review
- very explicit product rules in `CLAUDE.md`

But the repo currently blends too much together:
- design docs are effectively part of the working loop
- broad feature proposals can mutate the live product direction
- higher-level product governance is not clearly separated from implementation

This is safe for a controlled, internal AI build. It is not ideal for a public app with long-term product stability and weak manual maintenance.

## 4. The new operational model for Nock

### 4.1 Backlog.md: the active work queue
Create a root `Backlog.md` that is the only place where active work is tracked.

Suggested structure:

```md
# Backlog

## Goals
- Keep the product stable
- Prefer small approved changes over broad redesigns
- Every feature must be linked to a design approval and a spec

## Priority
- P0: safety, correctness, critical flow
- P1: user-facing quality, core feature improvements
- P2: polish and UX improvements
- P3: experiments and optional ideas

## Items
### [ID] Title
- Status: proposed | approved | in progress | blocked | review | done
- Priority: P0/P1/P2/P3
- Area: backend | frontend | design | infra | tests
- Target release: vX.Y
- Problem: short statement
- Scope: in scope
- Out of scope: explicit exclusions
- Approved design: docs/design/approved/...
- Spec: specs/NNN-...
- Dependencies: ...
- Notes: ...
```

This is the source of task selection for Claude. It should not be a giant unbounded document: it should be short, structured, easy to scan.

### 4.2 Design proposals: brainstorming only
Add a folder like:

```text
docs/design/proposals/
```

Each proposal file is a design option, not a live design contract.

Example:

```md
# Design Proposal: Room Join Redesign

## Summary
Short statement of the idea.

## Problem
What user pain point this solves.

## Options
### Option A: minimal summary card
### Option B: full landing panel
### Option C: hybrid

## Recommendation
Which option is better and why.

## Constraints
- keep current shell structure
- do not change core game rules
- preserve accessibility baseline

## Approval
- Status: proposed | approved | rejected
- Approved by: human
- Date:
```

This is where Claude can propose ideas without mutating the working app.

### 4.3 Approved design contract
Add a folder like:

```text
docs/design/approved/
```

Each approved design file becomes the product design contract for a feature.

Example structure:

```md
# Approved Design: Room Join V2

## Status
Approved

## Screens affected
- room code entry
- summary card
- join confirmation state

## Visual rules
- keep current shell and top bar
- no new icon families
- preserve layout hierarchy

## Interaction rules
- one-click join from summary state
- visible primary CTA
- keyboard focus order preserved
- no auto-submit without confirmation

## Accessibility
- focus ring visible
- keyboard navigation works
- screen-reader labels retained
- contrast rules unchanged

## Out of scope
- no full room redesign
- no rule changes

## Implementation constraints
- only touch join and summary flow
```

This file is the design “law” for the implementation agent.

### 4.4 Spec-driven implementation remains required
Keep `specs/` as the behavior contract.

The rule becomes:
- the backlog item must point to an approved design file and a spec
- implementation cannot start without both
- if a feature is vague, Claude must ask for a brief or stop

This is the product-safety boundary.

## 5. Review model for the current repository

The current repo already has reviewer agents, but for your use case they must be more explicit and more layered.

### 5.1 Role split
Use at least three review roles:

- `design-reviewer`
  - checks that implementation matches the approved design contract
  - blocks arbitrary redesigns
  - checks route and state consistency
- `spec-reviewer`
  - checks feature behavior against the spec and acceptance criteria
  - checks edge cases and hidden scope creep
- `qa-reviewer`
  - runs the staged gate and checks regression risk

### 5.2 Review principles
Every review should check:
- is the change approved?
- is it linked to a backlog item?
- does it respect the approved design contract?
- does it stay within the feature scope?
- does it violate current UX or route contract?
- is there a test for each acceptance criterion?
- is the quality gate green?

The review process is not just “is the code correct?” It is “is the product contract respected?”

## 6. GitHub workflow to support this model

GitHub should be the governance layer for the process.

### 6.1 GitHub Project or Projects v2
Create a project board with columns like:
- Idea
- Proposal
- Approved
- Spec Ready
- In Progress
- Review
- Blocked
- Done
- Released

Add fields:
- Priority
- Area
- Design link
- Spec link
- Release target
- Risk
- Human approval

This gives you a visual board for the backlog and the process.

### 6.2 Issues as proposals and tasks
Use issue templates for:
- Feature request
- Design proposal
- Bug report
- Spec request

Each issue should force fields like:
- goal
- user problem
- in scope
- out of scope
- constraints
- linked design approval
- linked spec
- release target

This is how you feed the ideation into Claude in a consistent way.

### 6.3 PRs as implementation gates
Every PR should require:
- linked issue
- linked approved design doc
- linked spec
- release or risk label
- review approval
- required status checks

This stops scope drift from turning into a casual change.

### 6.4 Branch protection
Enable branch protection on `main`:
- require PRs
- require passing checks
- require review before merge
- enforce conversation resolution
- prevent direct pushes
- prevent force pushes

### 6.5 CODEOWNERS
Protect ownership boundaries:

```text
/src/ @owner-backend
/web/ @owner-frontend
/specs/ @owner-product
/docs/design/ @owner-design
/.claude/ @owner-tooling
/scripts/ @owner-tooling
```

This matters a lot when Claude is operating inside a repo with a public product surface.

### 6.6 Actions and gates
Use GitHub Actions to run the repo quality gate on PRs and main.

The minimum good gate should include:
- Python lint and formatting
- pyrefly or equivalent type check
- pytest
- web static check
- web build
- browser smoke test for key routes
- targeted regression only for changed screens

This mirrors the design of `scripts/gate.py` and keeps the local Claude workflow aligned with CI.

### 6.7 Releases
Use GitHub Releases for product baselines.

Examples:
- `v1.1.0` stable release
- design baseline snapshot
- security and compatibility note

This is how you freeze and know what is stable before starting another round of agentic work.

## 7. How to feed ideas into the system

You do not want to give Claude a vague requirement like “improve the flow.”

You should give Claude a structured brief like this:

```md
# Feature brief

## Goal
What user problem are we solving?

## In scope
- ...

## Out of scope
- ...

## Constraints
- preserve current product shell
- do not change core game rules
- maintain accessibility baseline

## Approved design
docs/design/approved/...

## Related spec
specs/NNN-...

## Success criteria
- ...

## Risks
- ...
```

If there is no approved design or spec, the work is still in proposal mode and should not be implemented yet.

## 8. The recommended workflow for Nock

### Phase 1: Stop broad design drift
Create:
- `Backlog.md`
- `docs/design/proposals/`
- `docs/design/approved/`
- `docs/release/`
- GitHub Project board

### Phase 2: Use GitHub as the approval system
Create issue templates and fill a backlog.

### Phase 3: Use Claude in bounded mode
When a feature is approved:
1. read the backlog item
2. read the approved design contract
3. read the linked spec
4. write tests
5. implement only the approved scope
6. run the gate
7. request review

### Phase 4: Freeze the stable product baseline
At a milestone like `1.1.0` or `PR048`, create a release baseline and a stable product contract.

Then start the next cycle from the stable baseline, not from the same open-ended design environment.

## 9. The core rule to keep

The repo should be driven by this principle:

Approval before implementation.
Design before feature.
Spec before tests.
Gate before merge.
Release before product expansion.

That is the safe, durable model for a public app when you do not maintain the code yourself.

## 10. Minimum things to add immediately

The smallest useful change set is:
- `Backlog.md`
- `docs/design/proposals/README.md`
- `docs/design/approved/README.md`
- GitHub Project board
- issue templates
- PR template
- main branch protection
- CODEOWNERS
- release tagging

That will give Nock a much healthier development model without throwing away the work already done.

## 11. Final assessment

The current repository is already strong in two areas:
- spec-driven behavior
- structured quality gates

What it lacks is a clean separation between:
- proposal
- approval
- contract
- implementation

That separation is what makes a public app sustainable when the human owner is not the maintainer.

This is the change we should add to Nock next.
