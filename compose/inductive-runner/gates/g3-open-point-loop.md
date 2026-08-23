> Part of inductive-runner · loaded only when `$CTX.active_gate` is `G3`

# Gate 3 — Open-point Loop

Expose and resolve unresolved questions after the Topic Loop. Work in
human-started batches until the human closes G3 through a validated exit.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |
| `$OPEN_POINT_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/open_point_control.py" --out-dir "$INDUCTIVE_OUT_DIR" --project-root "$PROJECT_ROOT"` |

Use each control's `--help` as the command and stdout contract.

## Goal

- Detect one coherent batch across every lens when the human requests it.
- Process one active open at a time.
- Preserve discussion as an equal path while G3 is active.

## Dialogue cognition

| Role | Authority |
|---|---|
| Human | Starts detection, disposes each open, and chooses whether to close |
| Parent Agent | Presents, discusses, dispatches analysis, and invokes controls |
| Analysis sub-agent | Returns read-only analysis for one requested scope |
| Control | Validates freshness and performs mechanical state changes |

The Parent Agent may recommend. It never substitutes its choice for the
human's disposition.

## Session boundaries

- Read `../references/open-point-model.md` before entering the loop.
- Resolve position through `$OPEN_POINT_CTL resolve-context`.
- Detect runner fetches `$OPEN_POINT_CTL detect-context`. Parent does not.
- Process context is `$OPEN_POINT_CTL process-context`.
- Initial position is `idle`; entry never starts detection.
- `processing` has one active batch and at most one active open.
- Free dialogue remains available in both positions.
- Route only from control stdout or a resolved context.

## Tool boundaries

- `../open-point-detect-runner/SKILL.md` owns full-lens batch analysis.
- `../open-point-process-runner/SKILL.md` owns analysis of one active open.
- `fact-store-runner` owns fact preview, acknowledgement, and consumption.
- `$OPEN_POINT_CTL` owns open, batch, receipt, and loop transitions.
- `$INDUCTIVE_GATE_CTL` owns G3 closure.
- Sub-agents do not interact with the human or mutate session state.
- On timeout, exception, or invalid output, write no state. The Parent Agent
  reports the failure or retries with the same inputs while they remain fresh.

## Routing

Heading = phase; first line = after which action (behavior map); rest = paths
(what, not a script).

### Detect a batch

After an explicit human Detect request from `idle`:

- `$OPEN_POINT_CTL ensure-frontier` — only Detect-path frontier init write.
- Dispatch `../open-point-detect-runner/SKILL.md` with `--out-dir` and
  `--project-root` only.
- Present the candidate batch without adding solutions. The human may
  adjust; the Parent Agent may refine.
- Register the final set through `$OPEN_POINT_CTL add-opens --opens-json`
  `--detect-json`. Payload and empty-batch rules live in `--help`.
- Route from the control: process a registered batch or return to `idle`.
- Freshness failure → discard and repeat Detect from fresh context.

### Process the batch

After `$OPEN_POINT_CTL process-context` names the active open:

- Dispatch `../open-point-process-runner/SKILL.md` for that open only.
- Route its `validity`:
  - **`null`** — present the blocker; keep the Open active. Refresh
    available input and re-dispatch; otherwise wait.
  - **`changed`** — present the replacement question; after human
    confirmation, `$OPEN_POINT_CTL update-open`, resolve
    `process-context`, and re-dispatch.
  - **`resolved`** — present the cited fact links; after human
    confirmation, `$OPEN_POINT_CTL settle-resolved`.
  - **`invalid`** — present the reason; after human confirmation,
    `$OPEN_POINT_CTL reject-open`.
  - **`valid`** — present its analysis for disposition.
- For `valid`, wait for one human action:
  - **Land** — `fact-store-runner` `propose --kind settle_open` → ack →
    consume. Do not call `$OPEN_POINT_CTL settle-resolved`.
  - **Ignore** — `$OPEN_POINT_CTL defer-open`.
  - **Skip** — `$OPEN_POINT_CTL skip-open`.
  - **Reject** — `$OPEN_POINT_CTL reject-open`.
- Apply only the named control for that action.
- Resolve `$OPEN_POINT_CTL process-context` or `resolve-context` before
  selecting the next open.
- Dialogue exposes another open → `$OPEN_POINT_CTL add-opens`. Append to
  the active batch tail; create a batch when none is active.
- Re-dispatch when substantive inputs change. Never act on a stale
  analysis.

### Batch done

After control returns to `idle` (registered opens no longer remain open):

- Offer: detect another batch; continue discussion; request G3 closure.
- Human asks to change a lens start X, or to mark a required lens as not
  blocking `cleared` → `$OPEN_POINT_CTL set-frontier` or `frontier-skip`;
  then Detect again before `cleared`. Details in `--help`.
- Do not offer a climb / skip / no-climb fork after Detect. Do not start
  another detection automatically.

## Close

After the human chooses `cleared` or `hard-skip`, call
`$INDUCTIVE_GATE_CTL gate-close --gate G3 --mode <cleared|hard-skip> --confirm`
once. The control validates the exit. On success, resolve a fresh `$CTX`
and load the gate it names. Do not close G3 through `$OPEN_POINT_CTL`.

## Hard cuts

- Do not overlap Detect and Process dispatches.
- Do not paste Detect measurement, Process analysis, `--detect-json`
  fields, or close predicates into this gate.
