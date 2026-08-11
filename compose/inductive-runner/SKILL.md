---
name: inductive-runner
description: >-
  Pre-compose inductive investigation for compose stages. Dispatches shared
  fact-intake into _facts.json, tracks opens in inductive-opens.json and per-lens
  maturity under inductive-scope/, confirms a shape view, then refines via a
  two-lane dialogue (free discovery / open-processing) over a Class 1/2/3
  capability surface. Hands facts to compose Writing.
---

# inductive-runner

Run this sub-skill only when dispatched from a compose stage `start` (inductive path) — e.g. `lulu-design`.

Produces **three stores** under the active revision dir (`$INDUCTIVE_OUT_DIR`):
- **Facts (engine state):** `_facts.json` — intake-classified seeds + later
  `fact-store-runner` permit `consume` / shape corrections (K4; no K2 projection)
- **Opens:** `inductive-opens.json` — doc-level flat list (`O-n`)
- **Maturity:** `inductive-scope/<SECTION>.json` + `_index.json` — `{key, status, frontier_kw}` only

Compose Writing reads **`_facts.json`** directly (validate-only). After completion, control returns to the parent compose stage for Writing.

This runner is **stage-agnostic**: init/Exit lens set = `section-registry.section_order`; discovery `methods` / weights / shape hints / `mandatory_coverage_prompt` = `inductive-scan-criteria`.

---

## Dispatch Inputs (from parent compose stage)

The parent passes these in the `## Input` block; do not hardcode stage paths.

| Var | Meaning |
|-----|---------|
| `$COMPOSE_PROFILE` | Compose profile id (drives every `$FETCH_COMPOSE`) |
| `$CYCLE_ID` | Active cycle id |
| `$SCOPE_REF` | Session / G5 source-material path (L mirror `source_path`; not scope-package whole) |
| `$SOURCE_PATH` | Fact-intake SoT; same path as `$SCOPE_REF` for inductive |
| `$INTENT_BASELINE_REFS` | JSON array of intent baseline refs; generative via `intent_coverage` **and** G5 algorithm-A safety-net; empty → both no-op |
| `$NORM_CONSTRAINT_REFS` | JSON array of norm constraint refs; generation boundary **and** G5 algorithm-C; empty → both no-op |
| `$INDUCTIVE_OUT_DIR` | Active revision dir (`revision{active_doc}/`) for inductive state bundle |

`$REVISION_DIR` for intake = `$INDUCTIVE_OUT_DIR`. `$PROJECT_ROOT` = `$(pwd)`.

## Session Paths (derived)

```
INDUCTIVE_DIR         = $INDUCTIVE_OUT_DIR/inductive-scope          # maturity <SECTION>.json + _index.json
INDUCTIVE_OPENS       = $INDUCTIVE_OUT_DIR/inductive-opens.json     # doc-level opens (SoT for gaps)
INDUCTIVE_FACTS       = $INDUCTIVE_OUT_DIR/_facts.json              # discovery-written facts (engine state)
INDUCTIVE_DQI         = $INDUCTIVE_OUT_DIR/inductive-dqi.json       # optional resume aid; not SoT
INDUCTIVE_GATE_STATE  = $INDUCTIVE_OUT_DIR/inductive-gate-state.json
INDUCTIVE_SECTION_PTR = $INDUCTIVE_OUT_DIR/inductive-section-pointer.json  # routing aid; status also on section JSON
INDUCTIVE_SECTION_REGISTRY = $INDUCTIVE_OUT_DIR/section-registry.json  # intent + optional facet seeds (materialized for prompts)
INDUCTIVE_KW_CRITERIA = $INDUCTIVE_OUT_DIR/section-kw-criteria.md  # KW altitude rows (fetch for detect)
INDUCTIVE_GROUNDING   = $INDUCTIVE_OUT_DIR/grounding-notes.json     # optional receipts
INDUCTIVE_G4_REPORT   = $INDUCTIVE_OUT_DIR/g4-recompose-report.json
PROVENANCE_GATE_STATE = $INDUCTIVE_OUT_DIR/provenance-gate-state.json
PROVENANCE_TRACES     = $INDUCTIVE_OUT_DIR/provenance-trace-{intent,scope,norm}.json
```

> **Not SoT:** `exposed-points.json`, frozen `architecture_view` / `shape_constraints` as truth. Opens live in `inductive-opens.json` (not `<S>.json`). Shape baseline for G4 = `checkpoint --name shape` (`_index.last_checkpoint` + `checkpoint_git_sha`), not a frozen view file.

---

Also read `../../_subagent.md` for platform dispatch (not Script Macros rows).

## Script Macros

| Macro | Command |
|-------|---------|
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$INDUCTIVE_G3_SECTION_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_g3_section_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$(pwd)" --compose-profile "$COMPOSE_PROFILE" --compose-cycle-id "$CYCLE_ID"` |
| `$PROVENANCE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/provenance_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$TOPIC_CURRENT_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/topic_current_control.py"` |
| `$FACT_STORE_CTL` | `python3 "$SKILL_ROOT/compose/fact-store-runner/scripts/fact_production_control.py"` |

**Declare-use (sibling tools):** `fact-store-runner` · `narrative-arc-runner`.

Fetch schedule:
- **Before Fact Intake / Shape-confirm:** `$FETCH_COMPOSE --role section-registry` → `SECTION_REGISTRY` (`section_order` → `init-session --sections`); `$FETCH_COMPOSE --role inductive-scan-criteria` → `SCAN_CRITERIA` (methods / shape hints / mandatory)
- **Before detect / refine:** `$FETCH_COMPOSE --role section-form-registry`; `$FETCH_COMPOSE --role section-kw-criteria` → `KW_CRITERIA` (altitude rows); materialize section-registry for prompt seeds:
  - `$INDUCTIVE_G3_SECTION_CTL materialize-section-registry --from-fetch`  
    → writes `$INDUCTIVE_SECTION_REGISTRY`; or `materialize-section-registry --source <path>`
  - Observable done: `$INDUCTIVE_SECTION_REGISTRY` exists under `$INDUCTIVE_OUT_DIR`
  - **Facet seeds (Class 1B):** when the active lens has `facets: string[]`, paste that list into the detect prompt as **non-exhaustive reminders** (not a closed question set; list-external opens allowed). Seeds do **not** gate `clear-section` and there is **no** `facet_id` field.

**Primary CRUD (K4 triple store):** `materialize-section-registry`, `seed-decision` (→ facts; shape-correction / local add — **not** intake cover), `add-open` / `update-open` / `defer-open` / `reject-open` (→ opens), `attach-code-refs` (`O-` only), `get-section`, `view --synthesis off|on`, `checkpoint --name shape`, `set-frontier`, `activate-section`, `clear-section`, `skip-section`, `rewind-section`, `check-coverage`. Fact append / patch / delete / open→facts: `$FACT_STORE_CTL propose → ack → consume` (not G3 section control). See `$INDUCTIVE_G3_SECTION_CTL --help`.

**Removed (fail-fast if called):** `register-ep`, `update-ep`, `append-to-section` — use the commands above.

---

## Method

Inductive work discovers missing design decisions (parts → whole). **SoT = facts + opens + maturity.** Mutations land only via section-control commands (I1/I12). Progress is Exit-predicate driven, not sweep-count driven.

### Control spine

1. **Fact Intake** — Load and follow shared intake **inline** (interactive Confirm). Inductive caller: add `--require-seed-origin` on structure validate (fact-intake Step 3 / cut Done).

```text
Load {SKILL_ROOT}/compose/fact-intake-runner/SKILL.md and follow it.

## Input
REVISION_DIR: <$INDUCTIVE_OUT_DIR>
PROJECT_ROOT: <$PROJECT_ROOT>
COMPOSE_PROFILE: <$COMPOSE_PROFILE>
CYCLE_ID: <$CYCLE_ID>
SOURCE_PATH: <$SOURCE_PATH>
```

Do not re-implement cut / eval / disposition / Confirm; do not `seed-decision` to cover-stamp intake substance.

2. **Shape-confirm (I11)** — After intake: session init + maturity bind + `view --synthesis on --granularity <arch-overview hint>` (`gates/g1-shape.md`) → user confirms/corrects → corrections via commands (+ `set-frontier` when lens facts change) → re-view until confirmed → `gate-close --gate G1` (records `checkpoint --name shape`) → **stop and await user**. Do **not** auto-detect.
3. **G2 Topic Loop** — converge design through human-adopted topics; ends with a human-confirmed topic exit. See `gates/g2-topic-loop.md`, `references/topic-model.md`, `references/topic-landscape.md`, and `references/topic-portrait.md`.
4. **G3 gap-check** — leak scan (orphans / blocking opens); conclusion→facts and open→facts via `$FACT_STORE_CTL propose → ack(digest) → consume` (`stale_signal` only after consume). Per-open grounding = `attach-code-refs` when processing opens.
5. **Exit** — run `check-coverage`: ∀ init lens cleared∨skipped ∧ no (blocking∧open) ∧ (if demand manifest: all fulfilled∨deferred).
6. **Audit (user-triggered):** G4 internal hard · G5 external soft → Handoff (`view --synthesis off` / Writing). **G4 unchanged this wave.**

### Capability surface

Capabilities are catalogued in `references/g3-capabilities.md` — **Class 1** discover (1A user-triggered · 1B AI detect) · **Class 2** process · **Class 3** View. Availability and orchestration (what is global-anytime vs G3-scoped, and the two lanes) are owned by `gates/g3-refine.md`; this section does not restate them.

Provenance: opens stamp `trigger` × `means` (feeds G5 / I10); seed facts use `origin.type=seed` (not open trigger vocabulary). Presentation ref owns the rule that wording never drops stamps.

**Collaboration:** AI leads cognition + spine; user leads decision + progress. Scripts never judge semantics.

**User-facing wording:** every user-facing turn follows `references/inductive-presentation.md` — shield internal vocabulary; stamps and ✅ / ⚠️ labels are still recorded underneath.

---

## Pipeline

**Capability surface is primary.** Gates are checkpoints / audits around it:

**Fact Intake → Shape-confirm (G1) → Topic Loop (G2) → Gap-check (G3) → Audit G4 → Audit G5**

### Gate routing

<HARD-GATE>
Before executing any gate, read the corresponding gate file first.
Do NOT rely on memory for gate execution steps.
Fact Intake (Control spine §1) is **pre-gate** — complete it before loading G1.
</HARD-GATE>

| Gate | File | Load condition |
|------|------|-----------------|
| G1 — Shape-confirm | `gates/g1-shape.md` | Fact Intake done (classified `_facts.json`); or resume with `active_gate=G1` |
| G2 — Topic Loop | `gates/g2-topic-loop.md` | G1 closed; dialogue Topic Loop (no draft tree) |
| G3 — Gap-check | `gates/g3-refine.md` | G2 closed (Topic Loop exited) |
| G4 — Internal audit (hard) | `gates/g4-recompose.md` | User ready; G3 exit met |
| G5 — External audit (soft) | `gates/g5-provenance.md` | G4 closed |

---

## Roles & Global Rules

- **Who fixes what:** User decides how to fix; AI recommends; scripts move state only. G4/G5 find/name — never patch.
- **Focus guard:** Discovery may scan cross-section (read-only). Maturity / seed mutations require `activate-section` first; `add-open` has no focus-guard (doc-level).
- **Human inlet:** `add-open --trigger human --means human_probe|human_direct|human_view` — any altitude; optional `--detected-under <S>`.
- **AI detect:** never automatic; user asks. Means: `ai_scan` / `ai_intent_baseline` / `ai_probe`.
- **intent_coverage:** when a demand manifest exists, mount-or-create opens with `intent_ref` before inventing duplicates (`means=ai_intent_baseline`).

---

## Output Contract

**Maturity:** `inductive-scope/<SECTION>.json` — `{key, status, frontier_kw}` only + `_index.json` (`cycle_id`, `scope_ref`, `last_checkpoint`).

**Opens:** `inductive-opens.json` — `O-n` with `status`, `source{trigger,means}`, `kw`, `blocking`, `problem`, optional `detected_under` / `leaning` / `intent_ref` / `code_refs` / `resolved_by` / `note` / `reason`.

**Facts:** `_facts.json` — `F-n` with `text`, `lens_tags` (non-empty on inductive write), optional `origin{type,ref}`.  
**Multi-L (when parent locked a multi-node tree):** treat locked slice rulers as the split ruler. Before write: decompose mixed content into pure-L facts (seam → `full_plan` side + `depend_only` side). Each fact **must** include `home_l` and short `home_rationale`; persist via parent `$FACTS_CTL write --target-l <home_l>` (G1 divert allowed). Untagged writes hard-reject. Cannot split → stop for human (do not silent single-tag). `home_l=package` only after human confirms (`--package-confirm`); AI must not self-select package.

**Compose Writing input:** `_facts.json` (parent `begin-writing` validates existence). `$INDUCTIVE_G3_SECTION_CTL view --synthesis off` assembles fact text by lens (I2/V5).

**DQI** = optional resume/audit aid from gate-control; **not** decision SoT.

---

## Constraints

- Triple SoT = facts + opens + maturity (I1). Views non-authoritative (I3 / V1–V5). I13: View ≠ 碰撞.
- No AI hand-written JSON (I12) — section-control commands only.
- I5: subtract Settled facts (`_facts.json` by lens) before detect. I6: informed batch auto/manual/ignore. I7: coarse views stay coarse (no file:line in arch overview).
- G2 not an independent discovery gate; ground via `attach-code-refs` on `O-` ids.
- G4 hard / G5 soft; both user-triggered at delivery time.
- Clean cutover: no legacy `.md` / EP ledger as SoT; K2 projection retired.
