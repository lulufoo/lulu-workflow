---
name: decision/dc-delivery-runner
description: Internal runner for the Decision DC gate.
meta-skill-version: 1.0.0
---

# dc-delivery-runner

Verify that the decision meets delivery conditions and obtain the user's delivery
confirmation. Complete when the user confirms the decision is correct to deliver.

## Script Macros

| Macro | Command |
|-------|---------|
| `$DEC_EVAL` | `python3 "$DECISION_SKILL_DIR/scripts/dec_eval_control.py" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$SESSION_INTEGRITY` | `python3 "$DECISION_SKILL_DIR/scripts/dec_session_integrity.py" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`. `$SUBAGENT_*`: `_subagent.md`.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `DC`, R exit `dc`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Must hold

| ID | Must hold |
|----|-----------|
| `G-cleared` | Delivery preconditions hold: structural audit clean, Decision Eval pass, delivery `decision-doc.md` rendered. |
| `G-confirm` | User confirms the decisions are correct to deliver (after any realign). |

## Present

1. `$SESSION_INTEGRITY render` once before `present`. Layout / section set: `render --help`. Template: `$DECISION_SKILL_DIR/templates/decision-doc.template.md`.
2. Show the rendered doc; omit file paths.
3. After close, do not announce stage Delivered or next stages.

## Eval

Eval owns probe-runner dispatch; Decision never dispatches Eval runners or remediation. Contracts: `eval/eval-profile.json`, `$DEC_EVAL` / `$EVAL_CONTROL` `--help`, `eval/methods/decision-consistency.md`.

1. Pin `$EVAL_ADAPTER_CONFIG` = `$DECISION_SKILL_DIR/eval/eval-profile.json`.
2. Load `$SKILL_ROOT/eval/SKILL.md` and execute its **Begin Eval** probe-only
   segment.
3. Pin the successful `complete-probe-only` JSON as `probe_result`.
4. Run `$DEC_EVAL route-probe-result --probe-result-json '<probe_result JSON>'`.
   - `outcome: pass` → continue to `$SESSION_INTEGRITY render`.
   - `outcome: fail` → RS at `realign_gate`; do not present completion.

## Modes

| Mode | When | Behavior |
|------|------|----------|
| `prepare` | `G-cleared` unmet | `$GATE_CONTROL check-delivery-ready` (fix all errors) → Eval → `$SESSION_INTEGRITY render`. |
| `present` | `G-cleared` met | Show the rendered doc. |
| `confirm` | `G-cleared` met | Ask whether decisions are correct / any item to realign. |
| `close` | User confirms | `$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'` → `$GATE_CONTROL complete` |

## Signals

Apply Decision [Signals](../../SKILL.md#signals) throughout DC.

## Routes

- Confirm-time realign → load RS runner; after sync, `$GATE_CONTROL resolve-context` (fresh `$CTX`); restore `G-cleared` / `G-confirm` before close.

## Act

1. If `$CTX.gates.DC.status == stale`, follow
   `$DECISION_SKILL_DIR/references/rs-stale-gate-update.md` Assess only, then
   continue.
2. Loop Modes (Signals and Routes as above) until `close` succeeds.

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE DC Completed` · `GATE_FAILED DC reason=<brief description>`
