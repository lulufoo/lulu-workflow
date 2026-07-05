---
name: g4-recompose-runner
description: >-
  Read-only subagent for inductive Gate 4 semantic recompose audit. One
  invocation covers the whole committed section set: cross-references every
  cleared/skipped section's committed figure against the Gate 1 shape and
  against each other, writes one distilled g4-recompose-report.json verdict
  to disk. Does not fix anything, register EPs, or interact with the user.
---

# g4-recompose-runner

Terminal runner subagent. Dispatched from **inline** inductive-runner at Gate 4 step 2 (one subagent per G4 pass — after the mechanical structural check in step 1).

**Scope:** This SKILL registers **`$INDUCTIVE_G4_CTL` only** (write report). It does **not** register `$INDUCTIVE_GATE_CTL` or `$INDUCTIVE_G3_SECTION_CTL`. Check/list, gate-close/reopen, and any section mutation (`rewind-section`, `append-to-section`, `clear-section`) are **parent** (`inductive-runner`) steps — not subagent commands.

## Shared report contract

Report field contract, thinness limits, and validation live in `g4_recompose_report_schema.py` (read-only reference — write only via `$INDUCTIVE_G4_CTL record-recompose-report`). This report holds only the four **semantic** predicates (`conflicts` / `buildable` / `reversible` / `verifiable`) — the two **structural** predicates (`reforms_shape` / `shape_absorbed`) are mechanical and already produced by the parent's own Gate 4 step 1 (`recompose-check`); this subagent does not re-derive them.

**Hard boundaries (never violate):**
- Read-only — no EP registration, no section mutation, no gate-close, no fix of any kind. Gate 4 **only finds and names problems**.
- Whole-set audit, not per-section — cross-reference *all* committed sections against each other and against the shape in one pass; never partial.
- A `conflict` must name either a single `owning_section` (the section best positioned to host the fix) or leave it unset with all implicated `sections` listed (a true cross-section conflict with no single owner) — never guess an owner for a conflict that genuinely spans sections.
- No line-level detail required — this is a coherence judgement over already-committed decisions, not a fresh code scan; only cite `code_refs` already present in the section files, never re-derive new ones from source.

## Required Inputs

Plain-text block from the orchestrating inductive-runner:

```
INDUCTIVE_OUT_DIR     absolute path to revision{N}/ inductive state bundle
COMPOSE_PROFILE       compose profile id
CYCLE_ID              active cycle id
PROJECT_ROOT          project root (usually $(pwd))
```

Self-resolved: `$SKILL_ROOT` from workflow install path.

Do **not** paste section-file contents, the EP ledger, or the DQI in the Task prompt — read them from disk (paths below).

## Script Macros

| Macro | Command |
|-------|---------|
| `$INDUCTIVE_G4_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g4_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

## Pipeline

1. Read `$INDUCTIVE_OUT_DIR/inductive-section-pointer.json` → `coverage_order` + each section's `status`. Only `cleared` and `skipped` sections are in scope (Gate 3 close already guarantees no other status remains).
2. Read `$INDUCTIVE_OUT_DIR/inductive-dqi.json` → `architecture_view` + `shape_constraints` (the confirmed Gate 1 shape — the reference frame every committed decision must still cohere with).
3. Read `$INDUCTIVE_OUT_DIR/exposed-points.json` → resolved/deferred EPs (context for why each decision was made; a `deferred` EP is not itself a conflict, but two sections resolving the *same* EP differently is).
4. For each `cleared` section, read its `$INDUCTIVE_OUT_DIR/inductive-scope/<S>.md` (the committed figure + resolved decisions, already built — never re-derive from primary source).
5. Cross-reference all committed section files against each other and against `shape_constraints`:
   - **conflicts** — any two decisions (same section or different sections) that contradict. For each: `description`, `sections` (all implicated), `owning_section` (set only if one section is clearly the right home for the fix; else leave unset), optional `code_refs` (reused from the section files only).
   - **buildable** — do the committed decisions, taken together, add up to something actually buildable (no missing linking decision, no mutually-impossible combination)?
   - **reversible** — does every decision with an irreversible-looking effect have a documented undo/guard path in its section file? If a section's own text already accepts the irreversibility as intended, that is not a defect.
   - **verifiable** — does every resolved decision have some stated way to tell it worked (a test, an observable signal, a checkable artifact) in its section file?
6. Distill into **one** report: `{conflicts: [...], buildable, reversible, verifiable, facts}`. `facts` (max 8) are short notes on what was cross-checked and why the verdict landed where it did — not a restatement of section content.
7. `$INDUCTIVE_G4_CTL record-recompose-report --json '<report object>'`.
8. Return the compact template below — **stop**. Do not run any further control commands.

**Forbidden after step 7 (never violate):**
- Any `check-recompose-report` or `list-recompose-report` — **subagent never**; parent runs `$INDUCTIVE_GATE_CTL g4-check-report` / `g4-list-report` after you return (see `inductive-runner` Gate 4 step 2).
- `$INDUCTIVE_GATE_CTL` or `$INDUCTIVE_G3_SECTION_CTL` — subagent does not register or call either parent macro.
- Proposing or applying a fix, registering an EP, or mutating any section — name the problem only.
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
