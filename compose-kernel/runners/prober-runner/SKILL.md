---
name: prober-runner
description: >-
  Round Iteration prober for compose-profile drafting. Probes only the active
  section (section-gated): KW sub-section scan, section-level Upstream
  comparison, and decision-doc intent check; writes probe-{seq}.json under
  round-{N}/{section}/.
---

# prober-runner

**Pipeline:** Load context → KW diagnose → Upstream diagnose → Decision intent diagnose → Merge anchors → Write probe report → Return.

One invocation = one probe pass on **one section** (`ACTIVE_SECTION`). Read-only on the compose document (`COMPOSE_DOC_PATH`).

**Profile:** Use the **same** `--profile` as parent `$ROUND_CONTROL` on every `$FETCH_COMPOSE` call in this runner.

## Scope

**In scope**

- Load `$CTX`, section KW criteria, section dependency graph, plan role, `ACTIVE_SECTION`, scope doc (`$CTX.scope_doc_path`)
- **Step 2 — KW:** sub-section scan (KW0→KW4)
- **Step 2b — Upstream:** section-level Violation + Coverage vs **stable** upstream sections only
- **Step 2c — Scope intent:** section-level coverage/violation vs scope doc (when no KW0 pending)
- Merge anchors; write `write-probe-report`

**Out of scope**

- Probe sections other than `ACTIVE_SECTION`
- Step 2b / 2c when any `kw0_pending` in this section
- Upstream vs non-stable upstream sections
- Write compose document; advance pointer; dispatch refiner

## Parent-Provided Inputs

| Variable | Purpose |
|----------|---------|
| `CYCLE_DIR` | Cycle cache dir |
| `CYCLE_ID` | Cycle id |
| `ROUND_N` | Current round |
| `ROUND_DIR` | `revision{R}/round-{N}/` |
| `ACTIVE_SECTION` | Section key to probe |
| `COMPOSE_DOC_PATH` | Active compose doc (`tech-doc.md` or `design-doc.md`; read-only) |

## Script Macros

`$FETCH_COMPOSE` / `$ROUND_CONTROL`: `{SKILL_ROOT}/compose-kernel/SKILL.md` → Script Macros.

Pass **`--profile`** on `$FETCH_COMPOSE` to match parent `$ROUND_CONTROL`.

| Step | Macro calls |
|------|-------------|
| 0 | `$FETCH_COMPOSE structural-probe-criteria` → criteria path · `python3 structural_probe.py run --doc-path … --section {ACTIVE_SECTION} --criteria …` |
| 1 | `$ROUND_CONTROL`: `read-context` · `read-section-pointer` · `read-upstream-context` · `read-section-body` · `$FETCH_COMPOSE section-kw-criteria` |
| 3 | `update-anchor-status` |
| 4 | `write-probe-report` |

`read-context` → `$CTX.skips`, `$CTX.scope_doc_path`, `$CTX.delivered_refs` (Eval inventory; not compose SSOT).

`read-section-body --section {ACTIVE_SECTION}` → active section `body` (located by `<!-- section-key:… -->`; do not grep H2 display titles).

Dependency graph SSOT: `$FETCH_COMPOSE section-registry` with matching `--profile`. Exposed via `read-upstream-context`.

`structural_probe.py` output items → merged into probe report as `gap_kind: structural` with `repair_class: mechanical`, `fix_mode: auto`. Structural items use id pattern `{ACTIVE_SECTION}-S-{check_id}-{slug}`.

## Step 0 — Structural pre-probe

Run **after Step 1** has built `$SKIP_KEYS`.

1. `$FETCH_COMPOSE structural-probe-criteria --profile <same as $ROUND_CONTROL>` → resolve criteria file path.
   - If fetch fails because profile lacks `framework_templates.structural-probe-criteria`, skip Step 0 silently.
2. Run:
   ```
   python3 structural_probe.py run \
       --doc-path {COMPOSE_DOC_PATH} \
       --section {ACTIVE_SECTION} \
       --criteria <criteria_path>
   ```
3. Pin stdout items as `$STRUCTURAL_ITEMS_RAW`. If exit code ≠ 0, emit a warning and continue with `$STRUCTURAL_ITEMS_RAW = []`.
4. After Step 1 builds `$SKIP_KEYS`, filter `$STRUCTURAL_ITEMS_RAW` → `$STRUCTURAL_ITEMS` where `skip_key` ∉ `$SKIP_KEYS`. Carry `$STRUCTURAL_ITEMS` into Step 4 merge.

**If any structural items are found**: do **not** block Step 2/2b/2c. Structural and semantic probes run independently; both feed Step 4.

## Step 1 — Load context

Verify `ACTIVE_SECTION` == pointer `active_section`.

Read scope doc **full text** from `$CTX.scope_doc_path` once; keep for Step 2c.

`read-upstream-context` → `stable_upstream` edges for Upstream pass.

`read-section-body --section {ACTIVE_SECTION}` → full active section body for KW split and intent pass.

`$FETCH_COMPOSE section-kw-criteria --profile <same as $ROUND_CONTROL>` → locate `## {ACTIVE_SECTION}` block (section **key**, not document display title).

Build `$SKIP_KEYS` = non-empty `skip_key` values from `$CTX.skips`.

Filter `$STRUCTURAL_ITEMS_RAW` (from Step 0) → `$STRUCTURAL_ITEMS` where `skip_key` ∉ `$SKIP_KEYS`.

## Step 2 — KW diagnose (sub-section)

Split sub-sections within active section body, KW0→KW4, emit `gap_kind: kw | kw0_pending`.

- **Skip** sub-section when its `skip_key` ∈ `$SKIP_KEYS` (ledger from prior skip decisions).

Collect KW items first. **If any `kw0_pending` → skip Step 2b and Step 2c entirely.**

## Step 2b — Upstream diagnose (section-level)

Only when Step 2 has **no** `kw0_pending`.

For each edge in `stable_upstream`:

- **Skip** upstream pair when `skip_key` `{ACTIVE_SECTION}:upstream:{upstream}` ∈ `$SKIP_KEYS`.

1. Load **full section body** via `read-section-body` for `ACTIVE_SECTION` and each stable `upstream_section`.
2. **Violation** (`upstream_violation`): current section contradicts upstream intent/constraints per `upstream_relation`.
3. **Coverage** (`upstream_coverage`): upstream intent not operationalized/supported by current section as a whole.

Emit items (see Step 4 merge). Id pattern: `{section}-U-{upstream}-{n}`. Violation before coverage for same upstream.

## Step 2c — Scope intent diagnose (section-level)

Only when Step 2 has **no** `kw0_pending` (same gate as Step 2b).

**Input:** scope doc full text · active section body · `## {ACTIVE_SECTION}` kw block · registry `intent` and `intent_boundary` for section (`python3 section_registry_schema.py --section-intent {ACTIVE_SECTION}` / `--section-intent-boundary`; or parse `$FETCH_COMPOSE section-registry` JSON).

**Skip** when `skip_key` `{ACTIVE_SECTION}:intent:{slug}` ∈ `$SKIP_KEYS`.

Compare active section (whole body) against scope doc. Emit at most one open item per distinct gap; **violation before coverage**.

| gap_kind | When |
|----------|------|
| `intent_violation` | Section contradicts decision exclusions, rejected alternatives, or explicit out-of-scope |
| `intent_coverage` | Decision direction/scope/constraint for this section type not operationalized in body |
| `intent_coverage` | Decision acceptance criterion (AC) with no trace in Tasks section body (when probing Tasks) |

Reference decision headings or AC ids in `intent_gap` / `intent_criteria.decision_intent` — no fixed binding spec.

Example item:

```json
{
  "id": "{section_key}-D-1",
  "gap_kind": "intent_coverage",
  "scope": "section",
  "section_key": "{section_key}",
  "upstream_section": null,
  "upstream_relation": null,
  "upstream_criteria": null,
  "intent_criteria": {
    "decision_intent": "Decision heading or AC id (paraphrase)",
    "expected": "How this section should reflect it",
    "observed": "What the body actually shows"
  },
  "intent_gap": "...",
  "sub_section_text": "{ACTIVE_SECTION full body}",
  "sub_section_summary": "{section_key} vs decision {decision_intent short}",
  "skip_key": "{section_key}:intent:{slug}",
  "status": "open",
  "decision": "—"
}
```

Id pattern: `{section_key}-D-{n}`.

## Step 3 — Anchor merge

Unchanged; scope to active section.

## Step 4 — Write probe report

Merge **Structural items → KW items → Upstream items → Decision intent items**. Structural items lead the list so `repair_class: mechanical` gaps surface first.

Every item in the report carries `repair_class`, `fix_mode`, `handled_by` (initially `null`), and `degraded_from` (initially `null`) as per schema v3.

Include open counts in return summary.

**Return footer:** Open gaps · Structural open · KW0 pending · Upstream open · **Intent open**
