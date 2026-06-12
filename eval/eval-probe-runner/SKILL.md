---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Corpus-driven evaluation probe executor for lulu-dev-workflow. Invoked by
  eval/eval-rules.md per dimension. Writes ReviewFile only; state via
  finish-dimension-probe.
---

# eval-probe-runner/SKILL.md

Terminal runner subagent. Probes **one Dimension** per invocation (from EvalCorpus dispatch).

> Drafting Round Iteration (`prober-runner`) complements drafting maturity checks; Evaluating-stage dimensions are defined in workflow corpus templates (e.g. `tech-plan/corpora/*.json`).

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Read `{$SKILL_ROOT}/eval/scripts/url_fetch.py` — use `read_ref()` for all URL/path loads
5. Follow steps below

---

## Required Inputs

Plain-text block from `$EVAL_CONTROL begin-dimension` (all lines required unless noted):

```
DIMENSION_ID          canonical dimension id (e.g. codebase-consistency)
DIMENSION             dispatch key for finish-dimension-probe (legacy e1/e2/e3 or id)
DIMENSION_LABEL       human-readable label for review header
CYCLE_ID              cycle identifier
CYCLE_TYPE            feature | topic
EVAL_TARGET_PATH      absolute path to EvalTarget (B)
REMEDIATION_TARGET_PATH absolute path to RemediationTarget (informational; do not write)
EVALUATE_STATE_PATH   absolute path to evaluate-state.md (read-only)
EVALUATE_DIR          absolute path to evaluate{M}/
REVIEW_OUTPUT_PATH    review filename relative to EVALUATE_DIR
PROJECT_ROOT          project root
SOTS_JSON             JSON array of EvalSoT definitions (may be [])
METHOD_JSON           JSON object: EvalMethod (kind + source)
METHOD_FOCUS          one-line evaluation intent (header REFS anchor)
```

Optional legacy field (when present on url SoT for product doc):

```
PRODUCT_REF           absolute path (only when SOTS_JSON references product doc)
```

---

## Step 1 — Load context

1. Read `EVAL_TARGET_PATH` (EvalTarget **B**).
2. Parse `SOTS_JSON` and `METHOD_JSON`.
3. Load each EvalSoT:
   - `url` · `ref` (https URL or absolute local path) → `read_ref(ref, project_root=Path(PROJECT_ROOT))`
   - `codebase` · `discover_from` + `strategy: approach_or_legacy_sections` → parse B for code entry points:
     - **v2 template** (`## Approach Skeleton` or `## Tasks`)
     - **legacy template** (`§5 Data Flow`, `§6 API / Interfaces`)
     - Read identified code files
4. Load EvalMethod **M**:
   - `external` · `source` (https URL or absolute path) → `read_ref(source, project_root=Path(PROJECT_ROOT))` as rubric
   - `builtin` · `source.procedure_id: codebase_consistency` → compare B against loaded codebase SoT per METHOD_FOCUS
   - `builtin` · `source.procedure_id: tpef_solution_quality` → apply loaded TPEF SoT against B per METHOD_FOCUS

When `SOTS_JSON` is empty, **M** carries both rubric and basis.

---

## Step 2 — Generate issues list

Evaluate **B** using loaded SoT content and **M** / `METHOD_FOCUS`.

For each finding classify `root_cause` per `eval/SKILL.md` and fill all required columns.

Output fields per issue: `id`, `root_cause`, `sot_ref`, `location`, `severity`, `evidence`, `description`, `status: pending`, `decision: —`

Issue `id` prefix: use `DIMENSION` dispatch key (e.g. `e2-1`, `intent-alignment-1`).

---

## Step 3 — Write review file

Path: `{EVALUATE_DIR}/{REVIEW_OUTPUT_PATH}`

1. Read `{$SKILL_ROOT}/eval/review.template.md`
2. Substitute `{{DIM_LABEL}}` ← `DIMENSION_LABEL`, `{{REV}}`, `{{M}}`, `{{DATE}}`, `{{REFS}}` ← `METHOD_FOCUS`
3. Append issue rows; never alter header/separator row order
4. Zero issues: write header + separator only (no data rows)

Do **not** write RemediationTarget. Do **not** Write/Edit `evaluate-state.md`.

---

## Step 4 — Finish probe

Run `$EVAL_CONTROL finish-dimension-probe --dim {DIMENSION}` (non-zero → STOP, report parent).

---

## Constraints

- Probe only — no per-issue fix loop
- State updates **only** via `$EVAL_CONTROL finish-dimension-probe`
- Do **not** dispatch subagents
