---
name: prober-runner
description: >-
  Round Iteration prober for tech-plan drafting. Probes only the active section
  (section-gated): KW sub-section scan, section-level Upstream comparison, and
  decision-doc intent check; writes probe-{seq}.json under round-{N}/{section}/.
---

# prober-runner

**Pipeline:** Load context → KW diagnose → Upstream diagnose → Decision intent diagnose → Merge anchors → Write probe report → Return.

One invocation = one probe pass on **one section** (`ACTIVE_SECTION`). Read-only on tech-doc.

## Scope

**In scope**

- Load `$CTX`, section KW criteria, section dependency graph, plan role, `ACTIVE_SECTION`, decision-doc; when `$CTX.design_doc_path` is present, read design-doc full text as supplementary context (decision-doc remains SSOT)
- **Step 2 — KW:** sub-section scan (KW0→KW4)
- **Step 2b — Upstream:** section-level Violation + Coverage vs **stable** upstream sections only
- **Step 2c — Decision intent:** section-level coverage/violation vs decision-doc (when no KW0 pending)
- Merge anchors; write `write-probe-report`

**Out of scope**

- Probe sections other than `ACTIVE_SECTION`
- Step 2b / 2c when any `kw0_pending` in this section
- Upstream vs non-stable upstream sections
- Write tech-doc; advance pointer; dispatch refiner

## Parent-Provided Inputs

| Variable | Purpose |
|----------|---------|
| `CYCLE_DIR` | Cycle cache dir |
| `CYCLE_ID` | Cycle id |
| `ROUND_N` | Current round |
| `ROUND_DIR` | `revision{R}/round-{N}/` |
| `ACTIVE_SECTION` | Section key to probe |
| `TECH_DOC_PATH` | tech-doc (read-only) |

## Script Macros

| Step | Macro calls |
|------|-------------|
| 1 | `read-context` · `read-section-pointer` · `read-upstream-context` · `read-section-body` · `resolve-role` · `section-kw-criteria` |
| 3 | `update-anchor-status` |
| 4 | `write-probe-report` |

`read-context` → `$CTX.skips`, `$CTX.decision_doc_path`, optional `$CTX.design_doc_path`.

`read-section-body --section {ACTIVE_SECTION}` → active section `body` (located by `<!-- section-key:… -->`; do not grep H2 display titles).

Dependency graph SSOT: `$FETCH_TECH_PLAN section-registry` (`tpt_section_registry_url`). Exposed via `read-upstream-context`.

## Step 1 — Load context

Verify `ACTIVE_SECTION` == pointer `active_section`.

Read decision-doc **full text** from `$CTX.decision_doc_path` once; keep for Step 2c.

`read-upstream-context` → `stable_upstream` edges for Upstream pass.

`read-section-body --section {ACTIVE_SECTION}` → full active section body for KW split and intent pass.

`$FETCH_TECH_PLAN section-kw-criteria` → locate `## {ACTIVE_SECTION}` block (section **key**, not tech-doc display title).

Build `$SKIP_KEYS` = non-empty `skip_key` values from `$CTX.skips`.

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

## Step 2c — Decision intent diagnose (section-level)

Only when Step 2 has **no** `kw0_pending` (same gate as Step 2b).

**Input:** decision-doc full text · active section body · `## {ACTIVE_SECTION}` kw block · registry `intent` and `intent_boundary` for section (`python3 section_registry_schema.py --section-intent {ACTIVE_SECTION}` / `--section-intent-boundary`; or parse `$FETCH_TECH_PLAN section-registry` JSON).

**Skip** when `skip_key` `{ACTIVE_SECTION}:intent:{slug}` ∈ `$SKIP_KEYS`.

Compare active section (whole body) against decision-doc. Emit at most one open item per distinct gap; **violation before coverage**.

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

Merge **KW items → Upstream items → Decision intent items**. Include open counts in return summary.

**Return footer:** Open gaps · KW0 pending · Upstream open · **Intent open**
