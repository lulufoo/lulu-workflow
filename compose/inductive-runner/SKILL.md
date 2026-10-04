---
name: inductive-runner
description: >-
  Coordinates pre-writing induction across topic convergence
  and open-point resolution.
---

# inductive-runner

## Goal

Through the G2→G3 spine, induce intent step by step and converge it into settled facts. Topic dialogue converges the substance. Open questions dispose what is still unresolved and material.

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

Parent has already completed Fact Intake.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Use the control's `--help` as the command and stdout contract.

## Cognition

The stance every gate on this spine acts from.

| Term | Unit |
|---|---|
| induction, Open, land / defer / reject | `../references/cognition/producer/induce.md` |
| settled facts, fact set | `../references/cognition/fact.md` |

## Control Spine

1. Resolve `$CTX` through `$INDUCTIVE_GATE_CTL resolve-context`.
2. Load only the gate named by `$CTX.active_gate`.
3. After a gate transition, resolve a fresh `$CTX` before routing again.

## Gate Routing

Route only from control stdout or `$CTX`; never route from a state-file path.

| `$CTX.active_gate` | Load |
|---|---|
| `G2` | `gates/g2-topic-loop.md` |
| `G3` | `gates/g3-open-point-loop.md` |
| `complete` | Do not load another gate. |

- A fresh `$CTX.active_gate` authorizes its entry.
- After G3 closes, `$CTX.active_gate` is `complete`.
- Read `../../_subagent.md` before any sub-agent dispatch.

## Handoff

After G3 closes and `$CTX.active_gate` is `complete`, report completion and
return control to the parent Compose stage.
