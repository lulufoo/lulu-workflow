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

> Evaluating-stage dimensions are composed from the active workflow profile's `dimension-defs/` (resolved via `--workflow` / `$EVAL_CONTROL` adapter).

---

## Bootstrap

1. Read `{$SKILL_ROOT}/eval/SKILL.md`
2. Read `{$SKILL_ROOT}/eval/issue-taxonomy.json`
3. Read `{$SKILL_ROOT}/eval/review.template.md`
4. Read `{$SKILL_ROOT}/eval/scripts/url_fetch.py` — use `read_ref()` for all URL/path loads
5. Read `{$SKILL_ROOT}/eval/scripts/codebase_sot.py` — use `resolve_codebase_ref()` for codebase SoT
6. Read `{$SKILL_ROOT}/eval/scripts/eval_target_units.py` — split EvalTarget **B** into intent units (chapter anchors); **do not** read `_facts.json` / `_chapters.json`
7. Run `$RESOLVE_PLAN_ROLE` with `CYCLE_ID` and `--profile {WORKFLOW_ID}`; apply Plan Scope Constraints for probe narrative
8. Follow steps below
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
   - `url` · `ref` (https URL or absolute local path) → `read_ref(ref, project_root=Path(PROJECT_ROOT))`
   - `codebase` · `ref.root` + `ref.strategy` → `resolve_codebase_ref(ref, project_root=Path(PROJECT_ROOT))` yields repo root; with `strategy: all`, read code files narrowly as needed (do not batch-load the entire repo)
4. Load EvalMethod **M**:
   - `external` · `source` (https URL or absolute path) → `read_ref(source, project_root=Path(PROJECT_ROOT))` as rubric
   - `builtin` · `source.procedure_id: codebase_consistency` → compare B against code read from codebase SoT root per `METHOD_FOCUS` (dimension-def may constrain probe scope, e.g. cite-only sub-sections)
   - `builtin` · `source.procedure_id: intent_gap_probes` → follow **intent_gap_probes** procedure below; criteria **A** from url SoT in `SOTS_JSON`

When `SOTS_JSON` is empty, **M** carries both rubric and basis.

---

## Step 2 — Generate issues list

Evaluate **B** using loaded SoT content and **M** / `METHOD_FOCUS`.

### intent_gap_probes

Builtin `procedure_id: intent_gap_probes`. Criteria **A** = first url SoT in `SOTS_JSON` (loaded via `read_ref`).

**Eval model (K3-d):** evaluate **B** only. Content units come from **B**'s chapter anchors. Do **not** open `_facts.json`, `_chapters.json`, `_body-*`, or call compose facts/chapters CLIs.

1. Load **A** from SoT (P1–P4 definitions and applicability in **A**; run any profile-specific supplements defined in **A** after applicable P probes).
2. Do **not** parse `<!-- state-vector: … -->`. Do **not** load `layer-standards` or L Diagnostic Criteria.
3. Read **B** from `EVAL_TARGET_PATH`. Build the unit view via `eval_target_units.units_from_eval_target(B_text)` (or CLI: `python3 {$SKILL_ROOT}/eval/scripts/eval_target_units.py --path "$EVAL_TARGET_PATH"`).
4. Branch on `shape`:
   - **`unknown`** → emit one `UNRESOLVABLE` (B has no chapter anchors); stop further P probes for this dim.
   - **`empty: true`** → treat as empty artifact; apply **A** only where empty content still applies; otherwise no P findings.
   - **`chapter`** → follow **Chapter path** below (no section-registry).
5. For each finding classify `root_cause` per `eval/SKILL.md` and fill all required columns.
6. `sot_ref` → framework doc `#P{n}` or `#D{n}`; `description` → Gap output from **A**.
7. `location` → unit `id` (e.g. `chap-a#1`), not line numbers alone.

#### Chapter path (EvalTarget B)

Traverse `containers` in **document order** (not registry `section_order`).

For each container `C` with units `U`:

1. For each unit in `U`, run applicable probes per **A** (`Applies when`).
2. **P3:** upstream = `prior_container_units(view, C.id)` (all units from earlier chapters). If no prior chapters, P3 upstream is empty (skip P3 when **A** requires upstream).
3. **Severity** (chapter ↔ old section_order skeleton; use `severity_hints_chapter(view, C.id)`):
   - P1 fail on first container → `high`
   - P1 fail on a container with `has_prior` → `high`
   - P2 fail when `before_last` → `high`
   - P3 fail when `has_prior` → `high`
   - P4 fail on last container → `high`
   - P1/P2 fail on late approach-style containers → `medium`
   - P4 edge cases on early direction-style containers → `medium`
4. Optional: on last container — sanity-check verifiable action or file reference.

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
