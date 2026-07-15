---
name: g2-grounding-runner
description: >-
  DEPRECATED optional read-only subagent for legacy inductive Gate 2 topology
  grounding. Prefer attach-code-refs inside Class 2 processing. Validates confirmed
  shape claims (from section JSON / checkpoint) against observed code topology,
  writes a thin g2-topology-report.json verdict. Does not interact with the user.
---

# g2-grounding-runner

> **Deprecated (section-SoT):** Independent G2 is folded into Class 2 `attach-code-refs` (design Turn 44). Prefer **not** to dispatch this runner. Kept only for optional legacy topology passes when a report must exist for `verdict=ok` close.

Terminal runner subagent. Dispatched from **inline** inductive-runner at Gate 2 only when the parent explicitly chooses the legacy path (one subagent per G2 pass).

**Scope:** This SKILL registers **`$INDUCTIVE_G2_CTL` only** (write report). It does **not** register `$INDUCTIVE_GATE_CTL`. Check/list and gate-close/reopen are **parent** (`inductive-runner`) steps — not subagent commands.

## Shared report contract

Report field contract, thinness limits, and validation live in `g2_topology_report_schema.py` (read-only reference — write only via `$INDUCTIVE_G2_CTL record-g2-report`).

**Hard boundaries (never violate):**
- Read-only — no `add-open`, no section mutation, no gate-close.
- Topology only — no line-level detail in `facts`; `code_refs` belong in `divergences` only.
- No whole-file reads — Grep/symbol locate, then Read minimal line ranges if needed.
- **To-Be gaps are not breaking** — unimplemented future structure is for Gate 3, not G2.
- **Breaking = direct contradiction** with Shape-confirm claims from `_facts.json` / checkpoint — **not** with DQI as SoT.

## Required Inputs

Plain-text block from the orchestrating inductive-runner:

```
INDUCTIVE_OUT_DIR     absolute path to revision{N}/ inductive state bundle
COMPOSE_PROFILE       compose profile id
CYCLE_ID              active cycle id
PROJECT_ROOT          absolute project root, resolved by the orchestrator
```

Self-resolved: `$SKILL_ROOT` from workflow install path.

Do **not** paste shape claims in the Task prompt — read section JSON / `_index.json` from disk.

## Script Macros

| Macro | Command |
|-------|---------|
| `$INDUCTIVE_G2_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g2_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |

## Pipeline

1. Read `$INDUCTIVE_OUT_DIR/inductive-scope/_index.json` → require `last_checkpoint == "shape"`. Load coarse shape claims from `$INDUCTIVE_OUT_DIR/_facts.json` filtered by relevant `lens_tags` (I/ST/SC etc.). Maturity `<S>.json` is status/frontier only — not body. DQI `architecture_view` / `shape_constraints` are **optional non-authoritative hints only** — never the sole SSOT.
2. `$FETCH_COMPOSE --role inductive-scan-criteria` → `SCAN_CRITERIA` (topology scan methods if needed).
3. Read-only scan: confirm spine / To-Be topology blocks exist or can exist; key relations are plausible.
4. Optionally record checklist rows (`confirmed` | `not_applicable` | `contradiction`) against the section-derived claims.
5. If a **shape-breaking** contradiction exists → build report with `verdict: shape_breaking` and `divergences[]` (each with `shape_claim`, `finding`, optional `code_refs`).
6. Otherwise → `verdict: ok` with up to 5 topology-level `facts[]` (no line numbers in facts).
7. `$INDUCTIVE_G2_CTL record-g2-report --json '<report object>'`.
8. Return the compact template below — **stop**. Do not run any further control commands.

**Forbidden after step 7 (never violate):**
- Any `check-g2-report` or `list-g2-report` — **subagent never**; parent runs `$INDUCTIVE_GATE_CTL g2-check-report` / `g2-list-report` after you return (see `inductive-runner` Gate 2).
- `$INDUCTIVE_GATE_CTL` — subagent does not register or call the parent gate macro.
- Highlights, bullet summaries, user-facing prose, or any content beyond the Return template.
- Re-stating `facts` / `divergences` in Task return — they live in `g2-topology-report.json`; parent reads them via gate facade only.

## Return

Return **exactly** this shape (substitute values only; no extra lines, headings, or markdown):

```
g2-grounding complete.
verdict: ok | shape_breaking
facts: <N> | divergences: <N>
written: g2-topology-report.json
```

Stop after the Return template. **Do not** run check/list or gate commands — the orchestrating inductive-runner continues Gate 2 with `$INDUCTIVE_GATE_CTL g2-check-report`, then `g2-list-report`, then `gate-close G2` or `gate-reopen G1`.
