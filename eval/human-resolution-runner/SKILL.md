---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Per-dimension human-resolution runner. Captures authorized human decisions
  without modifying the evaluation target.
---

# human-resolution-runner/SKILL.md

Terminal runner subagent. Resolve one dimension's human-owned findings using
only the operation context supplied by Eval orchestration.

## Script Macros

| Macro | Command |
|-------|---------|
| `$READ_B_SNAPSHOT` | `$EVAL_CONTROL read-b-snapshot --dimension-token "$DIMENSION_TOKEN"` |
| `$SUBMIT_HUMAN_RESOLUTION` | `$EVAL_CONTROL submit-human-resolution --payload-file "$RESOLUTION_PAYLOAD"` |

## Workflow

1. Read the authorized pending findings from the operation context.
2. For each finding, present the evidence and obtain the required human
   resolution.
3. Use `$READ_B_SNAPSHOT` only when needed to explain B context; do not draft a
   B edit.
4. Create the control-compatible resolution payload, then run
   `$SUBMIT_HUMAN_RESOLUTION`.
5. On a non-zero control result, stop and report it to the parent.

## Constraints

- Do not choose among materially different implementations for the user.
- Do not prepare or submit a unified diff.
- Do not write Eval artifacts or state directly.
- Eval control owns resolution publication, disposition, and state updates.
- Do not dispatch subagents.
