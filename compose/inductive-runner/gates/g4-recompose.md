> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 4 — Recompose + Audit

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G4` (G3 closed).

**Goal:** audit the already-committed section files for cross-section coherence. This gate prevents the decomposition from losing the whole. It **only finds and names problems — it never fixes them**: it does not discover new EPs, does not run methods, does not write section files, and changes no decision. Every finding is routed back to the gate that owns it (step 3 table).

**Read discipline (context guard):** the **semantic** half of the audit (`conflicts` / `buildable` / `reversible` / `verifiable`) runs in `g4-recompose-runner` subagent only — **do not** inline-read section files, the EP ledger, or the DQI during G4. The **structural** half (`reforms_shape` / `shape_absorbed`) is mechanical and stays a direct script call (step 1) — it needs no subagent.

## Audit spine

1. **Structural check** (script) → `reforms_shape` / `shape_absorbed`.
2. **Semantic audit** (subagent) → gate: fetch its verdict via `g4-check-report` / `g4-list-report`.
3. **Present + route** — name each problem, route it to the gate that owns it; fix there, then re-run from step 1.
4. **Close** — report-driven; no payload the caller can forge.

### Step 1 — Structural check

Call `$INDUCTIVE_G3_SECTION_CTL recompose-check` (structural half — design Turn 61):
- **reforms_shape** — `_index.last_checkpoint == "shape"` (Shape-confirm mark present)
- **shape_absorbed** — every cleared section has `<S>.json` (or legacy `.md`); no blocking∧open

Semantic meaning of "still matches confirmed spine" is assessed in step 2 against the checkpoint baseline (not a frozen `architecture_view` SoT).

Both structural predicates are mechanical — no semantic judgement, so no subagent is needed here.

### Step 2 — Semantic audit (subagent)

Dispatch `g4-recompose-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/g4-recompose-runner/SKILL.md and follow its instructions.

## Input
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: {actual $PROJECT_ROOT}
```

Do **not** paste section-file contents in the Task prompt — the subagent reads `inductive-scope/<S>.json` (and legacy `.md` if any) from disk. Compare HEAD decisions against the Shape-confirm checkpoint baseline when judging drift.

Then run `$INDUCTIVE_GATE_CTL g4-check-report` **once** — immediately after the subagent returns. **Exit 1 (unresolved conflicts, or `buildable`/`reversible`/`verifiable`=false) is an expected branch — still run `$INDUCTIVE_GATE_CTL g4-list-report` next** to get the findings for step 3. **Ignore** the Task return beyond confirming completion — decide next step only via `$INDUCTIVE_GATE_CTL g4-list-report`. **Do not** read source inline in this step.

### Step 3 — Present + route

Present the recompose self-check — **naming each problem, not fixing it**. Route every finding back to the gate that owns it; Gate 4 registers no EP and changes no decision (the fix is made there through the normal AI-recommends → user-decides loop). After the fix, re-run from step 1 (structural + semantic must both be re-checked — a stale verdict is never reused).

| Finding | Route |
|---|---|
| `shape_absorbed=false`, or a `conflict` with a single `owning_section` | **Section-level.** `$INDUCTIVE_GATE_CTL gate-reopen --gate G3 --sections <S1,S2,...>` — atomically reopens G3, clears the stale semantic report, **and** rewinds every listed section in the same call (no separate `rewind-section` step; a G3 reopen can never be left half-paired) → fix via the `gates/g3-refine.md` step-4 loop (`append-to-section`) → re-`clear-section`. |
| a `conflict` with no `owning_section` (cross-section) | **Cross-section.** User picks **one owning section** to host the reconciliation → `activate-section` it → register the reconciliation as a normal EP there (focus guard applies) → decide it one at a time → re-`append-to-section` + `clear-section` any other affected section to match. |
| `reforms_shape=false` | **Shape-level.** `$INDUCTIVE_GATE_CTL gate-reopen --gate G1` (cascades: clears the stale G2/G4 reports too) → correct the shape with the user via `gates/g1-shape.md` → re-descend the spine. |
| `buildable=false` / `reversible=false` / `verifiable=false` | Same as a cross-section or section-level conflict, whichever the subagent's `facts` implicate; if the whole design is unsound, treat as shape-level. |

`gate-reopen --sections` is the only path back into Gate 3 for the section-level row above — it is atomic (gate status + affected sections move together in one call), so the spine can never be left half-paired (gate reopened, section still `cleared`, or vice versa). Committed `<S>.md` files and the EP ledger survive a reopen — only gate status, the rewound sections' `cleared` marker, and the now-stale g4 report reset.

### Step 4 — Close

**Close criterion:** call `$INDUCTIVE_GATE_CTL gate-close --gate G4` (no payload — **report-driven**, mirroring G2). Internally it re-runs `recompose-check` and reads `g4-recompose-report.json`, merges both, and rejects the close if any of `reforms_shape` / `shape_absorbed` / `conflicts==[]` / `buildable` / `reversible` / `verifiable` fails — a caller-supplied payload can never substitute for the actual report. On success it writes the merged predicates to `$INDUCTIVE_DQI.recompose_check` and advances to Gate 5. Call this only after the user confirms the integrated solution is coherent.

On G4 close, proceed to Gate 5 (`gates/g5-provenance.md`) before returning to the parent.
