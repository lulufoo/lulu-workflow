> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Topic Loop

**Status:** Design-convergence dialogue. **Not** draft-as-topic-tree. Production ⊥ display.

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

## Goal

Converge design via dialogue (not by writing the whole document at once).

Domain `cognitive_frame` (D1) and `intent_anchor` (D2) are the shared traction for the whole Topic Loop and for exit detection (`design_goal_met`) — not per-topic KPIs.

Close does **not** require a collab/Formal arc.

## Dialogue cognition

Mechanism = discover and work topics **in dialogue**. This is **not** two independent discovery channels (human || AI).

| Role | Does | Must not |
|------|------|----------|
| Human | May propose `gap`-state topics; **sole adopt authority** (dialogue adopt **or** select from `topic-landscape`); confirm `topic-portrait`; confirm conclusions; confirm exit / hard-skip | — |
| AI | May **guide-propose** after `topic-landscape` confirm; help pre-adopt clarify / deep work / summarize | Auto-adopt; skip `topic-landscape` / `topic-portrait` when their triggers fire; silent fact writes; treat D1+D2 exit check as a substitute for human exit |

G2 topic contract (definition, states, grain, lenses, tool protocols) → [`../references/g2-topic-model.md`](../references/g2-topic-model.md).

**Facade:** before guide-propose (or on refresh) → invoke `topic-landscape` → human confirm → default upstream; **pre-adopt clarify** → human adopt → `$TOPIC_CURRENT_CTL set` → invoke `topic-portrait` → human confirm → deep work. Direct dialogue adopt without a prior landscape is legal. Details only in the reference.

## Session notions

| Notion | Completion (cognitive) |
|--------|------------------------|
| topic (`gap`) | On seeking map / proposed; not yet human-adopted |
| topic (`adopted`) | title / scope / human-adopted (persist **at adopt**) |
| topic (`concluded`) | conclusion set → human confirm |
| production ⊥ display | Fact channel orthogonal to collab-arc display |

Bind session state only via `$MACRO` / `resolve-context` — not by treating data-file paths as workflow steps.

## Declared tools

| Tool | Trigger | Dispatch | G2-visible I/O | Forbidden |
|------|---------|----------|----------------|-----------|
| `topic-landscape` | Before AI guide-propose; when human/AI asks to refresh the seeking map; **before G2 close** | Inline protocol in `../references/g2-topic-model.md` (no runner dir) | Human-confirmable seeking map; adopt-by-select allowed after clarify | Skip confirm; rank by grain; adopted-topic DAG; paste protocol steps here; require landscape before every direct adopt |
| `topic-portrait` | After human adopt · **before deep work** | Same reference (topic-lens protocol) | Topic-context portrait + positioning triple; human confirm before deep work | Treat as seeking spine; deepen without confirm; run before adopt bind |
| `fact-runner` | Human confirms conclusion → persist facts | Inline public protocol order; argv in `fact-runner/SKILL.md` / `$FACT_CTL --help` | preview / digest / `stale_signal` | Silent fact writes; skip ACK; paste long argv here |
| `narrative-arc-runner` | After consume `stale_signal`, human chooses collab rebuild | `$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_SYNC` | DONE/FAIL summary | Expand `$NARRATIVE_ARC_*` / `$COMPOSE_VIEWER_CTL`; self-mount Viewer |

## Phase map

What structure — *not a hard dialogue lock*:

```text
topic-landscape → (optional guide-propose) → clarify (pre-adopt) → adopt → bind → topic-portrait → deep work → summarize → confirm conclusion → fact-runner → (pre-close topic-landscape) → gate-close
```

Optional: `stale_signal → offer collab rebuild` (details only in Branches).

## Phase → bind

| Phase | Bind |
|-------|------|
| before guide-propose / on seeking-map refresh | invoke `topic-landscape` (see reference) → human confirm |
| candidate (human propose or map select) | **pre-adopt clarify** (required) |
| human adopted (dialogue or map select) | `$TOPIC_CURRENT_CTL` `set` **at adopt** → invoke `topic-portrait` → human confirm → then deep work |
| after summarize, conclusion pending confirm | `$TOPIC_CURRENT_CTL` `set-conclusion` → human confirm → `confirm-conclusion` |
| conclusion confirmed | `fact-runner` public protocol order (see its SKILL / `$FACT_CTL --help`) |
| human confirms exit intent | invoke `topic-landscape` (close detect); if any `gap`-state remain → continue / hard-skip; then `$INDUCTIVE_GATE_CTL` `gate-close` (payload in Close) |

Details → `--help`. Do not paste flags / argv here.

## Branches

On consume `stale_signal`: optionally offer a human-chosen semantic collab arc rebuild (do **not** auto-run). If the human chooses rebuild:

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

| Summary | G2 action |
|---------|-----------|
| `mounted=true` | **Must** show `viewer_url` |
| `wrote=true` · `mounted=false` | Tell the user the arc was written but Viewer failed; optional re-dispatch of the same runner; **do not** self-mount |
| `wrote=false` | Existing collab arc unchanged; report `error` |

Refuse rebuild → continue with the existing collab arc.

On pre-close `topic-landscape`: if `gap`-state topics remain, offer **continue** (return to seeking/clarify) or **hard-skip** (write `topic_exit=hard_skip`). Do **not** silent-close.

## Close

Before close: design goal passes against D1+D2 (Goal); human confirms exit; no unconfirmed conclusion (Session notions); pre-close `topic-landscape` done; `topic_exit` is `cleared` (no remaining `gap`-state topics) or `hard_skip`. Collab/Formal arc not required. **Do not** auto-close without human exit.

```bash
$INDUCTIVE_GATE_CTL gate-close --gate G2 --payload '{"topic_loop_done": true, "design_goal_met": true, "human_exit_confirmed": true, "topic_exit": "cleared"}'
```

`topic_exit` may be `"hard_skip"` when the human hard-skips remaining `gap`-state topics.

## Hard cuts

- Do **not** call `$NARRATIVE_ARC_DRAFT_CTL` / draft-as-topic-tree / `$TOPIC_FOCUS_CTL` (retired).
- Do **not** invoke `$NARRATIVE_ARC_BUILD_CTL` / `$NARRATIVE_ARC_COLLAB_CTL` / `$COMPOSE_VIEWER_CTL` from this gate.
- Do **not** paste `topic-landscape` / `topic-portrait` product checklists into this gate — invoke the tool names; protocols stay in the reference.
