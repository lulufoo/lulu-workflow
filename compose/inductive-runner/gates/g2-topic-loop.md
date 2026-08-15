> Part of inductive-runner · gate execution entry · loaded from `../SKILL.md`

# Gate 2 — Topic Loop

**Prerequisites:** `$INDUCTIVE_GATE_CTL resolve-context` reports `active_gate` is `G2` (G1 closed).

## Goal

Converge the current Compose stage's substance through Topic-driven dialogue.
Domain `cognitive_frame` (D1) and `intent_anchor` (D2) jointly guide the Topic
Loop as a whole.

## Dialogue cognition

Mechanism = use `topic-landscape` to discover and manage `gap` Topics, then
work human-adopted Topics **in dialogue**. This is **not** two independent
discovery channels (human || AI).

| Role | Does | Must not |
|------|------|----------|
| Human | **sole authority** to confirm a landscape, select a `gap` node (caller then adopts), confirm conclusions, and confirm exit / hard-skip | — |
| AI | Autonomously build the initial `topic-landscape` from induction context and settled facts; may **guide-propose** from a confirmed upstream frontier; may optionally invoke `topic-question-driver` after the portrait; help free dialogue / deep work / summarize | Treat human correction as a parallel discovery source; auto-adopt; require the question driver; skip `topic-landscape` / `topic-portrait` when their triggers fire; silent fact writes; treat a closure candidate or D1+D2 exit check as a substitute for human confirmation / exit |

## Session boundaries

- G2 maps Domain D1+D2 to the model's induction context, the current
  settled-fact set to settled facts, and `$TOPIC_CURRENT_CTL` binding to
  the optional current topic.
- Fact production and narrative-arc display are orthogonal.
- `$TOPIC_CURRENT_CTL` binds only the current adopted topic; it does not store the seeking landscape or close proof.
- Exit receipts are the pre-close landscape and exit receipt (Close).
- Route session state through `$MACRO` / `resolve-context`, never through data-file paths.

## Tool boundaries

- `topic-model`: generic contract in `../references/topic-model.md`.
- `topic-landscape`: generic contract in `../references/topic-landscape.md`.
- `topic-portrait`: generic contract in `../references/topic-portrait.md`.
- `topic-question-driver`: optional stateless contract in
  `../references/topic-question-driver.md`; it does not invoke `/converge`.
- `fact-store-runner`: use its public protocol.
- `narrative-arc-runner`
  - **Human request:** Any time while G2 is active.
  - **Dispatch:** `$SUBAGENT_TOOL` + `$SUBAGENT_AWAIT_ASYNC`; do not block or auto-run.
  - **Runner Input** (pin while Viewer HTML still client-guards Formal basename):

```text
REVISION_DIR: <inductive out dir>
PROJECT_ROOT: <abs project root>
CYCLE_ID: <cycle id>
OUTPUT_PATH: _narrative-arc.collab.json
MOUNT: true
```

  - **G2:** dispatch and report its Summary (`wrote` / `write_ready` / `mounted`).
    Protocol lives in `narrative-arc-runner/SKILL.md` + `contracts/delivery.md`.
- Keep tool-internal arguments and output handling in their owning contracts.

## Routing

Heading = phase; first line = after which action (behavior map); rest = paths
(what, not a script).

### Topic landscape

Invoke on seeking entry, refresh, Topic proposal, or invalid landscape. After
`topic-landscape` runs: behavior map for seeking present / review.

- Receipt: `$INDUCTIVE_GATE_CTL record-topic-landscape` with
  `purpose=seek|refresh` and caller-reported `gap_remaining`; never hand-write.
- Review → re-present until human confirms.
- Select a confirmed `gap` node →
  `$TOPIC_CURRENT_CTL set --title <selected-title> --scope <selected-scope> --human-adopted`
  → `topic-portrait`.
- May guide-propose from upstream frontier; selection is not frontier-only.
- Invalidate → rebuild, re-present, reconfirm before select.

### Topic portrait

After `topic-portrait` runs: behavior map for the adopted-topic view.

- `Blocked` → free dialogue for grounding → rerun; no deep work until
  non-`Blocked`.
- Material Closure-target correction → rebind
  `--scope <corrected-scope> --human-adopted` → rerun.
- Non-`Blocked` → prefer `topic-question-driver`; free dialogue remains open
  (interruptible either way). State which path is active.

### Topic question drive

After `topic-question-driver` runs: behavior map for its outputs.

- `Next Question` → dialogue.
- `Conclusion Candidate` → Topic conclusion.
- Not mandatory; free dialogue or rewrite remains open.

### Topic conclusion

After a Conclusion Candidate or free-dialogue conclusion: behavior map for
convergent close.

- Conclude: Summarize → `set-conclusion` → human confirm →
  `confirm-conclusion` → `fact-store-runner` → Seeking (`topic-landscape`).
- After Seeking present when `stale_signal`: remind `narrative-arc-runner` on request (no auto-run).

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
- Do **not** invoke `$NARRATIVE_ARC_BUILD_CTL` / `$NARRATIVE_ARC_CTL` /
  `$COMPOSE_VIEWER_CTL` from this gate — only dispatch `narrative-arc-runner`.
- Do **not** paste `topic-landscape` / `topic-portrait` /
  `topic-question-driver` product checklists into this gate — invoke the tool
  names; protocols stay in their references.
