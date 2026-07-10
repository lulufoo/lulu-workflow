---
name: inductive-runner
description: >-
  Pre-compose inductive investigation for compose stages. Seeds per-section
  JSON SoT from the upstream scope doc, confirms a shape view, then refines via
  a user-driven capability surface (view / probe / detect / settle). Hands
  mechanical fidelity projections to compose Initializing.
---

# inductive-runner

Run this sub-skill only when dispatched from a compose stage `start` (inductive path) — e.g. `lulu-design`.

**Design SSOT:** `docs/biz/inductive-scope-section-sot-design.md` (+ theory). Implementation plan: `docs/superpowers/plans/2026-07-10-inductive-scope-section-sot.md`.

Produces **per-section JSON** under `inductive-scope/` (`<SECTION>.json` + `_index.json`) under the active revision dir. Compose Initializing reads a **mechanical fidelity projection** of `decisions[].text` (same as `view --synthesis off`). After completion, control returns to the parent compose stage for Initializing.

This runner is **stage-agnostic**: `coverage_sections`, section weights, and discovery `methods` are profile data fetched as `inductive-scan-criteria`.

---

## Dispatch Inputs (from parent compose stage)

The parent passes these in the `## Input` block; do not hardcode stage paths.

| Var | Meaning |
|-----|---------|
| `$COMPOSE_PROFILE` | Compose profile id (drives every `$FETCH_COMPOSE`) |
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_DOC` | Upstream scope path (Seed source; Audit cross-check — e.g. `decision-doc.md`) |
| `$INTENT_BASELINE_REFS` | JSON array of intent baseline refs; generative via `intent_coverage` **and** G5 algorithm-A safety-net; empty → both no-op |
| `$NORM_CONSTRAINT_REFS` | JSON array of norm constraint refs; generation boundary **and** G5 algorithm-C; empty → both no-op |
| `$INDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) for inductive state bundle |

## Session Paths (derived)

```
INDUCTIVE_DIR         = $INDUCTIVE_OUT_DIR/inductive-scope          # <SECTION>.json + _index.json (SoT)
INDUCTIVE_DQI         = $INDUCTIVE_OUT_DIR/inductive-dqi.json       # optional resume aid; not SoT
INDUCTIVE_GATE_STATE  = $INDUCTIVE_OUT_DIR/inductive-gate-state.json
INDUCTIVE_SECTION_PTR = $INDUCTIVE_OUT_DIR/inductive-section-pointer.json
INDUCTIVE_GROUNDING   = $INDUCTIVE_OUT_DIR/grounding-notes.json     # optional receipts
INDUCTIVE_G4_REPORT   = $INDUCTIVE_OUT_DIR/g4-recompose-report.json
PROVENANCE_GATE_STATE = $INDUCTIVE_OUT_DIR/provenance-gate-state.json
PROVENANCE_TRACES     = $INDUCTIVE_OUT_DIR/provenance-trace-{intent,scope,norm}.json
```

> **Removed as SoT:** `exposed-points.json` (opens live in `<S>.json` `open[]`), frozen `architecture_view` as truth (shape is a view; baseline = `checkpoint --name shape`).

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$INDUCTIVE_G3_SECTION_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g3_section_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$PROVENANCE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/provenance_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Fetch schedule:
- **At Shape-confirm / G1 start:** `$FETCH_COMPOSE --role inductive-scan-criteria` → `SCAN_CRITERIA`
- **Before detect / refine:** `$FETCH_COMPOSE --role section-form-registry`; `$FETCH_COMPOSE --role section-kw-criteria` → `KW_CRITERIA` (altitude register)

**Primary CRUD (section-SoT):** `seed-decision`, `add-open`, `settle-open`, `defer-open`, `update-decision`, `attach-code-refs`, `get-section`, `view --synthesis off|on`, `checkpoint --name shape`, `set-frontier`, `clear-section`. See `$INDUCTIVE_G3_SECTION_CTL --help`.

---

## Method (capability surface)

Inductive work discovers missing design decisions (parts → whole). **SoT = per-section JSON.** Views and collision are read-only observations; mutations land only via section commands (I1/I12).

**Control model (user-driven — design §7):**

1. **Seed** — `seed-decision` from `$SCOPE_DOC` into mapped sections (`trigger=seed`, `means=scope`).
2. **Shape-confirm** — `view --synthesis on --granularity 架构大局` → user confirms/corrects → corrections via section commands → `$INDUCTIVE_G3_SECTION_CTL checkpoint --name shape` → `gate-close G1` (legacy payload still accepted for resume) → **stop and await user**.
3. **G2** — folded: `gate-close G2` auto-passes without topology report (see `gates/g2-grounding.md`). Topology grounding happens per-open via `attach-code-refs`.
4. **Capabilities (user triggers; do not auto-sweep):**
   - ① **view** — fidelity projection (`synthesis off` = compose init input; `on` = AI-shaped bundle)
   - ② **碰撞 (human/probe)** — questioning observation; gaps → `add-open --trigger human --means probe`
   - ③ **detect** — on demand: `ai_scan` / `intent_baseline` / `ai/probe` (4 lenses at `frontier_kw`) → `add-open --trigger ai --means …`
   - ④ **process batch** — auto/manual: `attach-code-refs` → `settle-open` / `defer-open`
   - ⑤ **user-proposed** — `add-open --trigger human --means direct` → immediately ④
5. **Exit** — coverage sections cleared/skipped ∧ no blocking∧open ∧ (manifest demands fulfilled∨deferred if present)
6. **Audit (user-triggered close):** G4 internal (hard) · G5 external (soft) → Handoff

**Discovery skeleton (Expose):** section + `frontier_kw` ruler; methods measure; evidence differs (code / demand / methodology). `trigger=human` exempt from altitude filter; `trigger=ai` applies it. `ai/probe` MVP lenses: failure / boundary / assumption / seam (design §6.1).

**Collaboration:** AI leads cognition + spine; user leads decision and progress. Scripts never judge content semantics.

---

## Pipeline

**Seed + Shape-confirm (G1) → G2 (auto/folded) → Refine capabilities (G3) → Audit G4 → Audit G5**

### Gate routing

<HARD-GATE>
Before executing any gate, read the corresponding gate file first. Every gate file's first step is `$INDUCTIVE_GATE_CTL resolve-context` (Gate 5: `$PROVENANCE_GATE_CTL resolve-context`).
On a `gate-reopen`, load the target gate's file next.
Do NOT rely on memory for gate execution steps.
</HARD-GATE>

| Gate | File | Load condition |
|------|------|-----------------|
| G1 — Shape-confirm | `gates/g1-shape.md` | Session start or `active_gate=G1` |
| G2 — Folded grounding | `gates/g2-grounding.md` | G1 closed — usually auto-close |
| G3 — Refine (capabilities) | `gates/g3-refine.md` | G2 closed |
| G4 — Internal audit | `gates/g4-recompose.md` | User ready; G3 exit met |
| G5 — External audit | `gates/g5-provenance.md` | G4 closed |

---

## Roles & Global Rules

- **Collaboration baseline:** AI leads cognition and the spine; user leads decision and progress. Output = finding + leaning — never a verdict menu.
- **Who fixes what:** User decides how to fix; AI recommends; scripts move state only. G4 finds/names — never patches.
- **Focus guard:** Discovery may scan cross-section (read-only). Mutations (`seed-decision`, `add-open`, `settle-open`, `set-frontier`, `clear-section`, …) require `activate-section` first.
- **Human inlet:** `add-open --trigger human --means probe|direct|view` — any altitude; AI maps owning section.
- **AI detect:** never automatic; user asks. Sources: `ai_scan`, `intent_baseline`, `probe` (black-box lenses).
- **Session state:** each turn start with `$INDUCTIVE_GATE_CTL resolve-context`.

---

## Output Contract

**SoT:** `inductive-scope/<SECTION>.json` with `decisions[]` / `open[]` / `deferred[]` + `_index.json` (`last_checkpoint`).

**Compose init input:** `$INDUCTIVE_G3_SECTION_CTL view --synthesis off --scope <S|all>` (mechanical `decisions[].text` assembly) — same bytes the resolver may materialize for Initializing.

**DQI** remains a resume/audit aid written by gate-control; it is **not** the decision SoT.

---

## Constraints

- Single SoT = section JSON; views non-authoritative (V1–V5).
- No AI hand-written JSON (I12) — only section-control commands.
- G2 not an independent discovery gate; ground via `attach-code-refs`.
- G4 structural: shape checkpoint + cleared files + no blocking opens; semantic half in `g4-recompose-runner`.
- Clean cutover: no migration of legacy `.md` / EP ledger as SoT.
