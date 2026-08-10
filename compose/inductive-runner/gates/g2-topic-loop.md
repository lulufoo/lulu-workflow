> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Topic Loop

**Status:** Design-convergence dialogue. **Not** draft-as-topic-tree.

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

## Goal

Converge design via dialogue (not by writing the whole document at once).

Domain `cognitive_frame` (D1) and `intent_anchor` (D2) are the shared traction for the whole Topic Loop and for exit detection (`design_goal_met`) — not per-topic KPIs.

Close does **not** require a collab/Formal arc.

## Dialogue cognition

Mechanism = use `topic-landscape` to discover and manage `gap` Topics, then
work human-adopted Topics **in dialogue**. This is **not** two independent
discovery channels (human || AI).

| Role | Does | Must not |
|------|------|----------|
| Human | May add, correct, or remove Topics during `topic-landscape` review; **sole authority** to confirm a landscape, select a `gap` node (caller then adopts), confirm conclusions, and confirm exit / hard-skip | — |
| AI | Autonomously build the initial `topic-landscape` from induction context and settled facts; reconcile human corrections and re-present; may **guide-propose** from a confirmed upstream frontier; may optionally invoke `topic-question-driver` after the portrait; help free dialogue / deep work / summarize | Treat human correction as a parallel discovery source; auto-adopt; require the question driver; skip `topic-landscape` / `topic-portrait` when their triggers fire; silent fact writes; treat a closure candidate or D1+D2 exit check as a substitute for human confirmation / exit |

## Session boundaries

- G2 maps Domain D1+D2 to the model's induction context, human add/correct/remove
  input to landscape corrections, the current settled-fact set to settled
  facts, and `$TOPIC_CURRENT_CTL` binding to the optional current topic.
- Fact production and collab-arc display are orthogonal.
- `$TOPIC_CURRENT_CTL` binds only the current adopted topic; it does not store the seeking landscape or close proof.
- Exit receipts are the pre-close landscape and exit receipt (Close).
- Route session state through `$MACRO` / `resolve-context`, never through data-file paths.

## Tool boundaries

- `topic-model`: generic contract in `../references/topic-model.md`.
- `topic-landscape`: generic contract in `../references/topic-landscape.md`.
- `topic-portrait`: generic contract in `../references/topic-portrait.md`.
- `topic-question-driver`: optional stateless contract in
  `../references/topic-question-driver.md`; it does not invoke `/converge`.
- After every `topic-landscape` result, record the G2 landscape receipt through
  `$INDUCTIVE_GATE_CTL record-topic-landscape`: use `seek`, `refresh`, or
  `pre_close` for `purpose` and pass caller-reported `gap_remaining`. Do not
  hand-write the receipt.
- `fact-runner`: use its public protocol.
- `narrative-arc-runner`
  - **Human request:** Any time while G2 is active.
  - **Dispatch:** `$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_ASYNC`; do not block or auto-run.
  - **Runner:** collab input, build, validation, persistence, and Viewer mount.
  - **G2:** dispatch and report its summary.
- Keep tool-internal arguments and output handling in their owning contracts.

## Routing

Route by signal; do not treat these entries as a scripted event chain.

| Signal / condition | Route |
|--------------------|-------|
| Seeking entry, refresh, Topic proposal, or invalid landscape | Invoke `topic-landscape`. A proposal enters its Review loop; require confirmation and node selection before binding. |
| Human selects a node from the current confirmed landscape | `$TOPIC_CURRENT_CTL set --title <selected-title> --scope <selected-scope> --human-adopted` → `topic-portrait`. |
| `topic-portrait` returns `Blocked` | Use free dialogue to obtain grounding, then rerun the portrait. Do not enter deep work before a non-`Blocked` portrait is presented. |
| Human materially corrects `Closure target` | Rebind with `$TOPIC_CURRENT_CTL set --title <current-title> --scope <corrected-scope> --human-adopted`, then rerun the portrait. |
| Non-`Blocked` portrait presented | Continue free dialogue or optionally invoke `topic-question-driver`; either path may be interrupted or resumed. |
| Driver returns `Next Question` / `Blocked` | Route to dialogue / free discussion. |
| `Topic Closure Candidate` or free-dialogue conclusion | Summarize → `$TOPIC_CURRENT_CTL set-conclusion` → human confirmation → `$TOPIC_CURRENT_CTL confirm-conclusion` → `fact-runner`; on success, return to Seeking. |
| `fact-runner` consume emits `stale_signal` | Offer the collab-display rebuild defined in Tool boundaries. |

## Close

- On human exit intent, invoke `topic-landscape`, record it with
  `purpose=pre_close`, and require confirmation. With no gaps, the human chooses
  **cleared**; otherwise they choose **continue** (return to Seeking) or
  **hard-skip**.
- After **cleared** or **hard-skip**, record
  `$INDUCTIVE_GATE_CTL record-g2-topic-exit` against the current pre-close
  landscape receipt, then gate-close.
- Gate-close payload requires `topic_loop_done=true`, `design_goal_met=true`,
  `human_exit_confirmed=true`, and `topic_exit` matching the recorded
  **cleared** or **hard-skip** result.
- The current landscape must be `pre_close`; its run and `gap_remaining` must
  match the human-confirmed exit receipt. **cleared** requires zero remaining
  gaps, and no Topic conclusion may remain unconfirmed. Never auto-close or
  hand-edit receipts.

## Hard cuts

- Do **not** call `$NARRATIVE_ARC_DRAFT_CTL` / draft-as-topic-tree / `$TOPIC_FOCUS_CTL` (retired).
- Do **not** invoke `$NARRATIVE_ARC_BUILD_CTL` / `$NARRATIVE_ARC_COLLAB_CTL` / `$COMPOSE_VIEWER_CTL` from this gate.
- Do **not** paste `topic-landscape` / `topic-portrait` /
  `topic-question-driver` product checklists into this gate — invoke the tool
  names; protocols stay in their references.
