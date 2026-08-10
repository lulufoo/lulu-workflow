---
name: decision/hd-human-decision-runner
description: >-
  Human Decision subroutine after R suspend. Routes to RS or Unable to Decide.
  Invoked by decision/SKILL.md.
meta-skill-version: 1.0.0
---

# hd-human-decision-runner

Execute **Human Decision** after R exit `human_decision` (open risks unresolved).

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/hd-human-decision.md`
- Trigger: R exit `human_decision`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin `$CTX`
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.
3. Present failure context; user selects exit:
   - **Upstream wrong** → identify align gate → load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md`
   - **No solution** → output Unable to Decide (directions ≥2, stuck gate, unlock condition); session incomplete
4. Return `HD_COMPLETE exit=rs|unable` or hand off to RS runner

## Exit

`HD_COMPLETE exit=rs reenter=<G>` · `HD_COMPLETE exit=unable`
