> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Topic Loop (archive-9.0)

**Status:** Replaces folded grounding. G2 is the **Topic Loop** main discovery cycle (single tree dual-role narrative axis).

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

## Hard enter (after G1)

1. Build process draft from current facts (AI may refine; mechanical skeleton OK first):

```bash
$NARRATIVE_ARC_DRAFT_CTL ensure-skeleton --revision-dir "$INDUCTIVE_OUT_DIR"
```

Agent may then `$NARRATIVE_ARC_DRAFT_CTL write` a richer draft (`kind=narrative-arc-draft`, `status=draft`). Validate:

```bash
$NARRATIVE_ARC_DRAFT_CTL validate --revision-dir "$INDUCTIVE_OUT_DIR"
```

2. Mount Viewer (prints URL only — do not auto-open browser):

```bash
$NARRATIVE_ARC_VIEWER_CTL mount --revision-dir "$INDUCTIVE_OUT_DIR"
```

Present the returned `url` to the user for paste into Cursor browser.

3. Topic Loop (see archive-9.0 T3): for each focused leaf run `define → discuss → summarize`.
   - Routing: `$TOPIC_FOCUS_CTL set|clear|set-phase`
   - Tree: `$NARRATIVE_ARC_DRAFT_CTL add-node|move|rename|deepen|attach-fact`
   - Facts: existing `$INDUCTIVE_G3_SECTION_CTL` / facts write path; then `attach-fact`
   - No focus → do not attach settled facts
   - MVP: no delete topic

4. Section `activate-section` is **not** the discussion router during G2.

## Close G2 → G3 (gap-check)

User explicitly exits Topic Loop. Prefer `focus` cleared. Then:

```bash
$INDUCTIVE_GATE_CTL gate-close --gate G2 --payload '{"topic_loop_done": true}'
```

**Hard close criterion:** payload `topic_loop_done: true` **and** valid `_narrative-arc.draft.json` present.

**Do not** auto-close G2 without user exit.
