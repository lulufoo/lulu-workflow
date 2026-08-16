---
name: inductive-runner
description: >-
  Coordinates pre-writing induction across shape perception, topic convergence,
  open-point resolution, internal audit, and provenance audit.
---

# inductive-runner

Run the G1→G5 control spine for one active Compose slice. Complete when G5 is
closed and the settled facts are ready for Compose Writing.

## Dispatch Inputs

The parent Compose stage supplies:

| Variable | Meaning |
|---|---|
| `$CYCLE_ID` | Active cycle identifier |
| `$SCOPE_REF` | Current slice source |
| `$SOURCE_PATH` | Fact Intake source; equal to `$SCOPE_REF` |
| `$INTENT_BASELINE_REFS` | JSON array of intent references |
| `$NORM_CONSTRAINT_REFS` | JSON array of normative references |
| `$INDUCTIVE_OUT_DIR` | Active slice output directory |

Bind `$PROJECT_ROOT` to the current project root. Bind Fact Intake's
`$REVISION_DIR` to `$INDUCTIVE_OUT_DIR`.

Read `../../_subagent.md` before any sub-agent dispatch.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

Use the control's `--help` as the command and stdout contract.

## Control Spine

1. Run Fact Intake.
2. Resolve `$CTX` through `$INDUCTIVE_GATE_CTL resolve-context`.
3. Load only the gate named by `$CTX.active_gate`.
4. After a gate transition, resolve a fresh `$CTX` before routing again.
5. Return to the parent only after G5 closes.

### Fact Intake

Load and follow `../fact-intake-runner/SKILL.md` with:

```text
## Input
REVISION_DIR: <$INDUCTIVE_OUT_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
REQUIRE_SEED_ORIGIN: true
```

Fact Intake owns cut, evaluation, disposition, and confirmation. Do not
reimplement them here.

## Gate Routing

Route only from control stdout or `$CTX`; never route from a state-file path.

| `$CTX.active_gate` | Load |
|---|---|
| `G1` | `gates/g1-shape.md` |
| `G2` | `gates/g2-topic-loop.md` |
| `G3` | `gates/g3-open-point-loop.md` |
| `G4` | `gates/g4-recompose.md` |
| `G5` | `gates/g5-provenance.md` |

Before executing a gate, read its file. A readable next gate does not authorize
execution.

## Permissions and Boundaries

- The human owns semantic decisions and authorization.
- The parent Agent owns dialogue, presentation, sub-agent dispatch, and control
  invocation.
- Sub-agent permissions come only from their owning contract.
- Each loaded gate owns its local tool routing.
- Controls own validation, persistence, and mechanical transitions.
- Never read or write session data directly for routing or mutation.
- Treat empty intent or norm reference arrays as inactive inputs.

## Handoff

After G5 closes, report completion and return control to the parent Compose
stage. Compose Writing consumes the settled facts; provenance receipts remain
available to the parent delivery flow.
