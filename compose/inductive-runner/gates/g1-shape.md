> Part of inductive-runner · loaded only when `$CTX.active_gate` is `G1`

# Gate 1 — Shape Perception

Create one coarse, non-authoritative perception from the current facts and lens
registry. Present it, close G1 automatically, and enter G2.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |
| `$INDUCTIVE_SHAPE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_shape_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

Use each control's `--help` as the command and stdout contract.

## Preconditions

- Fact Intake is complete.
- `$INDUCTIVE_GATE_CTL resolve-context` reports `G1`.

## Shape Perception

1. Request a stateless current perception through `$INDUCTIVE_SHAPE_CTL`.
2. Keep the result coarse. Preserve uncertainty and visible gaps.
3. Present the result without requesting confirmation.

The perception is disposable output. It does not authorize facts or close an
open point.

## Close

After presentation, call `$INDUCTIVE_GATE_CTL gate-close --gate G1`. Resolve a
fresh `$CTX`, then load `g2-topic-loop.md`.

Presentation creates no stopping point. Any later fact correction or newly
exposed open enters through the active downstream gate's global inlet.
