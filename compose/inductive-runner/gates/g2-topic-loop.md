> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Topic Loop

**Status:** Design-convergence dialogue. **Not** draft-as-topic-tree.

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

## Goal

Converge design via dialogue (not by writing the whole document at once).

Domain `cognitive_frame` (D1) and `intent_anchor` (D2) are the shared traction for the whole Topic Loop and for exit detection (`design_goal_met`) — not per-topic KPIs.

Close does **not** require a collab/Formal arc.

## Dialogue cognition

Mechanism = discover and work topics **in dialogue**. This is **not** two independent discovery channels (human || AI).

| Role | Does | Must not |
|------|------|----------|
| Human | May propose `gap`-state topics; **sole authority** to adopt a candidate from dialogue or `topic-landscape`; confirm conclusions; confirm exit / hard-skip | — |
| AI | May **guide-propose** after `topic-landscape` confirm; help free dialogue / deep work / summarize | Auto-adopt; skip `topic-landscape` / `topic-portrait` when their triggers fire; silent fact writes; treat D1+D2 exit check as a substitute for human exit |

G2 topic contract (definition, states, grain, lenses, tool protocols) → [`../references/g2-topic-model.md`](../references/g2-topic-model.md).

## Session boundaries

- Fact production and collab-arc display are orthogonal.
- `$TOPIC_CURRENT_CTL` binds only the current adopted topic; it does not store the seeking map or close proof.
- Exit receipts are the pre-close landscape and exit receipt (Workflow: Exit).
- Route session state through `$MACRO` / `resolve-context`, never through data-file paths.

## Tool boundaries

- `topic-landscape` / `topic-portrait`: inline protocols in `../references/g2-topic-model.md`.
- `fact-runner`: use its public protocol.
- `narrative-arc-runner`: optional collab rebuild via `$SUBAGENT_TOOL`.
- Keep tool-internal arguments and output handling in their owning contracts.

## Workflow

Orchestration only; not a scripted event-chain gate.

### Seeking

- Before AI guide-proposes and on a map refresh, invoke `topic-landscape` and require human confirmation.
- From a confirmed map, guide from the most-upstream `gap`; the human may choose another node or continue free dialogue.
- Direct dialogue may propose and adopt a topic without a landscape.

### Work a topic

- A dialogue signal or map selection supplies an adopt candidate; perform `adopt` as defined in the Topic Model.
- Then invoke `topic-portrait` before deep work. Presentation is required; confirmation is not.
- After summary: `$TOPIC_CURRENT_CTL` `set-conclusion` → human confirm → `confirm-conclusion` → `fact-runner` public protocol.
- After `fact-runner` completes successfully, return to Seeking.

### Exit

- On human exit intent, invoke `topic-landscape` with `pre_close` and require confirmation. With no gaps, the human chooses **cleared**; otherwise they choose **continue** (return to Seeking) or **hard-skip**.
- After **cleared** or **hard-skip**, record matching `$INDUCTIVE_GATE_CTL record-topic-landscape` and `record-g2-topic-exit` receipts, then gate-close.
- Gate-close requires the D1+D2 design goal, human exit, no unconfirmed conclusion, and matching pre-close landscape, exit receipt, and `payload.topic_exit`. Never auto-close or hand-edit receipts.

### Display refresh (optional)

- Only after `fact-runner` consume emits `stale_signal`, offer a semantic collab-arc rebuild; never auto-run it.
- If chosen, dispatch `narrative-arc-runner` via `$SUBAGENT_TOOL` and `$SUBAGENT_AWAIT_SYNC` under its collab input contract. Parse only its summary: show `viewer_url` when mounted; otherwise report the partial or failed result without self-mounting.
- Refusal or failure retains the existing collab arc. A collab/Formal arc is never a close prerequisite.

## Hard cuts

- Do **not** call `$NARRATIVE_ARC_DRAFT_CTL` / draft-as-topic-tree / `$TOPIC_FOCUS_CTL` (retired).
- Do **not** invoke `$NARRATIVE_ARC_BUILD_CTL` / `$NARRATIVE_ARC_COLLAB_CTL` / `$COMPOSE_VIEWER_CTL` from this gate.
- Do **not** paste `topic-landscape` / `topic-portrait` product checklists into this gate — invoke the tool names; protocols stay in the reference.
