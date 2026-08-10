---
name: decision/hd-human-decision-runner
description: Internal runner for the Decision Human Decision subroutine.
meta-skill-version: 1.0.0
---

# hd-human-decision-runner

Resolve an R suspension caused by unresolved risks. Complete by routing an
upstream error to RS or reporting an Unable to Decide outcome.

## Blocking policy

Control CLI non-zero → stop, report error, wait for user direction.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- Gate contract: `$SKILL_DIR/gates/hd-human-decision.md`
- Trigger: R exit `human_decision`

## Pipeline

**Entry:**

1. Run `$GATE_CONTROL resolve-context`; pin stdout JSON as `$CTX`.
2. Apply `$CTX.domain_constraints` (`objective`, `role.instruction`,
   `domain.instruction`) to the dialogue.

**Act:**

1. Present failure context; user selects exit:
   - **Upstream wrong** → identify align gate → load `$SKILL_DIR/runners/rs-realign-runner/SKILL.md`
   - **No solution** → output Unable to Decide (directions ≥2, stuck gate, unlock condition); session incomplete

**Done:** Return `HD_COMPLETE exit=rs|unable` or hand off to RS runner.

## Exit

`HD_COMPLETE exit=rs reenter=<G>` · `HD_COMPLETE exit=unable`
