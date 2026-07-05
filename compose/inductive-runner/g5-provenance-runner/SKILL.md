---
name: g5-provenance-runner
description: >-
  Read-only subagent for inductive Gate 5 provenance detection. Runs
  algorithms A/B/C (intent-baseline / scope / norm-constraint) over the
  already-committed section files, records named deltas to the three
  provenance trace files. Does not interact with the user, never fixes a
  decision, never collects sign-off.
---

# g5-provenance-runner

Terminal runner subagent. Dispatched from **inline** inductive-runner at Gate 5 (one subagent per G5 pass, after G4 closes).

**Scope:** This SKILL registers **`$PROVENANCE_GATE_CTL` `record-delta` only**. It does not call `init-session`, `present`, or `gate-close` — those are **parent** (`inductive-runner`) steps, run before dispatch and after you return. It does not register `$INDUCTIVE_GATE_CTL` or `$INDUCTIVE_G3_SECTION_CTL`.

## Shared trace contract

Delta field contract, bucket vocabulary per (role, axis), and axis-1/axis-2 shape rules live in `provenance_trace_schema.py` (read-only reference — write only via `$PROVENANCE_GATE_CTL record-delta`). Algorithm semantics (why each bucket exists, default-deny vs silence-is-ok per role) live in `docs/biz/compose-provenance-mechanism.md` §2 — read there, do not re-derive.

**Hard boundaries (never violate):**
- Read-only over already-committed artifacts — no EP registration, no section mutation, no gate-close.
- **Find and name only** — never fixes, edits, or re-opens a decision. Every delta the schema forces to `pending-signoff`; routing a finding back to its owning gate is the parent's/user's job, not yours.
- Axis 1 is a **per-section** scan (`--section` required); axis 2 is a **whole-document, once** pass (`--section` omitted) — run axis 2 only after all sections are scanned.
- `norm-constraint` role has **no axis 2** — skip it for that role regardless.
- Empty `$INTENT_BASELINE_REFS` → skip algorithm A entirely; empty `$NORM_CONSTRAINT_REFS` → skip algorithm C entirely.

## Required Inputs

Plain-text block from the orchestrating inductive-runner:

```
INDUCTIVE_OUT_DIR       absolute path to revision{N}/ inductive state bundle
SCOPE_DOC               absolute path to the upstream scope doc (派生父级 SSOT, algorithm B)
INTENT_BASELINE_REFS    JSON array of {type,path} refs (意图基准, algorithm A); [] to skip A
NORM_CONSTRAINT_REFS    JSON array of {type,path} refs (规范约束, algorithm C); [] to skip C
COMPOSE_PROFILE         compose profile id
CYCLE_ID                active cycle id
PROJECT_ROOT            absolute project root, resolved by the orchestrator
```

Self-resolved: `$SKILL_ROOT` from workflow install path.

Do **not** paste section-file contents or upstream doc contents in the Task prompt — read them from disk.

## Script Macros

| Macro | Command |
|-------|---------|
| `$PROVENANCE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/provenance_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

## Pipeline

1. Read every `$INDUCTIVE_OUT_DIR/inductive-scope/*.md` (committed section figures + resolved decisions + `code_refs`) and `$INDUCTIVE_OUT_DIR/inductive-dqi.json` (`architecture_view` for the shape-level frame).
2. Read `$SCOPE_DOC` in full — algorithm B's upstream.
3. If `$INTENT_BASELINE_REFS` is non-empty, read each ref's file — algorithm A's upstream; else skip algorithm A.
4. If `$NORM_CONSTRAINT_REFS` is non-empty, read each ref's file — algorithm C's upstream; else skip algorithm C.
5. **Axis 1 (per section, overreach/conflict) — for each committed section, for each active algorithm:**
   - **A (intent-baseline):** a product-visible decision not honored (within expression) by a same-topic intent item → `扩充意图` (same topic, exceeds expression) | `新增意图` (no same-topic item) | `不一致` (conflicts with an item). Default-deny — an unmatched product-visible addition is flagged, not assumed fine.
   - **B (scope):** a decision directly contradicting an explicit 派生父级 decision → `不一致`. Silence is ok — an untraceable decision is expected (this stage is authorized to elaborate/branch).
   - **C (norm-constraint):** a decision (technical or product) violating a rule → `违反`. Silence is ok.
   - Record each hit immediately: `$PROVENANCE_GATE_CTL record-delta --role <role> --id <unique-id> --axis 1 --bucket <bucket> --section <S> --upstream-anchor <excerpt of the conflicting/violated clause> --description <finding> [--code-refs a.py:1,b.py:2]`.
6. **Axis 2 (whole-document, once, after all sections scanned):**
   - Enumerate every 意图基准 item; any not fulfilled anywhere downstream → `record-delta --role intent-baseline --axis 2 --bucket 未履行意图 --upstream-anchor <item> --description <finding>` (omit `--section`).
   - Enumerate every 派生父级 explicit decision; any not carried forward / elaborated / explicitly deferred → `record-delta --role scope --axis 2 --bucket 遗漏明确决策 --upstream-anchor <decision> --description <finding>` (omit `--section`).
   - `norm-constraint` has no axis 2 — do not call `record-delta` for it here.
7. Return the compact template below — **stop**. Do not run `present` or `gate-close`.

**Forbidden after step 7 (never violate):**
- Any `present` or `gate-close` — **subagent never**; parent runs `$PROVENANCE_GATE_CTL present` then `gate-close` after you return.
- `$INDUCTIVE_GATE_CTL` / `$INDUCTIVE_G3_SECTION_CTL` — subagent does not register or call any other gate macro.
- Fixing, editing, or re-opening a decision, or collecting sign-off — out of scope for this gate entirely.
- Re-stating delta text in the Task return — deltas live in the three trace files; parent reads them via `$PROVENANCE_GATE_CTL present` only.

## Return

Return **exactly** this shape (substitute values only; no extra lines, headings, or markdown):

```
g5-provenance complete.
intent-baseline: <ran|skipped> — <N> deltas
scope: <N> deltas
norm-constraint: <ran|skipped> — <N> deltas
written: provenance-trace-{intent,scope,norm}.json
```

Stop after the Return template. **Do not** run present or gate-close commands — the orchestrating inductive-runner continues Gate 5 with `$PROVENANCE_GATE_CTL present`, then `$PROVENANCE_GATE_CTL gate-close`.
