---
name: decision/rs-realign-runner
description: Internal runner for the Decision RS global gate.
meta-skill-version: 1.0.0
---

# rs-realign-runner

Serially realign downstream decision state after an upstream conclusion changes.
Complete when the affected boundary and Register dispositions are confirmed,
stale state is committed, and one recovery route is selected.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/decision`
- A routing trigger supplied the upstream-change reason.
- No spine `gate-close` occurs until RS returns.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$RS_COMMIT` | `$GATE_CONTROL rs-commit --gate "<G>" --operations '<json array>'` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |
| `$BATCH_RECLOSE` | `$GATE_CONTROL batch-reclose --payloads '<json object>'` |

Subcommand and stdout contracts: module docstring / `--help`.

## Cognitive map

### Decision model

- **Align point** — the earliest affected gate in `Q / GL / E / D / X`.
- **Register disposition** — label every Prior and Assumption entry:
  - In the realign scope, an entry currently shown as verified defaults to
    `[pending review]`.
  - All other entries default to `[verified]`.
  - Semantic relevance may override either default.
  - `[verified]` / `[pending review]` retain the entry; `[invalid]` deletes it.
- **Recovery route** — after commit, choose exactly one:
  - **Batch** for a claimed light patch accepted by the user.
  - **Per-gate** otherwise.

### Bounds

- The user confirms the align point and all Register operations before commit.
- Prior may change between `pending` / `verified`; Assumption progress remains
  `risk_state`, so RS may only retain or delete Assumption rows.
- RS does not edit or delete `C#`. Constraint revise/remove is G0
  `$REGISTER_COMMIT`.
- `$RS_COMMIT` owns stale marking and persistence. Do not edit session data,
  delete payloads, call `stale-from` separately, or enumerate downstream gates.
- Surviving Assumption risk facts remain intact. RS does not invent or rewrite
  `completed`; stale R review belongs to the R runner.
- Batch starts only after the recovery-route choice.

## Pipeline

**Entry**

1. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
3. From the routing trigger and `$CTX`, propose the earliest align point; obtain
   user confirmation.

**Confirm**

4. Present the three-state label for every entry in both Registers, including
   any semantic override of the defaults.
5. Revise until the user confirms the complete disposition. Translate only the
   confirmed Prior state changes and deletions into operations.

**Commit**

6. Run `$RS_COMMIT`. Pin its stdout as the new `$CTX`.
7. Non-zero exit → stop, report the error, and wait for user direction.

**Route**

8. State whether the change is a light patch and why; ask Batch vs Per-gate.
9. Batch → follow `$SKILL_DIR/references/rs-stale-batch-confirm.md`; return its
   `BATCH_COMPLETE`.
10. Per-gate → return `RS_COMPLETE reenter=<G>`; the kernel loads that stale
    gate's runner.

**Stop**

- Align point, Register disposition, or route cannot be judged.
- User has not confirmed the pending decision.
- Any control command fails.

## Exit

`RS_COMPLETE reenter=<G>` · `BATCH_COMPLETE active_gate=<G>` ·
`RS_FAILED reason=<brief description>`
