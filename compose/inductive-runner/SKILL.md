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
INDUCTIVE_SECTION_PTR = $INDUCTIVE_OUT_DIR/inductive-section-pointer.json  # routing aid; status also on section JSON
INDUCTIVE_GROUNDING   = $INDUCTIVE_OUT_DIR/grounding-notes.json     # optional receipts
INDUCTIVE_G4_REPORT   = $INDUCTIVE_OUT_DIR/g4-recompose-report.json
PROVENANCE_GATE_STATE = $INDUCTIVE_OUT_DIR/provenance-gate-state.json
PROVENANCE_TRACES     = $INDUCTIVE_OUT_DIR/provenance-trace-{intent,scope,norm}.json
```

> **Not SoT:** `exposed-points.json`, frozen `architecture_view` / `shape_constraints` as truth. Opens live in `<S>.json` `open[]`. Shape baseline for G4 = `checkpoint --name shape` (`_index.last_checkpoint` + `checkpoint_git_sha`), not a frozen view file.

---

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$INDUCTIVE_G3_SECTION_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g3_section_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$PROVENANCE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/provenance_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Fetch schedule:
- **Before Seed / Shape-confirm:** `$FETCH_COMPOSE --role inductive-scan-criteria` → `SCAN_CRITERIA`; `$FETCH_COMPOSE --role section-registry` (map scope statements → sections)
- **Before detect / refine:** `$FETCH_COMPOSE --role section-form-registry`; `$FETCH_COMPOSE --role section-kw-criteria` → `KW_CRITERIA`

**Primary CRUD (section-SoT):** `seed-decision`, `add-open`, `update-open`, `settle-open`, `defer-open`, `update-decision`, `attach-code-refs`, `get-section`, `view --synthesis off|on`, `checkpoint --name shape`, `set-frontier`, `activate-section`, `clear-section`, `skip-section`, `rewind-section`, `check-coverage`. See `$INDUCTIVE_G3_SECTION_CTL --help`.

**Removed (fail-fast if called):** `register-ep`, `update-ep`, `append-to-section` — use the section-SoT commands above.

---

## Method (capability surface)

Inductive work discovers missing design decisions (parts → whole). **SoT = per-section JSON.** Mutations land only via section commands (I1/I12). Progress is Exit-predicate driven, not sweep-count driven.

### Control spine

1. **Seed** — For each mapped section: `activate-section` → `seed-decision` (`trigger=seed`, `means=scope`, `confidence=direct`) → AI re-judges KW → `set-frontier`. Registry maps structural → ST, boundary → SC, goals → GO, invariants → I, etc. **I4:** never invent beyond scope. Git commit `"seeded"`.
2. **Shape-confirm (I11)** — After Seed: `view --synthesis on --granularity <arch-overview hint>` → user confirms/corrects → corrections via section commands (+ `set-frontier` when decisions change) → re-view until confirmed → `gate-close G1` (records `checkpoint --name shape`) → **stop and await user**. Do **not** auto-detect.
3. **G2 folded** — `gate-close G2` auto-passes without topology report. Per-open grounding = `attach-code-refs` inside capability ④.
4. **User-driven capabilities** (below) until Exit.
5. **Exit** — run `check-coverage`: ∀ coverage section cleared∨skipped ∧ no (blocking∧open) ∧ (if demand manifest: all fulfilled∨deferred).
6. **Audit (user-triggered):** G4 internal hard · G5 external soft → Handoff (`view --synthesis off` / Initializing).

### Global observation (anytime after Seed — **not** Gate-3-only; I13)

| # | Capability | Contract | Lands via |
|---|------------|----------|-----------|
| ① | **view** | Fidelity projection. **V1** source=section SoT only · **V2** no invent / gaps stay gaps · **V3** shape free · **V4** non-authoritative · **V5** `synthesis:off` = compose-init mechanical assembly. **No inference** when presenting as View. | Corrections → section commands |
| ② | **碰撞 (human/probe)** | Questioning observation. AI may infer but **must** label ✅ Verified (anchor) / ⚠️ Inferred / say unknown. Multi-readings OK; **never** decide for the user. | Gaps → `add-open --trigger human --means probe` → ④ |

Do **not** mix ① and ②: stuffing inference into a View violates V2.

### Advance actions (mutate SoT)

| # | Capability | Notes |
|---|------------|-------|
| ③ | **detect** [sections] | User asks only. Subtract **Settled** (`decisions[]`) first (**I5**). Run `ai_scan` / `intent_baseline` / `ai/probe` (4 lenses at `frontier_kw`) → `add-open --trigger ai --means …`. Present batch (problem+leaning). |
| ④ | **process batch** | Informed choice after seeing problem+leaning: **auto** (authorized continuous settle) / **manual** (pause per point) / **ignore** (`defer-open`). Path: `attach-code-refs` → `settle-open` / `defer-open`. One git commit per settle/defer (**I8**). Then ①/② to confirm. |
| ⑤ | **user-proposed** | `add-open --trigger human --means direct` (or `means=view` if found while viewing) → **immediately** ④. |

**② vs ③ vs ⑤:** ② = ad-hoc dialogue questions; ③ = systematic section batch; ⑤ = user already asserts a gap (often after ②).

**Discovery skeleton:** section + `frontier_kw` ruler; methods measure; evidence differs (code / demand / methodology). `trigger=human` altitude-exempt; `trigger=ai` applies `frontier_kw`. Provenance vocabulary: `trigger ∈ {human,ai,seed}` × `means ∈ {probe,direct,view,ai_scan,intent_baseline,scope}` (`seed`/`scope` Seed-only).

**`ai/probe` MVP lenses:** failure / boundary / assumption / seam — silence ∧ KW-false → gap; no correctness judging (G4). Dedup identity = (section, KW row, topic); collide → attach provenance via `update-open`, do not duplicate.

**`frontier_kw`:** re-judge via `set-frontier` only when that section's `decisions` change (`seed-decision` / `settle-open` / `update-decision`). No global refresh.

**Lazy consistency (I8):** after `update-decision` on id=X, single-hop re-read opens with `hangs_under==X` (+ citing sections); conflict → `add-open`. No cascade engine.

**Collaboration:** AI leads cognition + spine; user leads decision and progress. Scripts never judge content semantics. Output = finding + leaning — never a verdict menu.

---

## Pipeline

**Capability surface is primary.** Gates are checkpoints / audits around it:

**Seed + Shape-confirm (G1) → G2 (auto/folded) → Refine (G3 hosts ③④⑤; ①② global) → Audit G4 → Audit G5**

### Gate routing

<HARD-GATE>
Before executing any gate, read the corresponding gate file first.
Do NOT rely on memory for gate execution steps.
</HARD-GATE>

| Gate | File | Load condition |
|------|------|-----------------|
| G1 — Shape-confirm | `gates/g1-shape.md` | Session start or `active_gate=G1` |
| G2 — Folded grounding | `gates/g2-grounding.md` | G1 closed — usually auto-close |
| G3 — Refine (③④⑤) | `gates/g3-refine.md` | G2 closed |
| G4 — Internal audit (hard) | `gates/g4-recompose.md` | User ready; G3 exit met |
| G5 — External audit (soft) | `gates/g5-provenance.md` | G4 closed |

---

## Roles & Global Rules

- **Who fixes what:** User decides how to fix; AI recommends; scripts move state only. G4/G5 find/name — never patch.
- **Focus guard:** Discovery may scan cross-section (read-only). Mutations require `activate-section` first.
- **Human inlet:** `add-open --trigger human --means probe|direct|view` — any altitude; AI maps owning section.
- **AI detect:** never automatic; user asks.
- **intent_coverage:** when a demand manifest exists, mount-or-create opens with `intent_ref` before inventing duplicates.

---

## Output Contract

**SoT:** `inductive-scope/<SECTION>.json` — minimum fields:

- `decisions[]`: `id`, `kw`, `text`, `trigger`, `means`, `intent_ref`, `confidence`, optional `rationale` / `code_refs`
- `open[]`: `id`, `kw`, `trigger`, `means`, `blocking`, `problem`, `leaning`, `confidence`, optional `intent_ref` / `hangs_under` / `code_refs`
- `deferred[]`: deferred opens (+ optional `intent_ref` / `note`)
- `_index.json`: `cycle_id`, `scope_ref`, `last_checkpoint`

**Compose init input:** `$INDUCTIVE_G3_SECTION_CTL view --synthesis off --scope <S|all>` — mechanical `decisions[].text` assembly (I2/V5).

**DQI** = optional resume/audit aid from gate-control; **not** decision SoT.

---

## Constraints

- Single SoT = section JSON (I1). Views non-authoritative (I3 / V1–V5). I13: View ≠ 碰撞.
- No AI hand-written JSON (I12) — section-control commands only.
- I5: subtract Settled before detect. I6: informed batch auto/manual/ignore. I7: coarse views stay coarse (no file:line in arch overview).
- G2 not an independent discovery gate; ground via `attach-code-refs`.
- G4 hard / G5 soft; both user-triggered at delivery time.
- Clean cutover: no legacy `.md` / EP ledger as SoT.
