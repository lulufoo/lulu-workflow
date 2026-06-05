---
name: work-order-eval-runner
description: >-
  Single-round work-order evaluation executor for lulu-dev-workflow /tech-work-order sessions.
  Invoked by the parent tech-work-order/SKILL.md orchestrator per evaluation round.
  Runs TDA → W0 → W1 → W2 phases and returns exit_code.
  Use when: dispatched by tech-work-order/SKILL.md Rule E2 for a single evaluation round.
meta-skill-version: 1.0.0
---

# work-order-eval-runner

Sub-agent executing a single work-order evaluation round within a lulu-dev-workflow /tech-work-order session.
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

If evidence cannot be located → label the finding `UNRESOLVABLE` and surface to human via AskQuestion. Do not guess, infer, or proceed without evidence.

### P2 · SOT Auditability

**Every issue must be classified: is the SOT defective, or did the work-order fail to reflect a valid SOT?**

- SOT defective → evaluation cannot proceed on that region → escalate (never fix silently)
- SOT valid, work-order wrong → fix work-order inline or return to Drafting
- **SOT issues always require AskQuestion — regardless of `execution_mode`. This constraint is not bypassed in autonomous mode.**

P1 is a prerequisite for P2: without evidence, SOT auditability cannot be exercised.

---

## Input Contract

Received via the invocation prompt from `tech-work-order/SKILL.md` Rule E2:

| Parameter | Type | Description |
|-----------|------|-------------|
| `evaluate_round` | int | Evaluation round number M (starts at 1) |
| `session_dir` | path | Absolute path to `r{N}/` session directory |
| `tech_doc_path` | path | Absolute path to `tech-doc.md` |
| `task_list_path` | path | Absolute path to `task-list.md` |
| `tda_url` | url | URL of `34-tech-doc-admission-framework.md` |
| `twca_url` | url | URL of `33-tech-workorder-crosscheck.md` |
| `woqa_url` | url | URL of `32-work-order-evaluation-framework.md` |
| `execution_mode` | enum | `guided` (prompt each issue) \| `autonomous` (auto-fix WO issues, always prompt SOT issues) |
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
| `tda_blocked` | Not executable. Report to parent: exit_code=tda_blocked. Do not re-run. |
| `w0_failed` | Not executable. Report to parent: exit_code=w0_failed. Do not re-run. |

**`DONE`, `tda_blocked`, `w0_failed` are exit codes, not executable phases.** Do not run any phase when these are the current dimension.

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
```

### Issue Routing by Root Cause

**WO-MISS / WO-ERROR — WO template:**

Present via AskQuestion (guided mode) or auto-fix (autonomous mode for WO-ERROR):

```
Issue [{#}] — {root_cause}
{description}
Location: {evidence_wo_loc}
Criterion: {criterion} (for WO-ERROR)
SOT source: {evidence_sot_quote} (for WO-MISS)

Options:
  Fix — apply suggested fix inline
  Ignore — record as noted, continue
```

**SOT-DEFECT / UNRESOLVABLE — SOT template (always AskQuestion, any mode):**

Step 1:
```
Issue [{#}] — {root_cause}
{description}
SOT source: {sot_source}
Evidence: {evidence_sot_quote} | {evidence_gap}

Options:
  Escalate — suspend evaluation; record as tda_blocked
  Reclassify — reassign root cause (provide new root cause + reason in Step 2)
  Ignore — record as noted, evaluation continues
```

Step 2 (only if Reclassify selected):
```
Provide reclassification:
  new_root_cause: SOT-DEFECT | WO-MISS | WO-ERROR  (UNRESOLVABLE → one of SOT-DEFECT | WO-MISS | WO-ERROR)
  reason: <brief justification citing P1 evidence>
```

**Routing outcomes:**
- `Escalate` → write report row (status: escalated) → set exit_code: tda_blocked → stop current phase
- `Reclassify` → update report row (root_cause: new_root_cause, decision: reclassified) → route to corresponding WO or SOT template
- `Ignore` → write report row (status: noted) → continue to next issue

---

## Phase TDA — Tech-doc Admission

**Inputs:** `tech-doc.md` only. No task files needed.  
**Framework:** `tda_url` (34-tech-doc-admission-framework.md)  
**Report:** `{session_dir}/evaluate{M}/wo-review-e{M}-tda.md`

### Steps

1. **Load framework.** Fetch `tda_url` and read the TDA framework in full.

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
   - `Escalate` → write report (status: escalated) → update evaluate-state.md: `tda_status: failed`, `current_dimension: tda_blocked` → **exit_code: tda_blocked**
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

- Any blocking issue found → update evaluate-state.md: `w0_status: failed`, `current_dimension: w0_failed` → **exit_code: w0_failed**
- No blocking issues → update evaluate-state.md: `w0_status: passed`, `current_dimension: W1` → advance to Phase W1

---

## Phase W1 — Compliance Cross-check (TWCA)

**Inputs:** `tech-doc.md` + `task-list.md` + all `task.md` files.  
**Framework:** `twca_url` (33-tech-workorder-crosscheck.md)  
**Report:** `{session_dir}/evaluate{M}/wo-review-e{M}-w1.md`

### Steps

1. **Load framework.** Fetch `twca_url` and read the TWCA framework in full.

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
   - Update evaluate-state.md: `w1_status: complete`, `post_split_scan_required: true`, `current_dimension: w0_failed` (return-to-Drafting path)
   - **exit_code: w0_failed** (structural return, not a W0 check failure)

7. **Exit W1.** No unresolved SOT-DEFECT; all WO-MISS fixed or noted:
   - Update evaluate-state.md: `w1_status: complete`, `current_dimension: W2`
   - Advance to Phase W2

---

## Phase W2 — Execution Admission (WOQA)

**Inputs:** All `task.md` files.  
**Framework:** `woqa_url` (32-work-order-evaluation-framework.md)  
**Report:** `{session_dir}/evaluate{M}/wo-review-e{M}-w2.md`

### Steps

1. **Load framework.** Fetch `woqa_url` and read the WOQA framework in full.

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
   - Update evaluate-state.md: `w2_status: complete`, `fix_severity: critical`, `current_dimension: w0_failed`
   - **exit_code: w0_failed** (structural return; trigger Drafting in parent SKILL)

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

| exit_code | Trigger | evaluate-state.md state | Parent action |
|-----------|---------|------------------------|--------------|
| `done` | All phases passed | `current_dimension: DONE` | Write `ReadyForDelivery` → await human-delivery-gate |
| `tda_blocked` | SOT-DEFECT escalated (TDA or W1) | `current_dimension: tda_blocked` | Write `TDABlocked`; present report path to human |
| `w0_failed` | W0 structural gate failed OR structural fix required in W1/W2 | `current_dimension: w0_failed` | Write `Drafting`; present report path |

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
| `root_cause` | `SOT-DEFECT` \| `WO-MISS` \| `WO-ERROR` \| `UNRESOLVABLE` |
| `sot_source` | tech-doc section or `—` if SOT not involved |
| `evidence` | Inline summary (full detail in frontmatter or notes block) |
| `Severity` | `critical` \| `medium` \| `minor` |
| `Status` | `Fixed` \| `Escalated` \| `Noted` \| `Reclassified` |
| `Decision` | `fix` \| `escalate` \| `ignore` \| `reclassify→{new_root_cause}` |
