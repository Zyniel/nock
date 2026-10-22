---
name: new-spec
description: Create a numbered draft spec in specs/ from a feature description, then stop for human approval.
argument-hint: [feature description and acceptance criteria]
disable-model-invocation: true
---

# Create a spec

The user wants a new spec for this feature:

$ARGUMENTS

You are the lead. The spec-writer agent writes the file; you carry messages
between it and the user, because the agent cannot ask the user anything itself.

1. Delegate to the `spec-writer` agent. Pass it the feature description above word
   for word, including any acceptance criteria the user already wrote. It does not
   see this conversation, so do not summarise.
2. When it returns, show the user the path of the new spec, the acceptance
   criteria and the open questions.
3. If there are open questions, ask the user. Send the answers back to the same
   `spec-writer` agent so it updates the spec, then show the result again.
4. If the spec-writer redrew screens (its report says so), rebuild the screens
   sheet with `uv run python docs/design/screens_sheet/build.py` and check that
   `uv run python docs/design/screens_sheet/build.py --check` passes.
5. Stop here. The spec stays `status: draft` until the user has read it and tells
   you it is approved. When they do, change the status line to `status: approved`
   and tell them the next step: `/feature specs/<file>`.

Do not start writing tests or code from this command.
