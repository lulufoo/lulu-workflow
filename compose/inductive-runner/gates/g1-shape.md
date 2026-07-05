> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 1 — Shape (coarse shape artifact)

**Prerequisites:** dispatched from parent compose stage `start`, or `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G1`.

**Goal:** render the change as a coarse **shape artifact** (`SCAN_CRITERIA.shape_extraction.artifact_label`) — the cold-start structural abstraction, as one coherent whole. Do **not** examine implementation; do **not** organize by section; do **not** drop to implementation detail.

1. Read `$SCOPE_DOC` in full (use its decision conclusions as primary source).
2. Produce one **shape artifact** (the carrier every later gate refines).
   For each field in `SCAN_CRITERIA.shape_extraction.required` (and `.optional` where applicable): render using the field's `carrier`, obey its `forbidden`, and present `as_is`+`to_be` as a paired before→after block. Field labels, guidance, and render rules are in `SCAN_CRITERIA.shape_extraction.fields` — do not deviate from them.
3. Append the 1–2 **load-bearing claims you are least sure of**, restricted to **shape altitude** — the spine framing, a boundary call, a structural relation, or an implicit premise the source material can't tell you. **Do not** raise implementation risks here — those belong to Gate 3.

**Present:** the shape artifact (all `shape_extraction.required` fields + any applicable `.optional` fields, rendered per `shape_extraction.fields`) + the shape-level load-bearing claims.

**Close criterion:** the user confirms the spine, the To-Be structure, and the boundary (e.g. "形状确认" / "shape confirmed"). Corrections are folded in and the view re-presented until confirmed. On confirmation, call `$INDUCTIVE_GATE_CTL gate-close --gate G1 --payload '{"architecture_view": {...}, "shape_constraints": [...]}'` — this persists the `architecture_view` to the DQI, freezes the load-bearing claims into **shape constraints** (invariants Gate 3 must respect and must not re-open), and advances the spine to Gate 2.

**Session init (once per session, at Gate 1 start):** call `$INDUCTIVE_GATE_CTL init-session --sections <coverage_sections CSV> --mandatory <mandatory_coverage_prompt CSV> --cycle-id <cycle_id> --stage <compose stage>` to seed both the gate state and section pointer. Skip if resuming an existing session — `$INDUCTIVE_GATE_CTL resolve-context` will confirm the current active gate.
