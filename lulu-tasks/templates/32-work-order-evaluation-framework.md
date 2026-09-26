# Work Order Quality Audit Framework (WOQA)

**Work Order Execution Admission**

---

## Purpose

After the work order task files are drafted and W1 (TWCA) passes, verify that every `task.md` is independently executable in a TDD session — no ambiguity, no inference required, no external context needed.

**When to run:** W2 phase of eval-runner, after TDA / W0 / W1 all pass.

**Attribution rule:** If a quality issue traces back to SOT ambiguity → `SOT-DEFECT` (TDA/W1 safety net). Otherwise → `WO-ERROR` → inline-fixable or return to Drafting if structural.

---

## Evaluation Dimensions (6)

### Dimension 1 — Granularity

**Question:** Does each task cover 1–3 function changes, completable in one TDD session?

| Check | Standard |
|-------|---------|
| Task scope | 1–3 function changes; single logical unit of work |
| Session completability | Executable in one TDD session without context-switching |
| `tdd_exempt` tasks | May cover more surface area (no TDD loop); but must still be bounded |

**Typical issues:**
- 🔴 Task covers 5+ unrelated functions — split required (structural, return to Drafting)
- 🟡 Task scope is large but related — justify or split

---

### Dimension 2 — TDD Compliance

**Question:** Do acceptance criteria precede function specs? Is Test-First order maintained?

| Check | Standard |
|-------|---------|
| Acceptance criteria position | Must appear before function specs in task.md |
| Test-First signal | Criteria written as observable test conditions, not implementation steps |
| `tdd_exempt` flag | If present: TDD compliance check skipped; verify flag is justified |

**Typical issues:**
- 🔴 Function spec written before acceptance criteria — reorder required
- 🟡 Acceptance criteria exist but not testable as written

---

### Dimension 3 — Spec Completeness

**Question:** Are function signatures complete? No empty acceptance criteria, no TBD?

| Check | Standard |
|-------|---------|
| Function signatures | Complete: name, parameters, return type |
| Acceptance criteria | Non-empty; no "TBD", no "to be defined" |
| No placeholders | No `TODO`, `...`, `[to be filled]` |

**Typical issues:**
- 🔴 Function signature has `// TODO` or missing parameters
- 🟡 Acceptance criterion is present but untestable ("should work correctly")

---

### Dimension 4 — Constraint Coverage

**Question:** Are all hard rules from the tech-doc explicitly copied into the task?

| Check | Standard |
|-------|---------|
| Hard rules copied | Performance thresholds, format requirements, error contracts present in task |
| Source cited | Each constraint references its tech-doc source |
| No implicit assumptions | Task does not assume the implementer knows the constraint |

**Typical issues:**
- 🔴 Performance threshold exists in tech-doc but absent from task constraints
- 🟡 Constraint present but no source citation

---

### Dimension 5 — Test Case Quality

**Question:** Do acceptance criteria cover normal / boundary / edge scenarios?

| Check | Standard |
|-------|---------|
| Normal cases | At least one happy-path scenario |
| Boundary cases | Input limits, empty inputs, single-element cases |
| Edge cases | Error states, concurrent access (if relevant), null/undefined |
| `tdd_exempt` flag | If present: test case quality check skipped |

**Typical issues:**
- 🔴 Only happy-path acceptance criteria; no error scenarios
- 🟡 Boundary cases present but edge cases (null, empty) missing

---

### Dimension 6 — Dependency Graph

**Question:** Is the execution order sound? No cycles, no missing dependencies?

| Check | Standard |
|-------|---------|
| No cycles | Task dependency graph is a DAG |
| Dependencies declared | All prerequisite tasks listed in `dependencies` field |
| Cross-phase deps | Phase-boundary dependencies explicitly noted |

**Typical issues:**
- 🔴 Task A depends on Task B which depends on Task A — cycle detected
- 🟡 Task assumes output from another task but no dependency declared

---

## Issue Row Format

```markdown
| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|------------|------------|----------|---------|--------|---------|
| W2-1 | {description} | t{N} | WO-ERROR | — | task t{N} §{section}: {violation} / W2-Dim{N} ({name}) | medium | Fixed | fix |
| W2-2 | {description} | t{M} | SOT-DEFECT | tech-doc §X.X | No passage defines this behavior | critical | Escalated | escalate |
```

**Evidence requirements:**
```
WO-ERROR:
  evidence: "<task file + section>" + "W2-Dim{N} ({dimension name}): <violation>"
  sot_source: — (SOT not involved)

SOT-DEFECT (rare safety net):
  sot_source: "tech-doc §X.X"
  evidence: "<ambiguous passage>" + "<why it forced an unresolvable task spec>"
```

---

## Severity Levels

| Level | Condition | Handling |
|-------|-----------|---------|
| 🔴 critical | Structural issues (granularity requires task split; cycle in dependency graph) | Return to Drafting |
| 🟡 medium | Spec completeness gap; missing constraint; incomplete test cases | Inline fix |
| 🟢 minor | Wording improvement; non-blocking precision gap | Optional |

**Structural vs non-structural:**
- **Structural** = fix requires modifying `task-list.md` (task split, task addition, dependency graph change) → return to Drafting
- **Non-structural** = fix modifies `task.md` content only → inline-fixable

---

## Output Report: `wo-review-e{M}-w2.md`

```markdown
# W2 WOQA Report — e{M}

tasks: {path to tasks/ dir}
evaluate_round: {M}
date: YYYY-MM-DD

## Issues

| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|------------|------------|----------|---------|--------|---------|

## Summary
w2_total_issues: N
w2_wo_error_count: N
w2_sot_defect_count: N
fix_severity: critical | medium | minor | none
fix_severity_reason: {reason}
w2_status: complete
```

---

## Quick Checklist (Before Marking W2 Complete)

- [ ] Each task covers ≤ 3 function changes (or `tdd_exempt` justified)
- [ ] Acceptance criteria appear before function specs in each task
- [ ] No `TODO`, `TBD`, or empty acceptance criteria
- [ ] All tech-doc hard rules explicitly present in task constraints with source citation
- [ ] Acceptance criteria cover normal / boundary / edge cases (unless `tdd_exempt`)
- [ ] Dependency graph is a DAG; cross-phase dependencies explicitly declared
- [ ] All SOT-DEFECT findings reviewed via SOT template AskQuestion
- [ ] Structural issues returned to Drafting; non-structural issues inline-fixed or ignored
