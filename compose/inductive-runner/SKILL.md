---
name: inductive-runner
description: >-
  Coordinates pre-writing induction across topic convergence,
  open-point resolution, and internal audit.
---

# inductive-runner

Run the G2→G4 control spine for one active Compose slice. Complete when G4 is
closed, `active_gate=complete`, and the settled facts are ready for Deductive.
Delivery Eval owns provenance audit of the written document.

## Dispatch Inputs

The parent Compose stage supplies:

| Variable | Meaning |
|---|---|
| `$CYCLE_ID` | Active cycle identifier |
| `$SCOPE_REF` | Current slice source |
| `$SOURCE_PATH` | Slice source; equal to `$SCOPE_REF` |
| `$INTENT_BASELINE_REFS` | JSON array of intent references |
| `$NORM_CONSTRAINT_REFS` | JSON array of normative references |
| `$INDUCTIVE_OUT_DIR` | Active slice output directory |

Bind `$PROJECT_ROOT` to the current project root. Parent has already completed
Fact Intake into this slice.

Read `../../_subagent.md` before any sub-agent dispatch.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

Use the control's `--help` as the command and stdout contract.

## Control Spine

1. Resolve `$CTX` through `$INDUCTIVE_GATE_CTL resolve-context`.
2. Load only the gate named by `$CTX.active_gate`.
3. After a gate transition, resolve a fresh `$CTX` before routing again.
4. Return to the parent only after G4 closes and `$CTX.active_gate` is `complete`.

## Gate Routing

Route only from control stdout or `$CTX`; never route from a state-file path.

| `$CTX.active_gate` | Load |
|---|---|
| `G2` | `gates/g2-topic-loop.md` |
| `G3` | `gates/g3-open-point-loop.md` |
| `G4` | `gates/g4-recompose.md` |
| `complete` | Return to the parent. Do not load another gate. |

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

After G4 closes and `$CTX.active_gate` is `complete`, report completion and
return control to the parent Compose stage. Parent enters Deductive. Delivery
Eval audits the written document against the intent / parent / norm triangle.
