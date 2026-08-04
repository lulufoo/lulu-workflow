---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Per-dimension artifact remediation runner. Prepares a token-scoped unified
  diff for artifact defects; Eval control owns publication.
---

# artifact-remediation-runner/SKILL.md

Terminal runner subagent. Resolve artifact defects for one dimension using only
the operation context supplied by Eval orchestration.

## Script Macros

| Macro | Command |
|-------|---------|
| `$READ_B_SNAPSHOT` | `$EVAL_CONTROL read-b-snapshot --dimension-token "$DIMENSION_TOKEN"` |
| `$SUBMIT_REMEDIATION_DIFF` | `$EVAL_CONTROL submit-remediation-diff --payload-file "$REMEDIATION_PAYLOAD"` |

## Workflow

1. Run `$READ_B_SNAPSHOT`.
2. Use the authorized pending artifact defects from the operation context. If
   none are present, stop.
3. Prepare a targeted unified diff against the returned B snapshot. Retain exact
   original context; do not search-and-replace repeated text.
4. Create the control-compatible remediation payload, then run
   `$SUBMIT_REMEDIATION_DIFF`.
5. On a non-zero control result, stop and report it to the parent.

## Constraints

- Do not write Eval artifacts or state directly.
- Eval control owns artifact publication, disposition, and state updates.
- Do not dispatch subagents.
