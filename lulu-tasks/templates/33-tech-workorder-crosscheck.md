# Tech–Work Order Coverage Audit (TWCA)

**Work Order Cross-check Against Tech-Doc**

---

## Purpose

After the work order (task files) are drafted and before evaluation completes, verify:
1. Every deliverable unit in the tech-doc has a corresponding task (Coverage)
2. Every task's acceptance criteria traces back to a tech-doc requirement (Traceability)
3. Task constraints do not contradict tech-doc hard rules (Consistency)

**When to run:** W1 phase of eval-runner, after TDA and W0 pass.

**Attribution rule:** For every gap found, check if the tech-doc addresses it:
- Tech-doc has it → `WO-MISS` → inline-fixable
- Tech-doc is silent → `SOT-DEFECT` → escalate (TDA safety net)

---

## Direction 1 — Coverage: Tech-doc → Tasks

> Does every deliverable unit in the tech-doc have a corresponding task?

Enumerate **semantically** from tech-doc deliverable units (not by H2/H3 heading structure). A deliverable unit is any behavior, function, or integration point that must be implemented.

| Tech-doc Deliverable Unit | Covering Task(s) | root_cause | sot_source | Status |
|--------------------------|-----------------|------------|------------|--------|
| {unit from tech-doc} | t{N} | — | tech-doc §X.X | ✅ Covered |
| {unit from tech-doc} | — | WO-MISS | tech-doc §Y.Y | ❌ Missing |

**Attribution:**
- Unit is in tech-doc but no task covers it → `WO-MISS` → inline fix
- Unit is missing from tech-doc entirely → `SOT-DEFECT` (Completeness) → escalate

---

## Direction 2 — Traceability: Tasks → Tech-doc

> Can every task's acceptance criteria be traced back to a tech-doc requirement?

### E1 — Citation Missing (WO-MISS)

Task has acceptance criteria but no citation to a tech-doc section. Search tech-doc for the requirement.

| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|------------|------------|----------|---------|--------|---------|
| W1-E1-1 | Acceptance criterion has no tech-doc citation | t{N} | WO-MISS | tech-doc §X.X | "{SOT quote}" — criterion omits citation | medium | Open | — |

**Resolution:** Add `source: tech-doc §X.X` citation to task acceptance criteria.

### E2a — Scope Addition

Task covers scope not found in tech-doc — the task author added something beyond the spec.

| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|------------|------------|----------|---------|--------|---------|
| W1-E2a-1 | Task adds scope beyond tech-doc | t{N} | WO-MISS | not found | Task covers "{scope}" — no tech-doc passage found | medium | Open | — |

**Resolution:** Remove extra scope (WO-MISS) or justify explicitly in task.

### E2b — Tech-doc Gap (SOT-DEFECT)

Task's acceptance criterion references behavior with no basis in the tech-doc.

| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|------------|------------|----------|---------|--------|---------|
| W1-E2b-1 | No tech-doc passage supports this criterion | t{N} | SOT-DEFECT | not found | "{criterion text}" — full search found no defining passage | critical | Open | — |

**Resolution:** Escalate via SOT template AskQuestion (Escalate / Reclassify / Ignore).

---

## Direction 3 — Consistency: Task Constraints vs Tech-doc Hard Rules

> Do task constraints match tech-doc hard rules exactly? No contradictions?

Enumerate tech-doc hard rules (performance thresholds, format requirements, error handling contracts, integration constraints). Check each task that touches these areas.

| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|------------|------------|----------|---------|--------|---------|
| W1-C-1 | Task constraint contradicts tech-doc rule | t{N} | WO-ERROR | tech-doc §X.X | Tech-doc: "{rule}" — Task: "{constraint}" | critical | Open | — |
| W1-C-2 | No tech-doc rule; task made arbitrary choice | t{M} | SOT-DEFECT | not found | No passage defines this constraint | medium | Open | — |

---

## Evidence Requirements by root_cause

```
WO-MISS:
  sot_source: "tech-doc §X.X"
  evidence: "<SOT passage that states the requirement>" vs "<WO location that fails to reflect it>"

SOT-DEFECT:
  sot_source: "not found" | "tech-doc §X.X (ambiguous)"
  evidence: "<exact passage searched>" + "<what is missing/ambiguous and why it blocks implementation>"

WO-ERROR:
  sot_source: "tech-doc §X.X"
  evidence: "<task file + section>" + "<evaluation criterion being violated>"
```

---

## Severity Levels

| Level | Condition | Handling |
|-------|-----------|---------|
| 🔴 critical | Missing task for tech-doc deliverable; SOT-DEFECT blocking further evaluation | Must resolve before W1 passes |
| 🟡 medium | Citation missing; scope addition; minor inconsistency | Fix or explicitly ignore |
| 🟢 minor | Wording mismatch; non-blocking imprecision | Suggested improvement |

---

## Output Report: `wo-review-e{M}-w1.md`

```markdown
# W1 TWCA Report — e{M}

tech-doc: {path}
task-list: {path}
evaluate_round: {M}
date: YYYY-MM-DD

## Direction 1 — Coverage
| Tech-doc Deliverable Unit | Covering Task(s) | root_cause | sot_source | Status |

## Direction 2 — Traceability
### E1 Citation Missing
| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |

### E2a Scope Addition
| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |

### E2b Tech-doc Gap
| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |

## Direction 3 — Consistency
| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |

## Summary
w1_total_issues: N
w1_wo_miss_count: N
w1_sot_defect_count: N
w1_wo_error_count: N
w1_status: complete | blocked
```

---

## Quick Checklist (Before Marking W1 Complete)

- [ ] All tech-doc deliverable units enumerated semantically (not by heading structure)
- [ ] Every unit has a covering task OR gap documented with root_cause + evidence
- [ ] Every task's acceptance criteria has a cited tech-doc source OR E1/E2b gap raised
- [ ] Scope additions assessed: justified OR WO-MISS documented
- [ ] Tech-doc hard rules enumerated; each compared to relevant task constraints
- [ ] All SOT-DEFECT findings reviewed via SOT template AskQuestion
- [ ] All WO-MISS / WO-ERROR inline-fixed or explicitly ignored
