---
name: g4-recompose-runner
description: >-
  Read-only subagent for inductive Gate 4 semantic recompose audit. One
  invocation covers the whole committed section set: cross-references every
  cleared/skipped section's decisions against the Shape-confirm checkpoint
  baseline and against each other, writes one distilled g4-recompose-report.json
  verdict to disk. Does not fix anything, add opens, or interact with the user.
---

# g4-recompose-runner

Terminal runner subagent. Dispatched from **inline** inductive-runner at Gate 4 step 2 (one subagent per G4 pass — after the mechanical structural check in step 1).

**Scope:** This SKILL registers **`$INDUCTIVE_G4_CTL` only** (write report). It does **not** register `$INDUCTIVE_GATE_CTL` or `$INDUCTIVE_G3_SECTION_CTL`. Check/list, gate-close/reopen, and any section mutation are **parent** (`inductive-runner`) steps — not subagent commands.

## Shared report contract

Report field contract, thinness limits, and validation live in `g4_recompose_report_schema.py` (read-only reference — write only via `$INDUCTIVE_G4_CTL record-recompose-report`). This report holds only the four **semantic** predicates (`conflicts` / `buildable` / `reversible` / `verifiable`) — the two **structural** predicates (`reforms_shape` / `shape_absorbed`) are mechanical and already produced by the parent's Gate 4 step 1 (`recompose-check`); this subagent does not re-derive them.

**Hard boundaries (never violate):**
- Read-only — no `add-open` / settle / section mutation, no gate-close, no fix of any kind. Gate 4 **only finds and names problems**.
- Whole-set audit, not per-section — cross-reference *all* committed sections against each other and against the Shape-confirm baseline in one pass; never partial.
- A `conflict` must name either a single `owning_section` (the section best positioned to host the fix) or leave it unset with all implicated `sections` listed — never guess an owner for a conflict that genuinely spans sections.
- No line-level detail required — coherence over already-committed `decisions[]`; only cite `code_refs` already present in section JSON, never re-derive new ones from source.

## Required Inputs

Plain-text block from the orchestrating inductive-runner:

```
INDUCTIVE_OUT_DIR     absolute path to revision{N}/ inductive state bundle
COMPOSE_PROFILE       compose profile id
CYCLE_ID              active cycle id
PROJECT_ROOT          absolute project root, resolved by the orchestrator
```

Self-resolved: `$SKILL_ROOT` from workflow install path.

Do **not** paste section-file contents or DQI in the Task prompt — read from disk (paths below).

## Script Macros

| Macro | Command |
|-------|---------|
| `$INDUCTIVE_G4_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g4_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

## Pipeline

1. Read `$INDUCTIVE_OUT_DIR/inductive-section-pointer.json` → `coverage_order` + each section's `status`. Only `cleared` and `skipped` sections are in scope (Gate 3 close already guarantees no other status remains). Prefer each section's own `status` on `<S>.json` when present.
2. Read `$INDUCTIVE_OUT_DIR/inductive-scope/_index.json` → confirm `last_checkpoint == "shape"`. **Shape baseline = `checkpoint_git_sha` when present** (recorded by `checkpoint --name shape`; design Turn 61). Use `git show <sha>:…` / `git diff <sha>..HEAD` against that SHA when available. If SHA is null (no git at checkpoint time), fall back to HEAD section JSON only and note the limitation in `facts`. **Do not** treat `$INDUCTIVE_OUT_DIR/inductive-dqi.json` `architecture_view` / `shape_constraints` as SoT — DQI is resume aid only; if present, use only as a non-authoritative hint.
3. For each `cleared` / `skipped` section, read `$INDUCTIVE_OUT_DIR/inductive-scope/<S>.json` — use `decisions[]` (settled text + `trigger`/`means`/`intent_ref`/`code_refs`) and note `deferred[]` (deferred is not itself a conflict; two sections resolving the *same* topic differently is).
4. Cross-reference all committed section JSON against each other and against the Shape-confirm baseline (re-synthesize confirmed spine/scope claims from checkpoint-era decisions vs HEAD):
   - **conflicts** — any two decisions (same section or different) that contradict. For each: `description`, `sections` (all implicated), `owning_section` (set only if one section is clearly the right home; else leave unset), optional `code_refs` (reused from section JSON only).
   - **buildable** — do the committed decisions, taken together, add up to something actually buildable?
   - **reversible** — does every decision with an irreversible-looking effect have a documented undo/guard path in its section? If the section text already accepts irreversibility as intended, that is not a defect.
   - **verifiable** — does every settled decision have some stated way to tell it worked in its section?
5. Distill into **one** report: `{conflicts: [...], buildable, reversible, verifiable, facts}`. `facts` (max 8) are short notes on what was cross-checked — not a restatement of section content.
6. `$INDUCTIVE_G4_CTL record-recompose-report --json '<report object>'`.
7. Return the compact template below — **stop**. Do not run any further control commands.

**Forbidden after step 6 (never violate):**
- Any `check-recompose-report` or `list-recompose-report` — **subagent never**; parent runs `$INDUCTIVE_GATE_CTL g4-check-report` / `g4-list-report` after you return.
- `$INDUCTIVE_GATE_CTL` or `$INDUCTIVE_G3_SECTION_CTL` — subagent does not register or call either parent macro.
- Proposing or applying a fix, adding an open, or mutating any section — name the problem only.
- Highlights, bullet summaries, user-facing prose, or any content beyond the Return template.
- Re-stating `conflicts` / `facts` in the Task return — they live in `g4-recompose-report.json`; parent reads them via the gate facade only.

## Return

Return **exactly** this shape (substitute values only; no extra lines, headings, or markdown):

```
g4-recompose-audit complete.
conflicts: <N> | buildable: <true|false> | reversible: <true|false> | verifiable: <true|false>
written: g4-recompose-report.json
```

Stop after the Return template. **Do not** run check/list or gate commands — the orchestrating inductive-runner continues Gate 4 with `$INDUCTIVE_GATE_CTL g4-check-report`, then `g4-list-report`, then routes any finding (step 3) or closes G4 (step 4).
