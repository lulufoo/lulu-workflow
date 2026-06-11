---
rule-guard:
  globs:
    - "**/*.md"
description: >
  Single-round evaluation executor for lulu-dev-workflow tech-plan sessions.
  Invoked by tech-plan/SKILL.md eval-rules per evaluation round.
  Evaluates e1 (product intent) or e2 (codebase consistency). e3 deprecated in Phase 2.
---

# eval-runner/SKILL.md

> **e3 deprecated (Phase 2):** replaced by Round Iteration Prober. This runner evaluates **e1** or **e2** only.

Terminal runner subagent. Evaluates **one dimension** (`e1` or `e2`) per invocation.

---

## Required Inputs

```
DIMENSION           e1 | e2
TECH_DOC_PATH       absolute path to the revision tech-doc.md
EVALUATE_STATE_PATH absolute path to revision{N}/evaluate-state.md
EVALUATE_DIR        absolute path to revision{N}/evaluate{M}/
EXECUTION_MODE      guided | autonomous
```

Dimension-specific:

| Dimension | Additional inputs |
|-----------|------------------|
| `e1` | `PRODUCT_REF`, `TEMPLATE_SECTION` (`tech-plan`), `TEMPLATE_KEY` (`ptc_url`), `PROJECT_ROOT` |
| `e2` | `PROJECT_ROOT` (read `TECH_DOC_PATH` to identify relevant code paths — see Step 1 e2 rule) |

---

## Step 1 — Load context

- Read `TECH_DOC_PATH`
- For `e2`: locate relevant code entry points using the following priority rule:
  - **v2 template** (contains `## Approach Skeleton` or `## Tasks` headings): parse those sections to identify relevant code files
  - **legacy template** (contains `§5` / `§6` headings): parse `§5 Data Flow` and `§6 API / Interfaces` instead
  - Read the identified code files
- For `e1`: read `PRODUCT_REF`; use `$FETCH_TEMPLATE {TEMPLATE_SECTION} {TEMPLATE_KEY}`; read stdout as PTC framework

---

## Step 2 — Generate issues list

Evaluate the dimension against `TECH_DOC_PATH` and loaded references.

| Dim | Focus |
|-----|-------|
| `e1` | Intent alignment — does the tech design faithfully implement the product requirements? |
| `e2` | Codebase consistency — does the design align with existing code structure / conventions? |

Output: ordered list of issues, each with:
- `id`: e.g. `e2-1`, `e2-2`
- `location`: section / line ref in `tech-doc.md`
- `severity`: `critical` | `medium` | `minor`
- `description`: concise statement of the problem

---

## Step 3 — Write review skeleton

Path: `{EVALUATE_DIR}/tech-review-e{M}{DIM_N}.md`
where `DIM_N` = dimension index (e1→1, e2→2).

```markdown
# Tech Review — {DIMENSION upper} | Round {M}

| ID | Location | Severity | Description | Status | Decision |
|----|----------|----------|-------------|--------|----------|
| e{N}-1 | § | critical | … | Pending | — |
| e{N}-2 | § | medium   | … | Pending | — |
```

Write `{dim}_total_issues: K` to `evaluate-state.md`.

---

## Step 4 — Per-issue fix loop (E5)

For each issue row in order:

### guided mode

Present `AskQuestion`:

```
Issue {id}: {description}
Location: {location} | Severity: {severity}

Option A — Fix: apply fix to tech-doc.md
Option B — Ignore: skip this issue
Option C — Abandon: stop evaluation for this dimension
```

- `Option A` → fix `TECH_DOC_PATH`, update row: `Status: ✅ Fixed`, `Decision: fix`
- `Option B` → update row: `Status: Ignored`, `Decision: ignore`
- `Option C` → write `evaluate-state.md: current_dimension: abandoned` → STOP

### autonomous mode

Auto-apply Option A for all issues unless severity is `minor` and the fix would require structural changes. Log reasoning inline in the review file.

On any unrecoverable error, write `current_dimension: abandoned` → STOP.

---

## Step 5 — Finalize dimension

After all issues processed (or skipped):

1. Count rows with `Decision: fix` → write `{dim}_resolved_issues` in `evaluate-state.md`
2. Write `{dim}_status: complete` in `evaluate-state.md`
3. Update aggregate `resolved_issues` (sum all dims resolved so far)

Do **not** write `workflow-state.md` — parent (`eval-rules.md`) owns that transition.
