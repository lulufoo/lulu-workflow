> Part of inductive-runner · loaded only when `$CTX.active_gate` is `G4`

# Gate 4 — Internal Audit

Audit the current facts and Opens for internal coherence. Route every finding
back through G3; G4 performs no repair.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |
| `$INDUCTIVE_RECOMPOSE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/recompose/inductive_recompose_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Use each control's `--help` as the command and stdout contract.

## Goal

Require the current facts and Opens to be:

- free of conflicts;
- buildable;
- reversible where required; and
- verifiable.

## Boundaries

- `$INDUCTIVE_RECOMPOSE_CTL` owns digest-bound audit context and report recording.
- `../recompose-runner/SKILL.md` owns the read-only whole-set analysis.
- The Parent Agent owns dispatch, report handoff, presentation, and routing.
- `$INDUCTIVE_GATE_CTL` owns Gate transitions and report-driven closure.
- G4 names findings. G3 resolves them.

## Audit

Run only when `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate=G4`.

1. Obtain a fresh facts-and-Opens audit context through
   `$INDUCTIVE_RECOMPOSE_CTL audit-context`.
2. Dispatch `../recompose-runner/SKILL.md` through `$SUBAGENT_TOOL` with
   `$SUBAGENT_AWAIT_SYNC`, supplying that complete context.
3. Record the runner return through
   `$INDUCTIVE_RECOMPOSE_CTL record-recompose-report`. The parent records; the
   runner does not.
4. Route from the recorded report returned by the control.

On runner failure or invalid output, record nothing. Report the failure or
retry from a fresh audit context.

## Findings

When the recorded report has findings, present each one without repairing it
in G4. Then call:

`$INDUCTIVE_GATE_CTL gate-reopen --gate G3 --from-report --report-digest <digest>`

The control validates the report against current facts and Opens, atomically
registers all findings as Opens (each `finding.lens` must come from an
implicated Open.`lens` or a fact `lens` value), reopens G3,
resets G4, and invalidates the report. After G3 closes again, run the complete
G4 audit from fresh context.

## Close

When the recorded report has no findings and `buildable`, `reversible`, and
`verifiable` are all true, call
`$INDUCTIVE_GATE_CTL gate-close --gate G4`. Closure is report-driven.

On success, resolve a fresh `$CTX`. When `active_gate=complete`, return to
the parent. Do not load another gate.
