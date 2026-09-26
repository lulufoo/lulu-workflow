# Tech-Doc Admission Framework (TDA)

**Tech-Doc Admission — Work-Order Entry Gate**

---

## Scope Declaration

TDA evaluates the tech-doc **from the perspective of work-order decomposability only**.

| In scope | Out of scope |
|----------|-------------|
| Are behavior specs concrete enough to write acceptance criteria? | Architecture soundness |
| Are all execution paths (success/error/edge) defined? | Product requirement alignment |
| Are hard rules quantified, not vague? | Design choice evaluation |
| Is there internal consistency within the tech-doc? | Tech-plan evaluation criteria |

TDA does **not** re-evaluate the tech-doc as a design document — that is tech-plan's responsibility.
TDA is a safety net that intercepts implementation-critical gaps that escaped tech-plan review.

---

## When to Run

At the start of the `Evaluating` phase in `tech-work-order`, before W0/W1/W2.

**Inputs:** `tech-doc.md` only.
**Project SOT** (core-state-model.md, API definitions, naming conventions): passive only — raise if discovered incidentally; do not actively scan.

---

## SOT Tier Definitions

| Tier | Examples | TDA Handling |
|------|---------|-------------|
| **Feature SOT** | `tech-doc` (per work-order) | Active audit — scan in full |
| **Project SOT** | `core-state-model.md`, API interface definitions, naming conventions | Passive — raise on discovery only |
| **Process SOT** | `33-TWCA`, `32-WOQA` | Not audited in this workflow |

---

## Step 1 — Identify Functional Units

Scan tech-doc to identify **functional units**: distinct behaviors that must be implemented.

A functional unit is any:
- Named function, method, or operation
- State transition or event handler
- Data transformation or validation rule
- Integration point or API endpoint

List all identified functional units before checking each one.

---

## Step 2 — Per-Unit Decomposability Checklist

For **each functional unit** identified in Step 1, apply all 4 checks:

| # | Check | Pass condition | Fail → SOT-DEFECT sub-type |
|---|-------|---------------|---------------------------|
| 1 | **Success path defined?** | At least one expected behavior/output is specified | Completeness |
| 2 | **Error/exception path defined?** | Error conditions are specified OR explicitly marked out-of-scope | Completeness |
| 3 | **Acceptance criteria writable?** | A developer can write a test assertion from this spec alone, without guessing | Precision |
| 4 | **No design decisions delegated?** | The spec does not say "implement as appropriate" / "handle reasonably" / "decide based on context" | Precision |

**Pass condition for unit:** All 4 checks pass.
**Fail condition:** Any check fails → record as SOT-DEFECT finding with evidence.

---

## Step 3 — Global Consistency Check

After all units are checked, scan for cross-unit contradictions:

| Check | Description |
|-------|-------------|
| **No internal contradictions** | Two passages do not specify conflicting behavior for the same scenario |
| **Cross-references resolvable** | Any reference to another section is resolvable within the document |
| **Terminology consistency** | Same concept is named consistently throughout the doc |

---

## SOT-DEFECT Sub-types

| Sub-type | Condition | Example |
|----------|-----------|---------|
| **Completeness** | Implementation-critical behavior not defined anywhere | "Behavior when path does not exist" unspecified; error path entirely absent |
| **Precision** | Defined but too vague for a unique implementation | "Handle edge cases reasonably"; "return appropriate value" |
| **Consistency** | Internal contradiction within the SOT | §2 says return `null`; §5 says return empty list for the same scenario |

---

## Evidence Format

Every finding must include P1-compliant evidence before it is considered valid.

```yaml
SOT-DEFECT finding:
  unit: "<functional unit name>"
  defect_type: Completeness | Precision | Consistency
  sot_source: "tech-doc §X.X"
  evidence_sot_quote: "<exact passage from tech-doc, or 'no passage found'>"
  evidence_gap: "<what is missing/ambiguous/contradictory and why it blocks implementation>"
  severity: critical | medium
```

**If evidence cannot be located:** label finding as `UNRESOLVABLE` and surface to human for manual classification. Do not guess.

---

## Pass / Fail Criteria

**TDA Pass** — all of the following:
1. All functional units pass all 4 per-unit checks
2. No global consistency violations found
3. All `UNRESOLVABLE` findings reviewed by human (labeled Ignore or Escalate)

**TDA Fail** — any SOT-DEFECT finding with P1 evidence is confirmed (Escalated):
- Write findings to `wo-review-e{M}-tda.md`
- Present each finding via SOT template AskQuestion (Escalate / Reclassify / Ignore)
- If any finding is Escalated → `exit_code: tda_blocked`

---

## Output Format

```markdown
# TDA Report — e{M}

tech-doc: {path}
evaluate_round: {M}
date: YYYY-MM-DD

## Functional Units Identified
1. {unit name}
2. {unit name}
...

## Findings

| # | Unit | Defect Type | sot_source | evidence_gap | Severity | Status | Decision |
|---|------|------------|------------|-------------|---------|--------|---------|
| TDA-1 | {unit} | Completeness | tech-doc §X.X | {gap description} | critical | Escalated | escalate |
| TDA-2 | {unit} | Precision | tech-doc §Y.Y | {ambiguity} | medium | Noted | ignore |

## Result
exit_code: tda_blocked | tda_passed
```

---

## Quick Checklist (Before Marking TDA Pass)

- [ ] All functional units identified and listed
- [ ] Each unit: success path defined
- [ ] Each unit: error/exception path defined OR explicitly out-of-scope
- [ ] Each unit: acceptance criteria writable without guessing
- [ ] Each unit: no design decisions delegated to implementer
- [ ] No internal contradictions in tech-doc
- [ ] All `UNRESOLVABLE` findings surfaced to human
- [ ] All `Escalated` findings block evaluation (exit_code: tda_blocked)
