> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 1 — Shape-confirm (view checkpoint, not a frozen SoT artifact)

**Prerequisites:** dispatched from parent compose stage `start`, or `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G1`. **Fact-intake** already completed (classified `_facts.json` with `origin.type=seed`).

**Goal (I11):** after fact-intake, confirm the change as a coarse **shape view** synthesized from facts + maturity. The view is **not** SoT (V4). Corrections land only via section-control commands (I1). Baseline for later G4 = `checkpoint --name shape` (`last_checkpoint` + `checkpoint_git_sha`), not a frozen `architecture_view` file.

**Order (hard):** Fact-intake **before** first shape view. Do not synthesize a shape view from `$SCOPE_REF` / `$SOURCE_PATH` alone as a substitute for intake facts.

1. **Session init (once):** `$INDUCTIVE_GATE_CTL init-session --sections <SECTION_REGISTRY.section_order as CSV> --mandatory <mandatory CSV> --cycle-id <cycle_id> --scope-ref "$SCOPE_REF"` (skip if resuming). Forwards scope_ref onto `_index.json`; `_index.profile` comes from the revision session pointer.
2. **Maturity bind (if not done):** Intake already wrote `_facts.json` (seed + disposition). Do **not** re-cover intake substance via `seed-decision` from `$SOURCE_PATH`. For each key `S` in `SECTION_REGISTRY.section_order`:
   1. `$INDUCTIVE_G3_SECTION_CTL activate-section --section <S>`
   2. **Has lens substance** iff existing facts (typically `carried` / tagged) map into `S` under **I4**.
      - If yes: re-judge KW → `$INDUCTIVE_G3_SECTION_CTL set-frontier --section <S> --kw <N>`.
      - If no and `SECTION_REGISTRY.sections[S].presence` is `optional`: `$INDUCTIVE_G3_SECTION_CTL skip-section --section <S> --reason "no upstream substance"`.
      - If no and presence is `required` (default): do **not** skip; leave active for G3 discovery / later clear.

   Mapping: structural→ST, boundary→SC, goals→GO, invariants→I, …. Prefer a git commit `"intake-bound"` (or equivalent). Former peel keys are first-class init lenses (peel retired for this runner).
3. **Present shape view:** `$INDUCTIVE_G3_SECTION_CTL view --synthesis on --scope all --granularity <arch-overview hint>` (e.g. default perspective from `SCAN_CRITERIA.shape_extraction` — **hint only**, not a shape schema; V3). Content must come from facts + maturity SoT; gaps stay gaps (V2). Coarse altitude only — no file:line in the overview (I7).
4. **User confirms or corrects.** Corrections → `activate-section` + `seed-decision` / `$FACT_STORE_CTL propose --kind update → ack → consume` / `add-open` → re-`set-frontier` if lens facts changed → re-`view` until confirmed. (`seed-decision` here is human correction / local add — not intake cover-stamp.)
5. **Close:** `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"user_confirmed": true}'`  
   - **Hard close criterion:** user confirmed.  
   - `gate-close G1` records `checkpoint --name shape` (authoritative mark + best-effort `checkpoint_git_sha`). Do **not** call `checkpoint` separately before close — one owner.  
   - Optional resume aid only: you may also include `architecture_view` + `shape_constraints` in the payload for DQI; if present, fields must be complete. **Never** treat DQI as SoT or as G4's shape baseline.
6. Advance to G2 (Topic Loop — see `g2-topic-loop.md`). After G1 close: enter dialogue Topic Loop directly. **Do not** ensure draft-as-topic-tree. Viewer / semantic collab-arc rebuild are optional later (after fact-settle stale), human-chosen.

**After close:** default-present the confirmed shape view once more, then enter Topic Loop orchestration (`g2-topic-loop.md`). Do **not** auto-close G2. Class 1A discovery remains available anytime after fact-intake (parent SKILL).
