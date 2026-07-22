---
name: g4-recompose-runner
description: >-
  Read-only subagent for inductive Gate 4 semantic recompose audit. One
  invocation covers the whole committed lens set: cross-references every
  cleared/skipped lens's facts (and deferred opens) against the Shape-confirm
  checkpoint baseline and against each other, writes one distilled
  g4-recompose-report.json verdict to disk. Does not fix anything, add opens,
  or interact with the user.
---

# g4-recompose-runner

Terminal runner subagent. Dispatched from **inline** inductive-runner at Gate 4 step 2 (one subagent per G4 pass — after the mechanical structural check in step 1).

**Scope:** This SKILL registers **`$INDUCTIVE_G4_CTL` only** (write report). It does **not** register `$INDUCTIVE_GATE_CTL` or `$INDUCTIVE_G3_SECTION_CTL`. Check/list, gate-close/reopen, and any section mutation are **parent** (`inductive-runner`) steps — not subagent commands.

## Shared report contract

Report field contract, thinness limits, and validation live in `g4_recompose_report_schema.py` (read-only reference — write only via `$INDUCTIVE_G4_CTL record-recompose-report`). This report holds only the four **semantic** predicates (`conflicts` / `buildable` / `reversible` / `verifiable`) — the two **structural** predicates (`reforms_shape` / `shape_absorbed`) are mechanical and already produced by the parent's Gate 4 step 1 (`recompose-check`); this subagent does not re-derive them.

**Hard boundaries (never violate):**
- Read-only — no `add-open` / settle / section mutation, no gate-close, no fix of any kind. Gate 4 **only finds and names problems**.
- Whole-set audit, not per-section — cross-reference *all* committed lenses against each other and against the Shape-confirm baseline in one pass; never partial.
- A `conflict` must name either a single `owning_section` (the lens best positioned to host the fix) or leave it unset with all implicated `sections` listed — never guess an owner for a conflict that genuinely spans lenses.
- No line-level detail required — coherence over already-committed **facts**; only cite `code_refs` already present on related opens, never re-derive new ones from source.

## Required Inputs

Plain-text block from the orchestrating inductive-runner:

```
INDUCTIVE_OUT_DIR     absolute path to revision{N}/ inductive state bundle
COMPOSE_PROFILE       compose profile id
CYCLE_ID              active cycle id
PROJECT_ROOT          absolute project root, resolved by the orchestrator
```

Self-resolved: `$SKILL_ROOT` from workflow install path.

Do **not** paste fact/open contents or DQI in the Task prompt — read from disk (paths below).

## Script Macros

| Macro | Command |
|-------|---------|
| `$INDUCTIVE_G4_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g4_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

## Pipeline

1. Read `$INDUCTIVE_OUT_DIR/inductive-section-pointer.json` → `coverage_order` + each section's `status`. Only `cleared` and `skipped` sections are in scope (Gate 3 close already guarantees no other status remains). Prefer each section's own `status` on maturity `<S>.json` when present.
2. Read `$INDUCTIVE_OUT_DIR/inductive-scope/_index.json` → confirm `last_checkpoint == "shape"`. **Shape baseline = `checkpoint_git_sha` when present**. Use `git show <sha>:…` / `git diff <sha>..HEAD` against that SHA when available. If SHA is null, fall back to HEAD facts only and note the limitation in `facts`. **Do not** treat DQI as SoT.
3. **Read K4 stores:**
   - `$INDUCTIVE_OUT_DIR/_facts.json` — committed substance (`text`, `lens_tags`, optional `origin`)
   - `$INDUCTIVE_OUT_DIR/inductive-opens.json` — note `status=deferred` opens (deferred is not itself a conflict; two lenses resolving the *same* concern / gap differently is)
   - `$INDUCTIVE_OUT_DIR/inductive-scope/<S>.json` — maturity only; **no** `decisions[]`/`deferred[]`
4. Cross-reference all committed facts (grouped by `lens_tags`) against each other and against the Shape-confirm baseline (re-synthesize confirmed spine from checkpoint-era facts vs HEAD):
   - **conflicts** — any two facts (same lens or different) that contradict. For each: `description`, `sections` (all implicated lenses), `owning_section` (set only if one lens is clearly the right home; else leave unset), optional `code_refs` (reused from related opens only).
   - **buildable** — do the committed facts, taken together, add up to something actually buildable?
   - **reversible** — does every fact with an irreversible-looking effect have a documented undo/guard path among related facts/opens? If the text already accepts irreversibility as intended, that is not a defect.
   - **verifiable** — does every settled fact have some stated way to tell it worked?
5. Distill into **one** report: `{conflicts: [...], buildable, reversible, verifiable, facts}`. `facts` (max 8) are short notes on what was cross-checked — not a restatement of fact content.
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
