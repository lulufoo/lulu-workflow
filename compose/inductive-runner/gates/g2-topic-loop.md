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
| Human | May propose pending topics; **sole adopt authority** (dialogue adopt **or** select from `gap-landscape`); confirm `topic-portrait`; confirm conclusions; confirm exit from the Loop | — |
| AI | May **guide-propose** after `gap-landscape` confirm; help clarify / solve / summarize | Auto-adopt; skip `gap-landscape` / `topic-portrait` when their triggers fire; silent fact writes; treat D1+D2 exit check as a substitute for human exit |

Topic cognition (grain, two portrait lenses, tool protocols) → [`../references/topic-cognition-model.md`](../references/topic-cognition-model.md).

**Facade:** before guide-propose (or on refresh) → invoke `gap-landscape` → human confirm → default upstream; after human adopt at clarify entry → invoke `topic-portrait` → human confirm → then deepen clarify. Details only in the reference.

## Session notions

| Notion | Completion (cognitive) |
|--------|------------------------|
| pending topic | Proposed; not yet human-adopted |
| current topic | title / scope / human-adopted (persist after clarify) |
| conclusion | set → human confirm |
| production ⊥ display | Fact channel orthogonal to collab-arc display |

Bind session state only via `$MACRO` / `resolve-context` — not by treating data-file paths as workflow steps.

## Declared tools

| Tool | Trigger | Dispatch | G2-visible I/O | Forbidden |
|------|---------|----------|----------------|-----------|
| `gap-landscape` | Before AI guide-propose; when human/AI asks to refresh the gap map | Inline cognitive protocol in `../references/topic-cognition-model.md` (no runner dir) | Human-confirmable seeking map; adopt-by-select allowed | Skip confirm; rank by grain; topic↔topic DAG; paste protocol steps here |
| `topic-portrait` | After human adopt · **clarify entry** | Same reference (topic-lens protocol) | Topic-context portrait + positioning triple; human confirm before deep clarify | Treat as seeking spine; deepen clarify without confirm |
| `fact-runner` | Human confirms conclusion → persist facts | Inline public protocol order; argv in `fact-runner/SKILL.md` / `$FACT_CTL --help` | preview / digest / `stale_signal` | Silent fact writes; skip ACK; paste long argv here |
| `narrative-arc-runner` | After consume `stale_signal`, human chooses collab rebuild | `$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_SYNC` | DONE/FAIL summary | Expand `$NARRATIVE_ARC_*` / `$COMPOSE_VIEWER_CTL`; self-mount Viewer |

## Phase map

What structure — *not a hard dialogue lock*:

```text
gap-landscape → (optional guide-propose) → adopt → topic-portrait → clarify → persist topic → solve → summarize → confirm conclusion → fact-runner
```

Optional: `stale_signal → offer collab rebuild` (details only in Branches).

## Phase → bind

| Phase | Bind |
|-------|------|
| before guide-propose / on gap-map refresh | invoke `gap-landscape` (see reference) → human confirm |
| human adopted (dialogue or map select) · clarify entry | invoke `topic-portrait` → human confirm → then clarify |
| clarify done and adopted | `$TOPIC_CURRENT_CTL` `set` |
| after summarize, conclusion pending confirm | `$TOPIC_CURRENT_CTL` `set-conclusion` → human confirm → `confirm-conclusion` |
| conclusion confirmed | `fact-runner` public protocol order (see its SKILL / `$FACT_CTL --help`) |
| human confirms exit and Close predicates hold | `$INDUCTIVE_GATE_CTL` `gate-close` (payload in Close) |

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

## Close

Before close: design goal passes against D1+D2 (Goal); human confirms exit; no unconfirmed conclusion (Session notions). Collab/Formal arc not required. **Do not** auto-close without human exit.

```bash
$INDUCTIVE_GATE_CTL gate-close --gate G2 --payload '{"topic_loop_done": true, "design_goal_met": true, "human_exit_confirmed": true}'
```

## Hard cuts

- Do **not** call `$NARRATIVE_ARC_DRAFT_CTL` / draft-as-topic-tree / `$TOPIC_FOCUS_CTL` (retired).
- Do **not** invoke `$NARRATIVE_ARC_BUILD_CTL` / `$NARRATIVE_ARC_COLLAB_CTL` / `$COMPOSE_VIEWER_CTL` from this gate.
- Do **not** paste `gap-landscape` / `topic-portrait` product checklists into this gate — invoke the tool names; protocols stay in the reference.
