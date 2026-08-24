---
name: decision/dc-delivery-runner
description: Internal runner for the Decision DC gate.
meta-skill-version: 1.0.0
---

# dc-delivery-runner

Verify that the decision meets delivery conditions and obtain the user's delivery
confirmation. Complete when the user confirms the decision is correct to deliver.

## Prerequisites

- Run `$GATE_CONTROL resolve-context`; pin `$CTX` (`active_gate` is `DC`, R exit `dc`).
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$DEC_EVAL` | `python3 "$SKILL_DIR/scripts/dec_eval_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/eval/scripts/eval_entry.py" --adapter-config-file "$SKILL_DIR/eval/eval-profile.json" --project-root "$(pwd)" --cycle-id "<cycle_id>"` |
| `$SESSION_INTEGRITY` | `python3 "$SKILL_DIR/scripts/dec_session_integrity.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |

Subcommand contracts: module docstring / `--help`. `$SUBAGENT_*`: `_subagent.md`.

## Cognitive map

### Goals

| ID | Must be clear |
|----|----------------|
| `G-cleared` | Delivery preconditions hold: structural audit clean, Decision Eval pass, delivery `decision-doc.md` rendered. |
| `G-confirm` | User confirms the decisions are correct to deliver (after any realign side routes). |

### Coverage / bounds

- **Entry:** R→`dc` only.
- **Decision-doc:** not maintained during the session; `$SESSION_INTEGRITY render` builds it once before present. Layout / section filtering: `render --help`. Template: bundled at `$SKILL_DIR/templates/decision-doc.template.md` and loaded by the render command.
- **Present** (from rendered doc; do not show file paths): Direction Readiness;
  Decision Rationale; Scope (incl. exclusions); Assumptions & Risks
  (`RK#` `risk_level`, `risk_class`, `risk_state`, `release_terms` where set).
- **Eval:** replaces AI Semantic Review; invoke Eval's Probe control segment, then route its returned result through Decision. Eval owns probe-runner dispatch; Decision never dispatches Eval runners or remediation. Details: `eval/eval-profile.json`, `$DEC_EVAL` / `$EVAL_CONTROL` `--help`, `eval/methods/decision-consistency.md`.
- **After close:** do not announce stage Delivered or next stages.

### Dialogue modes

| Mode | When | Behavior |
|------|------|----------|
| `prepare` | `G-cleared` unmet | `$GATE_CONTROL check-delivery-ready` (fix all errors) → Decision Eval Probe handoff below (fail→RS; no remediation) → `$SESSION_INTEGRITY render`. |
| `present` | `G-cleared` met | Present Coverage sections from `decision-doc.md`. |
| `confirm` | `G-cleared` met | Ask whether decisions are correct / any item to realign. |
| `close` | User confirms | `$GATE_CONTROL gate-close --gate DC --payload '{"user_confirmed": true}'` → `$GATE_CONTROL complete` |

### Pass criterion

`G-confirm` with explicit user confirmation; close payload `user_confirmed: true`.

### Side routes

- Eval fail → summarize issues → RS at `realign_gate`; do not present completion.
- Confirm-time realign → load RS runner; after sync, `$GATE_CONTROL resolve-context` (fresh `$CTX`); restore `G-cleared` / `G-confirm` before close.
- G9 hit: load RS runner → after return, resume DC dialogue.
- G0 hit: load G0 runner → `G0_COMPLETE` → resume DC dialogue.

### Decision Eval Probe handoff

1. Load `$SKILL_ROOT/eval/SKILL.md` and execute its **Begin Eval** probe-only segment.
   Eval owns all probe-runner dispatch and token-based submission; Decision does
   not call `$SUBAGENT_TOOL`, load `dimension-probe-runner`, or run remediation.
2. Pin the successful `complete-probe-only` JSON as `probe_result`.
3. Run `$DEC_EVAL route-probe-result --probe-result-json '<probe_result JSON>'`.
   - `outcome: pass` → continue to `$SESSION_INTEGRITY render`.
   - `outcome: fail` → RS at `realign_gate`.

## Pipeline

**Entry:**

1. If `$CTX.gates.DC.status == stale`, follow
   `$SKILL_DIR/references/rs-stale-gate-update.md` **steps 1–3 only** (do **not**
   run that file’s step 4 `gate-close` or step 5 `GATE_COMPLETE`), then
   continue Act.

**Act:** Loop the Dialogue modes (side routes as above) until `close` succeeds,
then Exit.

## gate-close payload

```json
{"user_confirmed": true}
```

## Exit

`GATE_COMPLETE DC Completed` · `GATE_FAILED DC reason=<brief description>`
