> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Topic Loop (archive-10.0 / archive-16.0)

**Status:** Design-convergence dialogue. **Not** draft-as-topic-tree. Production ⊥ display.

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

## Declared tools

| Tool | Trigger | Dispatch | G2-visible I/O | Forbidden |
|------|---------|----------|----------------|-----------|
| `fact-runner` | Human confirms conclusion → persist facts | Inline public protocol order; argv in `fact-runner/SKILL.md` / `$FACT_CTL --help` | preview / digest / `stale_signal` | Silent fact writes; skip ACK; paste long argv here |
| `narrative-arc-runner` | After consume `stale_signal`, human chooses collab rebuild | `$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_SYNC` | DONE/FAIL summary | Expand `$NARRATIVE_ARC_*` / `$COMPOSE_VIEWER_CTL`; self-mount Viewer |

## Goal

Converge design via **dialogue** under Domain `cognitive_frame` (D1) + `intent_anchor` (D2). AI topic proposals are guidance (coarse→fine); human must explicitly adopt. Hand facts only via **fact-runner** after conclusion confirm.

## Loop (What structure — not a hard dialogue lock)

```text
converge / adopt topic → clarify → (persist topic) → solve → summarize → human confirms conclusion → fact-runner
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

5. Hand facts via **fact-runner** public protocol (dialogue shows the exact proposal; no staging file):

```text
propose → display exact preview → human ACK → ack → consume
(see fact-runner/SKILL.md / $FACT_CTL --help for argv; or revoke)
```

6. On consume `stale_signal`: optionally offer a human-chosen semantic collab
   arc rebuild (do **not** auto-run). If the human chooses rebuild:

Dispatch `narrative-arc-runner` via `$SUBAGENT_TOOL` with `$SUBAGENT_AWAIT_SYNC`:

```text
Load {actual $SKILL_ROOT}/compose/narrative-arc-runner/SKILL.md and follow its instructions.

## Input
target: collab
INDUCTIVE_OUT_DIR: {actual $INDUCTIVE_OUT_DIR}
PROJECT_ROOT: {actual $PROJECT_ROOT}
COMPOSE_PROFILE: {actual $COMPOSE_PROFILE}
CYCLE_ID: {actual $CYCLE_ID}
OUTPUT_PATH: _narrative-arc.collab.json
```

Parse the subagent summary only (do not re-run its internals):

- `mounted=true` → **must** show `viewer_url` to the user.
- `wrote=true` · `mounted=false` → tell the user the arc was written but Viewer failed; optional re-dispatch of the same runner; **do not** self-mount.
- `wrote=false` → existing collab arc unchanged; report `error`.

Refuse rebuild → continue with the existing collab arc.

**Hard cut:** do **not** call `$NARRATIVE_ARC_DRAFT_CTL` / draft-as-topic-tree / `$TOPIC_FOCUS_CTL` (retired). Do **not** invoke `$NARRATIVE_ARC_BUILD_CTL` / `$NARRATIVE_ARC_COLLAB_CTL` / `$COMPOSE_VIEWER_CTL` from this gate.

## Close G2 → G3 (gap-check)

AI checks design goal against D1+D2. Fail → **cannot** close. Pass → still need **human confirm exit**. No unconfirmed conclusion on topic. Then:

```bash
$INDUCTIVE_GATE_CTL gate-close --gate G2 --payload '{"topic_loop_done": true, "design_goal_met": true, "human_exit_confirmed": true}'
```

**Do not** require collaboration/Formal arc for close. **Do not** auto-close without human exit.
