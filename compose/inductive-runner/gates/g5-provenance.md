> Part of inductive-runner · loaded only when `$CTX.active_gate` is `G5`

# Gate 5 — External Audit

Name deviations between the current facts and Opens and their upstream
references. Record a soft provenance receipt without fixing decisions or
collecting sign-off.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |
| `$PROVENANCE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/provenance_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Use each control's `--help` as the command and stdout contract.

## Boundaries

- `$PROVENANCE_GATE_CTL` owns provenance context, validation, recording,
  presentation, and closure.
- `../g5-provenance-runner/SKILL.md` owns stateless A/B/C analysis.
- The Parent Agent owns dispatch and report handoff.
- G5 remains soft; detected deltas do not block closure.

## Audit

Run only when `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate=G5`.

1. Initialize or resume G5 through `$PROVENANCE_GATE_CTL`.
2. Obtain a fresh, digest-bound context through `$PROVENANCE_GATE_CTL`. It
   contains current facts and Opens plus resolved scope, intent-baseline, and
   norm-constraint content.
3. Dispatch `../g5-provenance-runner/SKILL.md` through `$SUBAGENT_TOOL` with
   `$SUBAGENT_AWAIT_SYNC`, supplying that complete context.
4. Pass the structured return unchanged to `$PROVENANCE_GATE_CTL` for
   validation and recording.
5. Call `$PROVENANCE_GATE_CTL present` and show the complete delta receipt.

On runner failure or invalid output, record nothing. Report the failure or
retry from fresh context.

## Close

Call `$PROVENANCE_GATE_CTL gate-close`. It presents the receipt and closes G5,
including when the receipt has no deltas.

## Return

Report delta counts by upstream role, then return control to Compose Writing.
