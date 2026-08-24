---
name: decision/rs-realign-runner
description: Internal runner for the Decision RS global gate.
meta-skill-version: 1.0.0
---

# rs-realign-runner

Serially realign downstream decision state after an upstream conclusion changes.
Complete when the affected boundary and Register dispositions are confirmed,
stale state is committed, and one recovery route is selected.

## Script Macros

| Macro | Command |
|-------|---------|
| `$GATE_CONTROL` | `python3 "$SKILL_DIR/scripts/dec_gate_control.py" --project-root "$(pwd)" --cycle-id "<cycle_id>" --constraints "<constraints_path>"` |
| `$RS_COMMIT` | `$GATE_CONTROL rs-commit --gate "<G>" --operations '<json array>'` |
| `$GET_PAYLOAD` | `$GATE_CONTROL get-payload` |
| `$BATCH_RECLOSE` | `$GATE_CONTROL batch-reclose --payloads '<json object>'` |

Subcommand and stdout contracts: module docstring / `--help`.

## Prerequisites

- A routing trigger supplied the upstream-change reason.
- No spine `gate-close` occurs until RS returns.
- Run `$GATE_CONTROL resolve-context`; pin `$CTX`.
- Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
  `domain.instruction`) to the dialogue.

## Align

The earliest affected gate in `Q / GL / E / D / X`. The user confirms the align
point before commit.

## Disposition

Label every Prior and Assumption entry:

- In the realign scope, an entry currently shown as verified defaults to
  `[pending review]`.
- All other entries default to `[verified]`.
- Semantic relevance may override either default.
- `[verified]` / `[pending review]` retain the entry; `[invalid]` deletes it.

Prior may change between `pending` / `verified`. Assumption progress remains
`risk_state`, so RS may only retain or delete Assumption rows.

RS does not edit or delete `C#`. Constraint revise/remove is G0
`$REGISTER_COMMIT`.

Surviving Assumption risk facts remain intact. RS does not invent or rewrite
`completed`; stale R review belongs to the R runner.

## Recover

After commit, choose exactly one:

- **Batch** for a claimed light patch accepted by the user.
- **Per-gate** otherwise.

Batch starts only after this choice.

## Act

1. From the routing trigger and `$CTX`, propose the earliest align point; obtain
   user confirmation.
2. Present the three-state label for every entry in both Registers, including
   any semantic override of the defaults.
3. Revise until the user confirms the complete disposition. Translate only the
   confirmed Prior state changes and deletions into operations.
4. Run `$RS_COMMIT`. Pin its stdout as the new `$CTX`. `$RS_COMMIT` owns stale
   marking and persistence. Do not edit session data, delete payloads, call
   `stale-from` separately, or enumerate downstream gates.
5. Non-zero exit → stop, report the error, and wait for user direction.
6. State whether the change is a light patch and why; ask Batch vs Per-gate.
7. Batch → follow `$SKILL_DIR/references/rs-stale-batch-confirm.md`; return its
   `BATCH_COMPLETE`.
8. Per-gate → return `RS_COMPLETE reenter=<G>`; the kernel loads that stale
   gate's runner.

Stop if the align point, disposition, or route cannot be judged; the user has
not confirmed the pending decision; or any control command fails.

## Exit

`RS_COMPLETE reenter=<G>` · `BATCH_COMPLETE active_gate=<G>` ·
`RS_FAILED reason=<brief description>`
