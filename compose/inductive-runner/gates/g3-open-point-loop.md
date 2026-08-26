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
| Human | Starts Detect, disposes each registered open, and chooses whether to close |
| Parent Agent | Dispatches analysis, invokes controls, then presents Process output |
| Analysis sub-agent | Returns read-only analysis for one requested scope |
| Control | Performs mechanical state changes |

The Parent Agent may recommend. It never substitutes Land, Ignore, Skip,
or Reject.

## Session boundaries

- Open registry status: `open` unresolved; `settled` conclusion in facts
  (Land); `deferred` not landed now (Ignore); `rejected` false or outside
  the slice (Reject). Skip keeps `open`.
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
  reports the failure or retries with the same `process-context`.

## Routing

Detect writes the batch. Process disposes one registered open. Idle waits
for the next human start.

Heading = phase; first line = after which action; rest = paths (what, not
a script).

### Detect a batch

After an explicit human Detect request from `idle`:

1. `$OPEN_POINT_CTL ensure-frontier` — only Detect-path frontier init write.
2. Dispatch `../open-point-detect-runner/SKILL.md` with `--out-dir` and
   `--project-root` only.
3. `$OPEN_POINT_CTL add-opens --opens-json --detect-json` with that return.
   Contract in `--help`.
4. Route from the control: a registered batch → Process; otherwise `idle`.

### Process the batch

After `$OPEN_POINT_CTL process-context` names the active open:

1. Dispatch `../open-point-process-runner/SKILL.md` with the
   `process-context` stdout only. Do not prescribe how the runner
   investigates.
2. Present the runner return. Route its `status`:
   - **`blocked`** — present the reason; no disposition. Recover input
     and re-dispatch; otherwise wait.
   - **`open`** — present its analysis for disposition.
3. For `open`, wait for one human action:
   - **Land** — `fact-store-runner` `propose --kind settle_open` → ack →
     consume.
   - **Ignore** — `$OPEN_POINT_CTL defer-open`.
   - **Skip** — `$OPEN_POINT_CTL skip-open`.
   - **Reject** — `$OPEN_POINT_CTL reject-open`.
4. Apply only the named control for that action.
5. Resolve `$OPEN_POINT_CTL process-context` or `resolve-context` before
   selecting the next open.
6. Dialogue exposes another open → `$OPEN_POINT_CTL add-opens`. Append to
   the active batch tail; create a batch when none is active.
7. Re-dispatch when substantive inputs change.

### Batch done

After control returns to `idle` (registered opens no longer remain open):

1. Offer: detect another batch; continue discussion; request G3 closure.
2. Human asks to change a lens start X, or to mark a required lens as not
   blocking `cleared` → `$OPEN_POINT_CTL set-frontier` or `frontier-skip`;
   then Detect again before `cleared`. Details in `--help`.
3. Do not start another detection automatically.

## Close

After the human chooses `cleared` or `hard-skip`, call
`$INDUCTIVE_GATE_CTL gate-close --gate G3 --mode <cleared|hard-skip> --confirm`
once. The control validates the exit. On success, resolve a fresh `$CTX`
and load the gate it names. Do not close G3 through `$OPEN_POINT_CTL`.

## Hard cuts

- Do not overlap Detect and Process dispatches.
- After Detect, route only to Process or `idle`.
- Do not paste Detect measurement, Process analysis, `--detect-json`
  fields, or close predicates into this gate.
