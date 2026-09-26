---
name: work-order-eval-runner
description: >-
  Single-round work-order evaluation executor for lulu-dev-workflow /lulu-tasks sessions.
  Invoked by the parent lulu-tasks/SKILL.md orchestrator per evaluation round.
  Runs TDA → W0 → W1 → W2 phases and returns exit_code.
  Use when: dispatched by lulu-tasks/SKILL.md Rule E2 for a single evaluation round.
meta-skill-version: 1.0.0
---

# work-order-eval-runner

Sub-agent executing a single work-order evaluation round within a lulu-dev-workflow /lulu-tasks session.
Runs TDA → W0 → W1 → W2 in sequence. Writes one report file per phase. Returns exit_code to parent.

---

## Constitutional Principles

These principles are **non-negotiable preconditions** for every finding across all phases. Read before executing any phase.

### P1 · Evaluation Evidence First

**Any evaluation finding must be backed by citable evidence before a conclusion is drawn. No evidence = invalid finding.**

| Root Cause | Required Evidence |
|-----------|------------------|
| `SOT-DEFECT` | Exact passage from SOT that is missing / ambiguous / contradictory + why it blocks implementation |
| `WO-MISS` | (1) SOT passage stating the requirement + (2) work-order location that fails to reflect it |
| `WO-ERROR` | (1) Exact task file + section + (2) evaluation criterion being violated |
| `DECISION-REQUIRED` | Two compliant interpretations plus their material contract or acceptance difference |

If evidence cannot be located → label the finding `UNRESOLVABLE` and surface to human via AskQuestion. Do not guess, infer, or proceed without evidence.

### P2 · SOT Auditability

**Every issue must be classified: is the SOT defective, is the work-order
defective, or is a human decision required?**

- SOT defective → evaluation cannot proceed on that region → escalate (never fix silently)
- SOT valid, work-order wrong → fix work-order inline or return to Drafting
- Materially different compliant interpretations → request a human decision; do
  not choose an implementation.
- **Human-owned issues always require AskQuestion — hard constraint; no bypass.**

P1 is a prerequisite for P2: without evidence, SOT auditability cannot be exercised.

---

## Input Contract

Received via the invocation prompt from `lulu-tasks/SKILL.md` Rule E2:

| Parameter | Type | Description |
|-----------|------|-------------|
| `evaluate_round` | int | Evaluation round number M (starts at 1) |
| `session_dir` | path | Absolute path to `r{N}/` session directory |
| `tech_doc_path` | path | Absolute path to `tech-doc.md` |
| `task_list_path` | path | Absolute path to `task-list.md` |
| `framework_tda` | path | `$SKILL_DIR/templates/34-tech-doc-admission-framework.md` |
| `framework_twca` | path | `$SKILL_DIR/templates/33-tech-workorder-crosscheck.md` |
| `framework_woqa` | path | `$SKILL_DIR/templates/32-work-order-evaluation-framework.md` |
| evaluate-state.md | file content | Pasted in prompt under `## Current Evaluation State` section; used for resume |

All report files are written to `{session_dir}/evaluate{M}/`.

---

## Resume Logic

On entry, read `current_dimension` from the `## Current Evaluation State` section of the invocation prompt.

| `current_dimension` | Action |
|--------------------|--------|
| `TDA` or not present | Begin at Phase TDA |
| `W0` | Skip TDA; begin at Phase W0 |
| `W1` | Skip TDA + W0; begin at Phase W1 |
| `W2` | Skip TDA + W0 + W1; begin at Phase W2 |
| `DONE` | All phases complete; verify exit contract and return |
| `FAILED` | Terminal state — not executable. Read `failure_type` from evaluate-state.md; report to parent. Do not re-run. |

**`DONE` and `FAILED` are terminal states, not executable phases.** Do not run any phase when either is the current dimension.

---

## Attribution Protocol

Used by Phase W1 and Phase W2 to route every issue finding.

### Root Cause Taxonomy

| Label | Meaning |
|-------|---------|
| `SOT-DEFECT` | The SOT itself is defective (Completeness / Precision / Consistency sub-types) |
| `WO-MISS` | SOT is valid; work-order failed to reflect a requirement that exists in the SOT |
| `WO-ERROR` | Work-order self-quality issue; SOT not involved |
| `UNRESOLVABLE` | Finding status (not a root cause): P1 evidence cannot be located |
| `DECISION-REQUIRED` | Work-order admits materially different compliant interpretations; a human choice is required |

### Evidence Format per Root Cause

```
SOT-DEFECT:
  evidence_sot_quote: "<exact passage from SOT>"
  evidence_gap:       "<what is missing/ambiguous/contradictory and why it blocks implementation>"
  sot_source:         "tech-doc §X.X" | "core-state-model.md §N" | ...

WO-MISS:
  evidence_sot_quote: "<SOT passage stating the requirement>"
  evidence_wo_loc:    "task t{N} / §{section} / {field}"
  description:        "<what is missing or wrong in the work-order>"

WO-ERROR:
  evidence_wo_loc:    "task t{N} / §{section} / {field}"
  criterion:          "W2-Dim{N} ({name})"
  description:        "<specific quality violation>"

UNRESOLVABLE:
  evidence_attempt:   "<what was searched and why evidence could not be located>"

DECISION-REQUIRED:
  candidate_a:         "<one compliant interpretation>"
  candidate_b:         "<a materially different compliant interpretation>"
  material_difference: "<contract, acceptance, or implementation effect>"
```

### Issue Routing by Root Cause

**WO-MISS / WO-ERROR — default Fix (no AskQuestion):**

Apply the suggested fix inline; record decision `fix` and status `Fixed`. Do not invoke AskQuestion for WO issues.

```
Issue [{#}] — {root_cause}
{description}
Location: {evidence_wo_loc}
Criterion: {criterion} (for WO-ERROR)
SOT source: {evidence_sot_quote} (for WO-MISS)

Action: Fix — apply suggested fix inline
```

**SOT-DEFECT / UNRESOLVABLE / DECISION-REQUIRED — Human Resolution template
(always AskQuestion):**

Step 1:
```
Issue [{#}] — {root_cause}
{description}
SOT source: {sot_source}
Evidence: {evidence_sot_quote} | {evidence_gap}

Options:
  Escalate — suspend evaluation; record as tda_blocked
  Reclassify — reassign root cause (provide new root cause + reason in Step 2)
  Ignore — record as noted, evaluation continues (not allowed for `DECISION-REQUIRED`)
```

Step 2 (only if Reclassify selected):
```
Provide reclassification:
  new_root_cause: SOT-DEFECT | WO-MISS | WO-ERROR | DECISION-REQUIRED
  reason: <brief justification citing P1 evidence>
```

**Routing outcomes:**
- `Escalate` → write report row (status: escalated) → write `current_dimension: FAILED`, `failure_type: sot_defect` to evaluate-state.md → stop current phase
- `Reclassify` → update report row (root_cause: new_root_cause, decision: reclassified) → route to corresponding WO or SOT template. **Special case: UNRESOLVABLE → Reclassify → SOT-DEFECT is treated as Escalate** — immediately write FAILED + sot_defect; do not start another AskQuestion round.
- `Ignore` → write report row (status: noted) → continue to next issue

**DECISION-REQUIRED resolution:** Select one interpretation or define an
explicit multi-option contract, then reclassify to `WO-ERROR` before applying
any work-order edit. Do not ignore it.

---

## Phase TDA — Tech-doc Admission

**Inputs:** `tech-doc.md` only. No task files needed.  
**Framework:** `framework_tda` (`34-tech-doc-admission-framework.md`)  
**Report:** `{session_dir}/evaluate{M}/wo-review-e{M}-tda.md`

### Steps

1. **Load framework.** Read `{framework_tda}` in full. Do not `$FETCH_TEMPLATE`.

2. **Identify functional units.** From `tech-doc.md`, enumerate the functional units that would need to be implemented (deliverable behaviors, not design elements).

3. **Per-unit decomposability check (4 checks):**
   For each functional unit, verify:
   - ① Success path is defined
   - ② Error/exception path is defined or explicitly marked out-of-scope
   - ③ Acceptance criteria can be written from this spec alone, without guessing
   - ④ Work-order author does not need to make design decisions (tech-doc has made them)

4. **Global consistency check.** Verify no internal contradictions; all cross-references within the tech-doc resolve.

5. **Record findings.** For each defect found: classify as `SOT-DEFECT` (Completeness / Precision / Consistency), record evidence per P1, write to `wo-review-e{M}-tda.md`.

6. **For each SOT-DEFECT found:** invoke SOT template AskQuestion (P2 — always required).
   - `Escalate` → write report (status: escalated) → update evaluate-state.md: `tda_status: failed`, `current_dimension: FAILED`, `failure_type: sot_defect` → **stop, return to parent**
   - `Reclassify` → update root_cause in report → route accordingly (if reclassified to WO-MISS/WO-ERROR: note for later phases; TDA itself is not about WO issues)
   - `Ignore` → write report (status: noted) → continue

7. **Exit TDA.** If no unresolved escalations:
   - Update evaluate-state.md: `tda_status: passed`, `current_dimension: W0`
   - Advance to Phase W0

**Project SOT handling:** If a Project SOT defect (e.g., core-state-model contradiction) is discovered incidentally, record it in `wo-review-e{M}-tda.md` and invoke SOT template. Do not actively scan Project SOT — passive raise only.

---

## Phase W0 — Structural Gate

**Inputs:** `task-list.md` only.  
**Framework:** Defined inline below (no external framework file).  
**Report:** `{session_dir}/evaluate{M}/wo-review-e{M}-w0.md`

This is a **hard gate**. W0 failures are not inline-fixable. Return exit_code: w0_failed immediately on any blocking issue.

### W0-A: Phase Boundary Dependency Check

For each phase boundary in `task-list.md` (e.g., Phase 1 → Phase 2):
- Every cross-phase dependency must be explicitly declared in the `dependencies` field of the dependent task
- A task in Phase N may not implicitly depend on Phase N-1 outputs without declaration

### W0-B: SKILL File Granularity Check

Count the number of distinct SKILL files modified across all tasks:
- If any single task modifies > 3 SKILL files → mandatory task split required
- `tdd_exempt` tasks: same granularity rule applies

### W0 Report Format

```markdown
# W0 Structural Gate Report — e{M}

task_list: {task_list_path}
evaluate_round: {M}
date: YYYY-MM-DD

## Issues

| # | Check | task_id | root_cause | evidence | Severity | Status | Decision |
|---|-------|---------|-----------|---------|---------|--------|---------|

## Summary
w0_total_issues: N
w0_status: passed | failed
```

### W0 Exit

- Any blocking issue found → update evaluate-state.md: `w0_status: failed`, `current_dimension: FAILED`, `failure_type: structural` → **stop, return to parent**
- No blocking issues → update evaluate-state.md: `w0_status: passed`, `current_dimension: W1` → advance to Phase W1

---

## Phase W1 — Compliance Cross-check (TWCA)

**Inputs:** `tech-doc.md` + `task-list.md` + all `task.md` files.  
**Framework:** `framework_twca` (`33-tech-workorder-crosscheck.md`)  
**Report:** `{session_dir}/evaluate{M}/wo-review-e{M}-w1.md`

### Steps

1. **Load framework.** Read `{framework_twca}` in full. Do not `$FETCH_TEMPLATE`.

2. **Direction 1 — Coverage.** For each deliverable unit in `tech-doc.md`, verify at least one task in `task-list.md` implements it. Flag gaps as `WO-MISS`.

3. **Direction 2 — Traceability.** For each task, verify:
   - **E1 — Citation missing:** Task references a tech-doc requirement but no `§` citation provided → `WO-MISS`
   - **E2a — Scope addition:** Task implements something not in tech-doc and not justified → `WO-MISS` (or `WO-ERROR` if purely a task quality issue)
   - **E2b — Tech-doc gap:** Task references behavior that tech-doc does not define → potential `SOT-DEFECT` (Completeness)

4. **Direction 3 — Consistency.** Verify task constraints do not contradict tech-doc hard rules. Contradictions → `WO-MISS` (if task omits a constraint) or `SOT-DEFECT` (if the contradiction is in the tech-doc itself).

5. **Attribution rule (P1 + P2).** For every gap:
   - First check: does tech-doc address this requirement?
   - Yes → `WO-MISS`; No → `SOT-DEFECT` (Completeness)
   - Route each finding through Attribution Protocol.

6. **Structural fix detection.** If any fix requires modifying `task-list.md` (task split, task addition, dependency graph change):
   - Update evaluate-state.md: `w1_status: complete`, `post_split_scan_required: true`, `current_dimension: FAILED`, `failure_type: structural`
   - **Stop and return to parent** (structural return; parent SKILL writes Drafting)

7. **Exit W1.** No unresolved SOT-DEFECT; all WO-MISS fixed or noted:
   - Update evaluate-state.md: `w1_status: complete`, `current_dimension: W2`
   - Advance to Phase W2

---

## Phase W2 — Execution Admission (WOQA)

**Inputs:** All `task.md` files.  
**Framework:** `framework_woqa` (`32-work-order-evaluation-framework.md`)  
**Report:** `{session_dir}/evaluate{M}/wo-review-e{M}-w2.md`

### Steps

1. **Load framework.** Read `{framework_woqa}` in full. Do not `$FETCH_TEMPLATE`.

2. **Per-task evaluation.** For each task file, check all 6 dimensions:
   - **Dim 1 — Granularity:** 1–3 function changes per task; completable in one TDD session
   - **Dim 2 — TDD Compliance:** Acceptance criteria before function specs
   - **Dim 3 — Spec Completeness:** No TODO/TBD; non-empty acceptance criteria; complete signatures
   - **Dim 4 — Constraint Coverage:** All tech-doc hard rules explicitly present with source citation
   - **Dim 5 — Test Case Quality:** Normal / boundary / edge cases covered (unless `tdd_exempt`)
   - **Dim 6 — Dependency Graph:** DAG; no cycles; cross-phase deps declared

3. **Attribution rule (P1 + P2).** For each issue:
   - Traces back to SOT ambiguity → `SOT-DEFECT` (W2 safety net; should have been caught in TDA/W1)
   - Otherwise → `WO-ERROR`
   - Route each finding through Attribution Protocol.

4. **Structural fix detection.** If any fix requires modifying `task-list.md` (granularity split, dependency cycle resolution):
   - Update evaluate-state.md: `w2_status: complete`, `fix_severity: critical`, `current_dimension: FAILED`, `failure_type: structural`
   - **Stop and return to parent** (structural return; parent SKILL writes Drafting)

5. **Exit W2.** No structural issues; all non-structural WO-ERROR fixed or noted:
   - Update evaluate-state.md: `w2_status: complete`, `fix_severity: {level}`, `fix_severity_reason: {reason}`, `current_dimension: DONE`
   - Advance to Done

---

## Done

1. Verify all four report files exist under `{session_dir}/evaluate{M}/`:
   - `wo-review-e{M}-tda.md`
   - `wo-review-e{M}-w0.md`
   - `wo-review-e{M}-w1.md`
   - `wo-review-e{M}-w2.md`

2. Verify `evaluate-state.md` has `current_dimension: DONE`.

3. Return to parent agent:
   ```
   EVAL_COMPLETE evaluate_round={M} exit_code=done
   ```

---

## Exit Contract

| `current_dimension` | `failure_type` | Trigger | Parent action |
|--------------------|---------------|---------|---------------|
| `DONE` | — | All phases passed | Write `ReadyForDelivery` → await human-delivery-gate |
| `FAILED` | `sot_defect` | SOT-DEFECT escalated in TDA or W1 | Write `TDABlocked`; present report path to human |
| `FAILED` | `structural` | W0 blocking issue OR structural fix required in W1/W2 | Write `Drafting`; present report path |

**`current_dimension: DONE` does not mean delivery is complete.** The parent SKILL must still:
1. Await human writing `human-delivery-gate.md`
2. Then write `current_state: Delivered`

All report files (`wo-review-e{M}-{tda|w0|w1|w2}.md`) are retained as audit trail regardless of outcome.

---

## Report Format Reference

Issue row format (all phases):

```markdown
| # | Issue | task_id | root_cause | sot_source | evidence | Severity | Status | Decision |
|---|-------|---------|-----------|------------|----------|---------|--------|---------|
```

| Column | Values |
|--------|--------|
| `root_cause` | `SOT-DEFECT` \| `WO-MISS` \| `WO-ERROR` \| `UNRESOLVABLE` \| `DECISION-REQUIRED` |
| `sot_source` | tech-doc section or `—` if SOT not involved |
| `evidence` | Inline summary (full detail in frontmatter or notes block) |
| `Severity` | `critical` \| `medium` \| `minor` |
| `Status` | `Fixed` \| `Escalated` \| `Noted` \| `Reclassified` |
| `Decision` | `fix` \| `escalate` \| `ignore` \| `reclassify→{new_root_cause}` |
