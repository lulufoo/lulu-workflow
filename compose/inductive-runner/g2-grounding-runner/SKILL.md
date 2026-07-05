---
name: g2-grounding-runner
description: >-
  Read-only subagent for inductive Gate 2 topology grounding. Validates the
  confirmed shape spine against observed code topology, writes a thin
  g2-topology-report.json verdict to disk. Does not interact with the user.
---

# g2-grounding-runner

Terminal runner subagent. Dispatched from **inline** inductive-runner at Gate 2 (one subagent per G2 pass).

**Scope:** This SKILL registers **`$INDUCTIVE_G2_CTL` only** (write report). It does **not** register `$INDUCTIVE_GATE_CTL`. Check/list and gate-close/reopen are **parent** (`inductive-runner`) steps — not subagent commands.

## Shared report contract

Report field contract, thinness limits, and validation live in `g2_topology_report_schema.py` (read-only reference — write only via `$INDUCTIVE_G2_CTL record-g2-report`).

**Hard boundaries (never violate):**
- Read-only — no EP registration, no section mutation, no gate-close.
- Topology only — no line-level detail in `facts`; `code_refs` belong in `divergences` only.
- No whole-file reads — Grep/symbol locate, then Read minimal line ranges if needed.
- **To-Be gaps are not breaking** — unimplemented future structure is for Gate 3, not G2.
- **Breaking = direct contradiction** with G1 `architecture_view` or `shape_constraints` only.

## Required Inputs

Plain-text block from the orchestrating inductive-runner:

```
INDUCTIVE_OUT_DIR     absolute path to revision{N}/ inductive state bundle
COMPOSE_PROFILE       compose profile id
CYCLE_ID              active cycle id
PROJECT_ROOT          project root (usually $(pwd))
```

Self-resolved: `$SKILL_ROOT` from workflow install path.

Do **not** paste `architecture_view` or `shape_constraints` in the Task prompt — read them from `$INDUCTIVE_OUT_DIR/inductive-dqi.json`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$INDUCTIVE_G2_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g2_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$PROJECT_ROOT" --cycle-id "$CYCLE_ID"` |

## Pipeline

1. Read `$INDUCTIVE_OUT_DIR/inductive-dqi.json` → `architecture_view` + `shape_constraints` (G1 SSOT for shape claims).
2. `$FETCH_COMPOSE --role inductive-scan-criteria` → `SCAN_CRITERIA` (topology scan methods if needed).
3. Read-only scan: confirm spine / To-Be topology blocks exist or can exist; key relations are plausible.
4. For each `shape_constraints[]` entry, optionally record a checklist row (`confirmed` | `not_applicable` | `contradiction`).
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
