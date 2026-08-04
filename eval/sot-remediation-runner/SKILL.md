---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Per-dimension SoT remediation runner. Escalates defective SoTs and prepares
  diffs only for user-reclassified artifact defects.
---

# sot-remediation-runner/SKILL.md

Terminal runner subagent. Resolve SoT issues for one dimension using only the
operation context supplied by Eval orchestration.

## Script Macros

| Macro | Command |
|-------|---------|
| `$READ_B_SNAPSHOT` | `$EVAL_CONTROL read-b-snapshot --dimension-token "$DIMENSION_TOKEN"` |
| `$SUBMIT_REMEDIATION_DIFF` | `$EVAL_CONTROL submit-remediation-diff --payload-file "$REMEDIATION_PAYLOAD"` |

## Workflow

1. Use the authorized pending SoT issues from the operation context.
2. Escalate defective SoTs without submitting an artifact diff.
3. Only a user-reclassified artifact defect may continue:
   1. Run `$READ_B_SNAPSHOT`.
   2. Prepare a targeted unified diff against the returned B snapshot. Retain
      exact original context; do not search-and-replace repeated text.
   3. Create the control-compatible remediation payload, then run
      `$SUBMIT_REMEDIATION_DIFF`.
4. On a non-zero control result, stop and report it to the parent.

## Constraints

- Do not write Eval artifacts or state directly.
- Eval control owns artifact publication, disposition, and state updates.
- Do not dispatch subagents.
