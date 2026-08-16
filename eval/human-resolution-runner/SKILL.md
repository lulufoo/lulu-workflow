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
2. Present every `required_issue_id` and its evidence. Offer only the
   per-issue choices in `allowed_resolution_kinds`.
   - Artifact-class `fix`: approve a later Artifact Remediation.
   - Artifact-class `accept-divergence`: record an intentional divergence;
     this is terminal and does not edit B.
   - `select` / `allow-multiple`: resolve `DECISION-REQUIRED`.
   - `escalate`: abandon the Eval round after the complete batch is applied.
3. Use `$READ_B_SNAPSHOT` only when needed to explain B context; do not draft a
   B edit.
4. Create one batch payload containing the pinned `dimension_token`,
   `base_digest`, `review_base_digest`, and `resolutions`. The union of
   `resolutions[].issue_ids` must equal `required_issue_ids` exactly.
5. Run `$SUBMIT_HUMAN_RESOLUTION` once for the complete batch.
6. On a non-zero control result, stop and report it to the parent.

## Constraints

- Do not choose among materially different implementations for the user.
- Do not invent a disposition outside `allowed_resolution_kinds`.
- Do not use `accept-divergence` for Human-class findings.
- Do not prepare or submit a unified diff.
- Do not write Eval artifacts or state directly.
- Eval control owns resolution publication, disposition, and state updates.
- Do not dispatch subagents.
