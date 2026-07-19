> Part of decision-workflow · gate contract · via `$SKILL_DIR/runners/gl-grill-runner/SKILL.md`

#### GL — Grill

**Prerequisites:** Q closed

Spine id `GL` (Grill). Not protocol G0/G8/G9. Not the RS align-gate metavariable `G`.

**Purpose:** Force-surface decision-domain operational/confirmation intents after Q locks problem+constraints and before E explores directions — reduce late reopen cost.

**Ask domain:** Decision-domain intent only (confirmation/authority, human–machine division, risk-vs-mitigation narrative, operational preferences tied to locked Q). Not implementation detail, WBS, or unbounded plan grilling.

**Topic circles (T1–T4):** confirmation & authority · human–machine division · risk narrative classification · operational constraints/preferences. Specific questions are context-driven within these circles.

**Before entering:**
1. Read locked Q from `gate-payloads/Q.json` (or session paths) — anchor all probes to problem + constraints.
2. Do not start Grill dialogue until Q payload is available.

**Execute (framework pass — agent + user):**
1. Grill in grilling style: **one question at a time**, each with a **recommended answer**; look up facts from environment / Q before asking.
2. User may amend or reject the recommendation — do not treat silence as consent to skip a circle.
3. Cover T1–T4 with real probes or reasoned `na` (user must understand na at G8). Unjustified all-na is a framework failure — do not `gate-close`.
4. If probing shows Q is wrong → **do not** `gate-close` GL; load RS / realign to Q (G9).
5. Persist only via gate-close payload `exchanges[]` — do not dual-write exchanges to G0. If G0 fires during GL, register `source` is `GL`.

**Confirmation (G8):** Ask whether operational/confirmation intents for T1–T4 are settled and direction exploration may begin. If all circles are na, state that explicitly in the confirm question.

**Pass criterion (framework):** T1–T4 settled or reasoned na; Q still holds; G8 confirmed; ask-domain respected.

**Mechanical close:** CLI enforces payload predicates only (non-empty `exchanges`, each Ti present, na/question/answer rules, `user_confirmed: true`). CLI green ≠ framework pass.
