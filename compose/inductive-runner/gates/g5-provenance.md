> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 5 — External audit (soft)

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` / `$PROVENANCE_GATE_CTL resolve-context` reports `active_gate` is `G5` (G4 closed).

**Goal:** on the G4-coherent **facts + opens**, **name every deviation** of this stage's output from its upstream references, and drop them into three trace files (external provenance audit). Like Gate 4, Gate 5 **only finds and names — it never fixes a decision and never collects sign-off.** All deltas are written `pending-signoff`; sign-off and delivery blocking are a later phase. **Soft:** does not hard-block gate-close.

**Read discipline (context guard):** runs in `g5-provenance-runner` subagent only — **do not** inline-read `_facts.json`, opens, `$SCOPE_REF`, or upstream refs during G5.

1. Call `$PROVENANCE_GATE_CTL init-session --cycle-id "$CYCLE_ID" --stage "$COMPOSE_PROFILE"` (once, on entry after G4) — seeds gate state + three empty traces. Resume: `$PROVENANCE_GATE_CTL resolve-context`.
2. **Provenance scan (subagent):** dispatch `g5-provenance-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/g5-provenance-runner/SKILL.md and follow its instructions.

## Input
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
SCOPE_REF: {actual $SCOPE_REF}
INTENT_BASELINE_REFS: {actual $INTENT_BASELINE_REFS}
NORM_CONSTRAINT_REFS: {actual $NORM_CONSTRAINT_REFS}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
PROJECT_ROOT: {actual $PROJECT_ROOT}
```

Do **not** paste fact/open or upstream-ref contents in the Task prompt — the subagent reads `_facts.json` / `inductive-opens.json` (and `$SCOPE_REF` / refs) from disk. **Ignore** the Task return beyond confirming completion — read the actual deltas only via `$PROVENANCE_GATE_CTL present` next.

Role/algorithm/file mapping, axis semantics, and bucket vocabulary are the subagent's own SSOT (its Pipeline + [`../../references/provenance-algorithm-semantics.md`](../../references/provenance-algorithm-semantics.md) + `provenance_trace_schema.py`) — not repeated here.

3. Call `$PROVENANCE_GATE_CTL present` (read-only) and show the user the full delta list — a receipt, **not** a sign-off.

**Close criterion:** call `$PROVENANCE_GATE_CTL gate-close` — it re-presents the full delta list (read-only receipt) and marks G5 closed. A clean stage simply closes with zero deltas.

## Return

```
inductive-runner complete.
maturity + opens + facts → <INDUCTIVE_OUT_DIR>/ (maturity under inductive-scope/; opens; _facts.json)
inductive-dqi.json → <path> (resume aid only; not SoT)
provenance deltas → intent <A> / scope <B> / norm <C> (all pending-signoff)
Deferred opens: <N> (from inductive-opens.json status=deferred; will appear in design-doc OQ)
Returning to parent compose stage for compose Initializing.
```
Control returns to the parent compose stage.
