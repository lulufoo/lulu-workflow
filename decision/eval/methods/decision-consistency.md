# Method — Decision consistency (single Eval)

Probe **one** EvalTarget (`decision-eval-target.md`) once. Run all checks below in this pass. Emit separate review issues per blocker; each issue **must** include `realign_gate` (`E` / `D` / `X`). Do not edit EvalTarget; Decision fail-exit → RS.

---

## Check 1 — E↔D direction match (`realign_gate=E`)

### Pair

- `<!-- chapter:direction -->` (`gate-payloads/E.json`)
- `<!-- chapter:settled_direction -->` (`gate-payloads/D.json`)

### Rule

E `user_choice` (and chosen direction) must describe the **same path** as D `decision_rationale` / `execution_approach`.

---

## Check 2 — D↔X phase alignment (`realign_gate=D`)

### Pair

- `<!-- chapter:settled_direction -->` → `execution_approach`
- `<!-- chapter:execution_analysis -->` → `acceptance_criteria`

### Rule

Major phases / landing steps in D must have corresponding acceptance coverage in X.

---

## Check 3 — X gap ↔ assumptions (`realign_gate=X`)

### Pair

- `<!-- chapter:execution_analysis -->` → `gap`
- `<!-- chapter:assumptions -->`

### Rule

X `gap` must not contradict assumption `risk_state` / `release_terms` conclusions.
