> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 1 — Shape-confirm (view checkpoint, not a frozen SoT artifact)

**Prerequisites:** dispatched from parent compose stage `start`, or `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G1`.

**Goal (I11):** after Seed, confirm the change as a coarse **shape view** synthesized from section JSON. The view is **not** SoT (V4). Corrections land only in section commands (I1). Baseline for later G4 = `checkpoint --name shape`, not a frozen `architecture_view` file.

**Order (hard):** Seed **before** first shape view. Do not synthesize a shape view from `$SCOPE_DOC` alone as a substitute for Seed.

1. **Session init (once):** `$INDUCTIVE_GATE_CTL init-session --sections <coverage_sections CSV> --mandatory <mandatory CSV> --cycle-id <cycle_id> --stage <compose stage>` (skip if resuming).
2. **Seed (if not done):** map `$SCOPE_DOC` decisions into sections via `$INDUCTIVE_G3_SECTION_CTL seed-decision` (`trigger=seed`, `means=scope`). Use `section-registry` mapping (structural→ST, boundary→SC, goals→GO, invariants→I, …). **I4:** do not invent beyond the scope. Prefer a git commit `"seeded"`.
3. **Present shape view:** `$INDUCTIVE_G3_SECTION_CTL view --synthesis on --scope all --granularity <arch-overview hint>` (e.g. default perspective from `SCAN_CRITERIA.shape_extraction` — **hint only**, not a shape schema; V3). Content must come from section SoT; gaps stay gaps (V2). Coarse altitude only — no file:line in the overview (I7).
4. **User confirms or corrects.** Corrections → `seed-decision` / `update-decision` / `add-open` on owning sections → re-`view` until confirmed.
5. **Checkpoint + close:**
   1. `$INDUCTIVE_G3_SECTION_CTL checkpoint --name shape` (authoritative Shape-confirm mark; records `last_checkpoint` + best-effort `checkpoint_git_sha` for G4).
   2. `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"user_confirmed": true}'`  
      - **Hard close criterion:** user confirmed + shape checkpoint.  
      - Optional resume aid only: you may also include `architecture_view` + `shape_constraints` in the payload for DQI; if present, fields must be complete. **Never** treat DQI as SoT or as G4's shape baseline.
6. Advance to G2 (usually auto-close — see `g2-grounding.md`).

**After close:** default-present the confirmed shape view once more, then **stop and await user** — do **not** auto-run detect/sweep. Capabilities ① view / ② 碰撞 remain available anytime (parent SKILL); they are not Gate-3-only.
