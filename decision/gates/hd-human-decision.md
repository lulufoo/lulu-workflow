> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/hd-human-decision-runner/SKILL.md`

## Human Decision

**Trigger:** Risk Release ❌ Failed — verification failed, upstream conclusion may be wrong, or information is insufficient to decide.

**Execute:** Present the failure to user. Ask user to choose:

**Two exits:**

1. **Upstream wrong** — the failure reveals that a prior gate's conclusion is incorrect  
   → trigger RS → RS routes back into LoopA at the identified gate

2. **No solution** — the decision cannot be made with available information  
   → output "Unable to Decide" with: directions explored (≥2) · gate stuck and why · unlock condition
