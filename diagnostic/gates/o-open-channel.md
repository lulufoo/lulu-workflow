> Part of diagnostic-workflow · loaded by Gate Routing in `$SKILL_DIR/SKILL.md`

#### O — Open Channel

**Prerequisites:** `$DX_START` complete · `active_gate` is `O`

**Execute:**
1. Apply `role.instruction` from `domain_constraints` if present (see kernel Domain Constraints HARD-GATE).
2. Run holder `### Context Loading` steps if injected.
3. Invite the user to share existing knowledge:

   > "Before we begin — share what you'd like me to know: direction preferences, concerns, or options you've already ruled out. It doesn't need to be complete; you can add more at any point."

4. G0 capture: confirm briefly, then `$REGISTER_CONTROL register-append` for Prior / Assumption (`source` defaults to `O` while `active_gate` is `O`).

**Pass criterion:** User confirms they are ready to proceed to Q (G8). Prior dump is optional — empty registers are allowed.

**Does not count toward Q's question quota.**
