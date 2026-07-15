> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 4 — Internal audit (hard)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G4` (G3 closed). User asked for delivery audit.

**Goal:** audit already-committed **facts + opens + maturity** for **internal coherence**. Gate 4 **only finds and names problems — it never fixes them**: it does not discover new opens, does not run detect methods, does not write section/fact files, and changes no decision. Every finding is routed back to the gate that owns it (step 3 table).

**Read discipline (context guard):** the **semantic** half (`conflicts` / `buildable` / `reversible` / `verifiable`) runs in `g4-recompose-runner` only — **do not** inline-read `_facts.json` / opens / DQI during G4. The **structural** half (`reforms_shape` / `shape_absorbed` / facts-without-maturity) is mechanical via script (step 1).

**Shape baseline (Turn 61):** `checkpoint("shape")` Git / `_index.last_checkpoint` — **not** a frozen `architecture_view` SoT. Semantic drift checks synthesize the confirmed spine from that checkpoint vs HEAD `_facts.json`.

## Audit spine

1. **Structural check** (script) → `reforms_shape` / `shape_absorbed` (+ facts-without-maturity).
2. **Semantic audit** (subagent) → gate: fetch its verdict via `g4-check-report` / `g4-list-report`.
3. **Present + route** — name each problem, route it; fix there, then re-run from step 1.
4. **Close** — report-driven; no payload the caller can forge.

### Step 1 — Structural check

Call `$INDUCTIVE_G3_SECTION_CTL recompose-check` (structural half):
- **reforms_shape** — `_index.last_checkpoint == "shape"` (Shape-confirm mark present)
- **shape_absorbed** — every cleared section has maturity `<S>.json`; no blocking∧open; no fact lens left on `untouched` maturity

Both structural predicates are mechanical — no semantic judgement here.

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

Do **not** paste fact/open contents in the Task prompt — the subagent reads `_facts.json` / `inductive-opens.json` / maturity from disk. Compare HEAD facts against the Shape-confirm checkpoint baseline when judging drift.

Then run `$INDUCTIVE_GATE_CTL g4-check-report` **once** — immediately after the subagent returns. **Exit 1 (unresolved conflicts, or `buildable`/`reversible`/`verifiable`=false) is an expected branch — still run `$INDUCTIVE_GATE_CTL g4-list-report` next** to get the findings for step 3. **Ignore** the Task return beyond confirming completion — decide next step only via `$INDUCTIVE_GATE_CTL g4-list-report`. **Do not** read source inline in this step.

### Step 3 — Present + route

Present the recompose self-check — **naming each problem, not fixing it**. Route every finding; Gate 4 registers no open and changes no decision (fix via normal AI-recommends → user-decides). After the fix, re-run from step 1 (structural + semantic must both be re-checked — a stale verdict is never reused).

| Finding | Route |
|---|---|
| `shape_absorbed=false`, or a `conflict` with a single `owning_section` | **Section-level.** `$INDUCTIVE_GATE_CTL gate-reopen --gate G3 --sections <S1,S2,...>` — atomically reopens G3, clears the stale semantic report, **and** rewinds every listed section → fix via `gates/g3-refine.md` (`update-decision` / `settle-open` / `add-open` + `attach-code-refs` as needed) → re-`clear-section`. |
| a `conflict` with no `owning_section` (cross-section) | **Cross-section.** User picks **one owning section** → `activate-section` → `add-open` (reconciliation) → Class 2 processing (`settle-open` / `update-decision`) → re-`clear-section` any other affected section to match. |
| `reforms_shape=false` | **Shape-level.** `$INDUCTIVE_GATE_CTL gate-reopen --gate G1` (cascades: clears stale G2/G4 reports) → correct via `gates/g1-shape.md` (commands + re-`view` + re-`checkpoint --name shape`) → re-descend. |
| `buildable=false` / `reversible=false` / `verifiable=false` | Same as cross-section or section-level, whichever the subagent's `facts` implicate; if the whole design is unsound, treat as shape-level. |

`gate-reopen --sections` is the only path back into Gate 3 for the section-level row — atomic (gate status + affected sections move together). Maturity `<S>.json` / `_facts.json` / opens survive a reopen — only gate status, rewound sections' `cleared` marker, and the stale g4 report reset.

### Step 4 — Close

**Close criterion:** call `$INDUCTIVE_GATE_CTL gate-close --gate G4` (no payload — **report-driven**). Internally it re-runs `recompose-check` and reads `g4-recompose-report.json`, merges both, and rejects the close if any of `reforms_shape` / `shape_absorbed` / `conflicts==[]` / `buildable` / `reversible` / `verifiable` fails — a caller-supplied payload can never substitute for the actual report. On success it writes the merged predicates to `$INDUCTIVE_DQI.recompose_check` and advances to Gate 5. Call this only after the user confirms the integrated solution is coherent.

On G4 close, proceed to Gate 5 (`gates/g5-provenance.md`) before returning to the parent.
