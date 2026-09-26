---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Per-dimension remediation runner. Prepares one candidate proposal, gates
  human-gated Issues, and applies one RemediationApplication.
---

# remediation-runner/SKILL.md

Terminal runner subagent. Remediate one Dimension's pending Issues using only
the operation context supplied by Eval orchestration.

## Script Macros

| Macro | Command |
|-------|---------|
| `$READ_B_SNAPSHOT` | `$EVAL_CONTROL read-b-snapshot --operation-token "$OPERATION_TOKEN"` |
| `$PREPARE_REMEDIATION` | `$EVAL_CONTROL prepare-remediation --proposal-file "$PROPOSAL_FILE"` |
| `$APPLY_REMEDIATION` | `$EVAL_CONTROL apply-remediation --application-file "$APPLICATION_FILE"` |

## Workflow

1. Run `$READ_B_SNAPSHOT`. Read pending Issues from the operation context.
2. Build one candidate proposal covering every required Issue.
3. Run `$PREPARE_REMEDIATION`. Use the returned canonical proposal. This command is read-only.
4. If any required Issue is `human-gated`, present evidence and the proposal; wait for human confirmation or modification. If every required Issue is `direct`, the canonical proposal becomes the final result and `human_gate` is null.
5. Build one `RemediationApplication` that embeds the original proposal and the final result. A mixed batch stays one runner, one Application, and one apply.
6. Run `$APPLY_REMEDIATION` once.
7. On a non-zero control result, stop and report it to the parent.

## Constraints

- Do not write B, ReviewFile, evaluate-state, or operation records.
- Do not dispatch subagents.
- Eval control owns publication, disposition, and state updates.
