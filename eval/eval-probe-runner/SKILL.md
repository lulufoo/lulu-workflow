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

> Evaluating-stage dimensions are composed from the active workflow adapter's `dimension-defs/` (resolved via caller-supplied adapter config / `$EVAL_CONTROL`).

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Read `{$SKILL_ROOT}/eval/scripts/url_fetch.py` — use `read_ref()` for all URL/path loads
5. Read `{$SKILL_ROOT}/eval/scripts/codebase_sot.py` — use `resolve_codebase_ref()` for codebase SoT
6. Run `$RESOLVE_ROLE` and `$RESOLVE_DOMAIN` with `CYCLE_ID` and `--profile {WORKFLOW_ID}`; apply Scope Constraints (role + domain) for probe narrative
7. Follow steps below
---

## Required Inputs

Plain-text block from `$EVAL_CONTROL begin-dimension` (all lines required unless noted):

```
WORKFLOW_ID           active compose profile id (e.g. lulu-plan, lulu-arch)
DIMENSION_ID          canonical dimension id (e.g. codebase-consistency)
DIMENSION             dispatch key for finish-dimension-probe (legacy e1/e2/e3 or id)
DIMENSION_LABEL       human-readable label for review header
CYCLE_ID              cycle identifier
CYCLE_TYPE            topic | feature
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

Optional field (when dimension SoT requires an upstream baseline document):

```
UPSTREAM_BASELINE_REF absolute path to upstream baseline doc (from adapter session context)
```

---

## Step 1 — Load context

1. Read `EVAL_TARGET_PATH` (EvalTarget **B**).
2. Parse `SOTS_JSON` and `METHOD_JSON`.
3. Load each EvalSoT:
   - `url` · `ref` (https URL, absolute path, or `PROJECT_ROOT`-relative path) → `read_ref(ref, project_root=Path(PROJECT_ROOT))`
   - `codebase` · `ref.root` + `ref.strategy` → `resolve_codebase_ref(ref, project_root=Path(PROJECT_ROOT))` yields repo root; with `strategy: all`, read code files narrowly as needed (do not batch-load the entire repo)
4. Load EvalMethod **M**:
   - `external` · `source` (https URL, absolute path, or `PROJECT_ROOT`-relative path) → `read_ref(source, project_root=Path(PROJECT_ROOT))` as the EvalMethod
   - `builtin` · `source.procedure_id: codebase_consistency` → compare B against code read from codebase SoT root per `METHOD_FOCUS` (dimension-def may constrain probe scope, e.g. cite-only sub-sections)
   - other `builtin` procedures → STOP and report an unsupported procedure id

When `SOTS_JSON` is empty, **M** carries both rubric and basis.

---

## Step 2 — Generate issues list

For an `external` EvalMethod, follow its procedure to evaluate **B** using every loaded SoT. The Method must define its unit model, traversal, SoT usage, severity rules, and required issue fields.

For `codebase_consistency`, follow the builtin procedure loaded in Step 1.

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
