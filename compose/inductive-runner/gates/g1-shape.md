> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 1 — Shape-confirm (view, not a frozen SoT artifact)

**Prerequisites:** dispatched from parent compose stage `start`, or `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G1`.

**Goal:** confirm the change as a coarse **shape view** synthesized from Seeded section JSON (or, on cold start before Seed completes, from `$SCOPE_DOC`). Do **not** treat the view as SoT — corrections land in section commands.

1. **Session init (once):** `$INDUCTIVE_GATE_CTL init-session --sections <coverage_sections CSV> --mandatory <mandatory CSV> --cycle-id <cycle_id> --stage <compose stage>` (skip if resuming).
2. **Seed (if not done):** map `$SCOPE_DOC` decisions into sections via `$INDUCTIVE_G3_SECTION_CTL seed-decision` (`trigger=seed`, `means=scope`). Do not invent content beyond the scope (I4).
3. **Present shape view:** `$INDUCTIVE_G3_SECTION_CTL view --synthesis on --scope all --granularity 架构大局` (or default `shape_extraction` perspective). Optionally still render fields from `SCAN_CRITERIA.shape_extraction` for familiarity — content must come from section SoT / scope, not invention.
4. **User confirms or corrects.** Corrections → `seed-decision` / `update-decision` / `add-open` on owning sections → re-`view` until confirmed.

**Close criterion:** user confirms spine / To-Be / boundary. Then:

1. `$INDUCTIVE_G3_SECTION_CTL checkpoint --name shape`
2. `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"architecture_view": {...}, "shape_constraints": [...], "user_confirmed": true}'`  
   - Payload still accepted for resume/DQI aid; **SoT baseline for G4 is the checkpoint mark**, not a frozen view file.
3. Advance to G2 (usually auto-close — see `g2-grounding.md`).

**After close:** stop and await user — do **not** auto-run detect/sweep.
