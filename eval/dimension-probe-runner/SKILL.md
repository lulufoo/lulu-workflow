---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Corpus-driven evaluation probe executor for lulu-dev-workflow. Invoked by
  Eval orchestration once per dimension.
---

# dimension-probe-runner/SKILL.md

Terminal runner subagent. Probe one dimension using only the operation context
supplied by Eval orchestration.

## Script Macros

| Macro | Command |
|-------|---------|
| `$READ_B_SNAPSHOT` | `$EVAL_CONTROL read-b-snapshot --dimension-token "$DIMENSION_TOKEN"` |
| `$READ_SOT_EVIDENCE` | `$EVAL_CONTROL read-evidence-snapshot --dimension-token "$DIMENSION_TOKEN" --evidence-ref "$EVIDENCE_REF"` |
| `$SUBMIT_PROBE_FINDINGS` | `$EVAL_CONTROL submit-probe-findings --payload-file "$FINDINGS_PAYLOAD"` |

## Workflow

1. Run `$READ_B_SNAPSHOT`; evaluate only its returned B snapshot.
2. Load the resolved method and SoT evidence from the operation context. For each
   evidence reference, run `$READ_SOT_EVIDENCE` and use its returned content and
   digest as evidence.
3. Follow the resolved method to derive findings from B and the evidence.
4. Create the control-compatible findings payload, then run
   `$SUBMIT_PROBE_FINDINGS`.
5. On a non-zero control result, stop and report it to the parent.

## Constraints

- Probe only; do not run a remediation loop or dispatch subagents.
- Eval control validates and publishes all Eval artifacts and state.
