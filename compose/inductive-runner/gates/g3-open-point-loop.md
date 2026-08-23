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

## Loop

### Detect a batch

Run only from `idle` after an explicit human request.

1. Run `$OPEN_POINT_CTL ensure-frontier`. This is the only Detect-path
   frontier init write.
2. Dispatch `../open-point-detect-runner/SKILL.md` with `--out-dir` and
   `--project-root` only. Do not pass snapshot fields.
3. Require one complete lens pass. Each lens starts at its
   `frontier_kw` (first pass: 0) and reports one coarsest remaining
   gap KW. Several questions at that KW are legal. Each registered
   Detect Open needs `lens` and `source.means` in `scan|intent|probe`,
   and that means must not be inert.
4. Present the candidate batch without adding solutions.
5. Let the human adjust the candidates; the Parent Agent may refine them.
6. Register the final set through `$OPEN_POINT_CTL add-opens --opens-json`
   `--detect-json`. Detect must pass `--detect-json` with the echoed
   digests, `inert_means`, and `lens_measurements`. Empty
   `--opens-json` is legal only with detect metadata. Control writes
   each non-null `gap_kw` as that lens's next start.
7. Route from the control result: process a registered batch or return to
   `idle`.

If freshness validation fails, discard the result and repeat detection from
fresh context. Removing all candidates from a non-empty detection is not a
zero-result detection.

### Process the batch

1. Resolve the active open through `$OPEN_POINT_CTL process-context`.
2. Dispatch `../open-point-process-runner/SKILL.md` for that open only.
3. Route its `validity` result:
   - **`null`** — not assessed. Present the blocker and keep the Open active.
     Refresh available input and re-dispatch; otherwise wait.
   - **`changed`** — present the replacement question; after human confirmation,
     call `$OPEN_POINT_CTL update-open`, resolve `process-context`, and
     re-dispatch analysis.
   - **`resolved`** — present the cited fact links; after human confirmation,
     call `$OPEN_POINT_CTL settle-resolved`.
   - **`invalid`** — present the reason; after human confirmation, call
     `$OPEN_POINT_CTL reject-open`.
   - **`valid`** — present its analysis for disposition.
4. For `valid`, wait for one human action:
   - **Land** — load `fact-store-runner` and run `propose --kind settle_open`
     → ack → consume. Do not call `$OPEN_POINT_CTL settle-resolved`.
   - **Ignore** — `$OPEN_POINT_CTL defer-open`.
   - **Skip** — `$OPEN_POINT_CTL skip-open`.
   - **Reject** — `$OPEN_POINT_CTL reject-open`.
5. Apply only the named control for that action.
6. Resolve `$OPEN_POINT_CTL process-context` or `resolve-context` before
   selecting the next open.

If dialogue exposes another open, call `$OPEN_POINT_CTL add-opens`. Append it
to the active batch tail without interrupting the active open; create a normal
batch when none is active.

Re-dispatch process analysis when its substantive inputs change. Never act on
an analysis rejected as stale.

### Batch done

The batch is done only when its registered opens no longer remain open. When
control returns to `idle`, offer:

- detect another batch;
- continue discussion;
- request G3 closure.

Facts do not reset a lens start. `$OPEN_POINT_CTL set-frontier` and
`frontier-skip` are only for a human override of a lens start X, or to
mark a required lens as not blocking `cleared`. Detect gaps go through
`add-opens` measurements. After either command, the previous receipt
is stale; Detect again before `cleared`.

Do not offer a climb / skip / no-climb fork after Detect. Do not start
another detection automatically.

## Close

G3 has two human-confirmed exits:

- **`cleared`** — the latest complete lens detection has zero raw candidates,
  its bound inputs (including the frontier digest) are current, no open
  remains, and every required unskipped lens was measured with no gap.
- **`hard-skip`** — no blocking open remains; non-blocking opens may remain.
  Altitude is not required.

After the human chooses an exit, call
`$INDUCTIVE_GATE_CTL gate-close --gate G3 --mode <cleared|hard-skip> --confirm`
once. Let the control validate the exit. On success, resolve a fresh `$CTX`
and load the gate it names. Do not close G3 through `$OPEN_POINT_CTL`.

## Hard cuts

- Do not overlap Detect and Process dispatches.
