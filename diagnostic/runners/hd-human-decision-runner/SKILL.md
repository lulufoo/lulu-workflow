---
name: diagnostic/hd-human-decision-runner
description: >-
  Human Decision subroutine after RR failure. Routes to RS or Unable to Decide.
  Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# hd-human-decision-runner

Execute **Human Decision** after Risk Release failure.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/hd-human-decision.md`
- Trigger: RR exit `human_decision`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Read and apply from `$CTX.domain_constraints` for all subsequent dialogue in this gate:
   - `objective` — session intent; frame the entire gate within this goal
   - `role.instruction` — persona and language stance
   - `domain.instruction` — domain boundary constraints
3. Present failure context; user selects exit (G8):
   - **Upstream wrong** → identify reopen gate → load `$SKILL_DIR/runners/rs-reopen-runner/SKILL.md`
   - **No solution** → output Unable to Decide (directions ≥2, stuck gate, unlock condition); session incomplete
4. Return `HD_COMPLETE exit=rs|unable` or hand off to RS runner

## Exit

`HD_COMPLETE exit=rs reenter=<G>` · `HD_COMPLETE exit=unable`
