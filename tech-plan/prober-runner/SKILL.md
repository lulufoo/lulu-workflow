---
name: prober-runner
description: >-
  Round Iteration prober for tech-plan drafting. Probes only the active section
  (section-gated): KW sub-section scan plus section-level Upstream comparison,
  writes probe-{seq}.json under round-{N}/{section}/.
---

# prober-runner

**Pipeline:** Load context → KW diagnose → Upstream diagnose → Merge anchors → Write probe report → Return.

One invocation = one probe pass on **one section** (`ACTIVE_SECTION`). Read-only on tech-doc.

## Scope

**In scope**

- Load `$CTX`, section KW criteria, section dependency graph, plan role, `ACTIVE_SECTION`
- **Step 2 — KW:** sub-section scan (KW0→KW4)
- **Step 2b — Upstream:** section-level Violation + Coverage vs **stable** upstream sections only
- Merge anchors; write `write-probe-report`

**Out of scope**

- Probe sections other than `ACTIVE_SECTION`
- Upstream when any `kw0_pending` in this section (skip Step 2b)
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

## Command Index

| Step | Macro calls |
|------|-------------|
| 1 | `read-context` · `read-section-pointer` · `read-upstream-context` · `read-section-body` · `resolve-role` · `section-kw-criteria` |
| 3 | `update-anchor-status` |
| 4 | `write-probe-report` |

`read-context` → `$CTX.skips` (skip ledger with `skip_key`).

`read-section-body --section {ACTIVE_SECTION}` → active section `body` (located by `<!-- section-key:… -->`; do not grep H2 display titles).

Dependency graph SSOT: `$FETCH_TECH_PLAN section-registry` (`tpt_section_registry_url`). Exposed via `read-upstream-context`.

## Step 1 — Load context

Verify `ACTIVE_SECTION` == pointer `active_section`.

`read-upstream-context` → `stable_upstream` edges for Upstream pass.

`read-section-body --section {ACTIVE_SECTION}` → full active section body for KW split.

`$FETCH_TECH_PLAN section-kw-criteria` → locate `## {ACTIVE_SECTION}` block (section **key**, not tech-doc display title).

Build `$SKIP_KEYS` = non-empty `skip_key` values from `$CTX.skips`.

## Step 2 — KW diagnose (sub-section)

Split sub-sections within active section body, KW0→KW4, emit `gap_kind: kw | kw0_pending`.

- **Skip** sub-section when its `skip_key` ∈ `$SKIP_KEYS` (ledger from prior skip decisions).

Collect KW items first. **If any `kw0_pending` → skip Step 2b entirely.**

## Step 2b — Upstream diagnose (section-level)

Only when Step 2 has **no** `kw0_pending`.

For each edge in `stable_upstream`:

- **Skip** upstream pair when `skip_key` `{ACTIVE_SECTION}:upstream:{upstream}` ∈ `$SKIP_KEYS`.

1. Load **full section body** via `read-section-body` for `ACTIVE_SECTION` and each stable `upstream_section`.
2. **Violation** (`upstream_violation`): current section contradicts upstream intent/constraints per `upstream_relation`.
3. **Coverage** (`upstream_coverage`): upstream intent not operationalized/supported by current section as a whole.

Emit items:

```json
{
  "id": "{section_key}-U-{upstream_section}-1",
  "gap_kind": "upstream_coverage",
  "scope": "section",
  "section_key": "{section_key}",
  "upstream_section": "{upstream_section}",
  "upstream_relation": "{upstream_relation}",
  "intent_gap": "...",
  "upstream_criteria": {
    "upstream_intent": "...",
    "expected": "...",
    "observed": "..."
  },
  "sub_section_text": "{ACTIVE_SECTION full body}",
  "sub_section_summary": "{section_key} upstream coverage vs {upstream_section}",
  "skip_key": "{section_key}:upstream:{upstream_section}",
  "status": "open",
  "decision": "—"
}
```

Id pattern: `{section}-U-{upstream}-{n}`. Violation items before coverage for same upstream.

## Step 3 — Anchor merge

Unchanged; scope to active section.

## Step 4 — Write probe report

Merge KW items then Upstream items. Include `upstream_open_count` in return summary.

**Return footer:** Open gaps · KW0 pending · **Upstream open**
