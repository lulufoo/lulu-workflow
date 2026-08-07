> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Topic Loop (archive-10.0)

**Status:** Design-convergence dialogue. **Not** draft-as-topic-tree. Production ⊥ display.

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

## Goal

Converge design via **dialogue** under Domain `cognitive_frame` (D1) + `intent_anchor` (D2). AI topic proposals are guidance (coarse→fine); human must explicitly adopt. Hand facts only via **fact-production-runner** after conclusion confirm.

## Loop (What structure — not a hard dialogue lock)

```text
converge / adopt topic → clarify → (persist topic) → solve → summarize → human confirms conclusion → fact-production
```

1. Load D1+D2 from Domain (shared traction for dialogue + exit check).
2. Dialogue discovers topics (human may propose; AI may guide propose). **Adopt = human explicit.**
3. After clarify: persist current topic:

```bash
$TOPIC_CURRENT_CTL set --revision-dir "$INDUCTIVE_OUT_DIR" --title "<title>" --scope "<one-line scope>" --human-adopted
```

4. Solve → summarize → set conclusion → human confirms:

```bash
$TOPIC_CURRENT_CTL set-conclusion --revision-dir "$INDUCTIVE_OUT_DIR" --text "<conclusion>"
$TOPIC_CURRENT_CTL confirm-conclusion --revision-dir "$INDUCTIVE_OUT_DIR"
```

5. Hand off to fact-production (dialogue shows proposed list; no staging file):

```bash
$FACT_PRODUCTION_CTL commit --revision-dir "$INDUCTIVE_OUT_DIR" --confirm --facts-json '[...]'
# or: $FACT_PRODUCTION_CTL cancel --revision-dir "$INDUCTIVE_OUT_DIR"
```

6. On commit `stale_signal`: optionally offer human-chosen collab-arc regenerate (do **not** auto-run):

```bash
$NARRATIVE_ARC_COLLAB_CTL regenerate --revision-dir "$INDUCTIVE_OUT_DIR" --output-path "_narrative-arc.collab.json" --confirm
$COMPOSE_VIEWER_CTL mount --revision-dir "$INDUCTIVE_OUT_DIR" --arc-file "_narrative-arc.collab.json"
```

Refuse regenerate → continue with orphans OK. Viewer prints URL only.

**Hard cut:** do **not** call `$NARRATIVE_ARC_DRAFT_CTL` / draft-as-topic-tree / `$TOPIC_FOCUS_CTL` (retired).

## Close G2 → G3 (gap-check)

AI checks design goal against D1+D2. Fail → **cannot** close. Pass → still need **human confirm exit**. No unconfirmed conclusion on topic. Then:

```bash
$INDUCTIVE_GATE_CTL gate-close --gate G2 --payload '{"topic_loop_done": true, "design_goal_met": true, "human_exit_confirmed": true}'
```

**Do not** require collaboration/Formal arc for close. **Do not** auto-close without human exit.
