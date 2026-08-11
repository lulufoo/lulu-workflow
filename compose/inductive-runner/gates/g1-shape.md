> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 1 — Shape-confirm (view checkpoint, not a frozen SoT artifact)

**Prerequisites:** dispatched from parent compose stage `start`, or `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G1`.

**Goal (I11):** after Seed, confirm the change as a coarse **shape view** synthesized from facts + maturity. The view is **not** SoT (V4). Corrections land only via section-control commands (I1). Baseline for later G4 = `checkpoint --name shape` (`last_checkpoint` + `checkpoint_git_sha`), not a frozen `architecture_view` file.

**Order (hard):** Seed **before** first shape view. Do not synthesize a shape view from `$SCOPE_REF` alone as a substitute for Seed.

1. **Session init (once):** `$INDUCTIVE_GATE_CTL init-session --sections <SECTION_REGISTRY.section_order as CSV> --mandatory <mandatory CSV> --cycle-id <cycle_id> --stage <compose stage> --scope-ref "$SCOPE_REF"` (skip if resuming). Forwards profile/scope_ref onto `_index.json`.
2. **Seed (if not done):** For each key `S` in `SECTION_REGISTRY.section_order`:
   1. `$INDUCTIVE_G3_SECTION_CTL activate-section --section <S>`
   2. **Has upstream substance** iff `$SCOPE_REF` has material that `section-registry` maps into `S` and that material is usable under **I4** (no invention).
      - If yes: `$INDUCTIVE_G3_SECTION_CTL seed-decision --section <S> --lens-tags <S> --text …` → re-judge KW → `$INDUCTIVE_G3_SECTION_CTL set-frontier --section <S> --kw <N>` (`--kw` on seed is optional hint; writes `_facts.json` with `origin.type=seed`).
      - If no and `SECTION_REGISTRY.sections[S].presence` is `optional`: `$INDUCTIVE_G3_SECTION_CTL skip-section --section <S> --reason "no upstream substance"`.
      - If no and presence is `required` (default): do **not** skip; leave active for G3 discovery / later clear.

   Mapping: structural→ST, boundary→SC, goals→GO, invariants→I, …. Prefer a git commit `"seeded"`. Former peel keys are first-class init lenses (peel retired for this runner).
3. **Present shape view:** `$INDUCTIVE_G3_SECTION_CTL view --synthesis on --scope all --granularity <arch-overview hint>` (e.g. default perspective from `SCAN_CRITERIA.shape_extraction` — **hint only**, not a shape schema; V3). Content must come from facts + maturity SoT; gaps stay gaps (V2). Coarse altitude only — no file:line in the overview (I7).
4. **User confirms or corrects.** Corrections → `activate-section` + `seed-decision` / `$FACT_STORE_CTL propose --kind update → ack → consume` / `add-open` → re-`set-frontier` if lens facts changed → re-`view` until confirmed.
5. **Close:** `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"user_confirmed": true}'`  
   - **Hard close criterion:** user confirmed.  
   - `gate-close G1` records `checkpoint --name shape` (authoritative mark + best-effort `checkpoint_git_sha`). Do **not** call `checkpoint` separately before close — one owner.  
   - Optional resume aid only: you may also include `architecture_view` + `shape_constraints` in the payload for DQI; if present, fields must be complete. **Never** treat DQI as SoT or as G4's shape baseline.
6. Advance to G2 (Topic Loop — see `g2-topic-loop.md`). After G1 close: enter dialogue Topic Loop directly. **Do not** ensure draft-as-topic-tree. Viewer / semantic collab-arc rebuild are optional later (after fact-settle stale), human-chosen.

**After close:** default-present the confirmed shape view once more, then enter Topic Loop orchestration (`g2-topic-loop.md`). Do **not** auto-close G2. View (Class 3, sensing) and Class 1A discovery remain available anytime after Seed (parent SKILL).
