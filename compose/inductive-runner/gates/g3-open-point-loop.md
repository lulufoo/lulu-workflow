> Part of inductive-runner · loaded only when `$CTX.active_gate` is `G3`

# Gate 3 — Open-point Loop

## Goal

Expose and dispose unresolved questions that matter to the current slice after
the Topic Loop. Complete when the human closes G3 through a validated exit.

## Script Macros

| Macro | Command |
|---|---|
| `$INDUCTIVE_GATE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_gate_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |
| `$OPEN_POINT_CTL` | `python3 "$SKILL_ROOT/compose/scripts/inductive/open-point/open_point_control.py" --out-dir "$INDUCTIVE_OUT_DIR"` |

Use each control's `--help` as the command and stdout contract.

## Principles

1. The human starts Detect, disposes each registered Open, and chooses
   whether to close. The Parent Agent may recommend. It never
   substitutes Land, Ignore, Skip, or Reject.
2. Discussion remains available beside Detect and Process; it is not a
   third control state.
3. Process one group at a time: the open Opens of the active batch that
   share the active Open's lens. Never overlap Detect and Process
   dispatches.
4. Route only from control stdout or `$OPEN_POINT_CTL resolve-context`.
   Do not read session data files.
5. Registry status: `open` unresolved; `settled` landed in facts;
   `deferred` not landed now; `rejected` false or outside the slice.
   Skip keeps `open`.

## Routing

Detect analyzes one human-started candidate batch and reports every
remaining unmet KW row of each pending lens in that pass. Process
analyzes one active Open group; the Parent Agent applies its human-selected
disposition. Entry and `idle` never start Detect automatically.

### Detect

After an explicit human Detect request from `idle`:

1. `$OPEN_POINT_CTL ensure-frontier`.
2. Dispatch `../open-point-detect-runner/SKILL.md`. The dispatch
   prompt carries the invoke argument `--out-dir`
   only — no contract or return-shape restatement. The runner fetches
   `$OPEN_POINT_CTL detect-context`, then `detect-lens-context` per
   `pending_lenses` key. Parent does not.
3. Review the candidates with the human, then call
   `$OPEN_POINT_CTL add-opens --opens-json --detect-json`. Contract in
   `--help`.
4. Route from its stdout: a registered batch → Process; otherwise
   `idle`.

### Process

Call `$OPEN_POINT_CTL process-context`. When it names the active group:

1. Dispatch `../open-point-process-runner/SKILL.md` once for the whole
   group with the `process-context` stdout only. Do not prescribe how the
   runner investigates.
2. Present the runner return for every Open of the group. Route each
   entry's `status`:
   - **`blocked`** — present the reason; that Open gets no disposition.
     Recover input and re-dispatch; otherwise it waits.
   - **`open`** — present its analysis for disposition.
3. Wait for one human reply that names an action for each `open` entry.
   Absent a per-Open override, one action covers the whole group:
   - **Land** — declare `fact-store-runner` `settle_open` once for all
     Opens being landed, with the Land ids and Process results.
   - **Ignore** — `$OPEN_POINT_CTL defer-open` per Open.
   - **Skip** — `$OPEN_POINT_CTL skip-open` for the Opens skipped.
   - **Reject** — `$OPEN_POINT_CTL reject-open` per Open.
4. Apply only the named controls for those actions. Close Ignore and
   Reject Opens before Land so the Land permit sees the final batch.
5. Resolve `$OPEN_POINT_CTL process-context` or `resolve-context` before
   selecting the next group.
6. Dialogue exposes another Open → `$OPEN_POINT_CTL add-opens`. Append
   to the active batch tail; create a batch when none is active.
7. Re-dispatch when substantive inputs change.

### Idle

After control returns to `idle` (registered Opens no longer remain
open):

1. Offer another Detect, continued discussion, or a G3 closure request.
2. On a human request to override a lens start X or exempt a required
   lens from blocking `cleared`, call `$OPEN_POINT_CTL set-frontier` or
   `frontier-skip`; then Detect again before `cleared`. Details in
   `--help`.
3. Do not start another detection automatically.

### Close

After the human chooses `cleared` or `hard-skip`, call
`$INDUCTIVE_GATE_CTL gate-close --gate G3 --mode <cleared|hard-skip> --confirm`
once for that confirmed choice. The control validates the exit. On rejection,
report the reason and remain in G3. On success, resolve a fresh `$CTX`. When
`active_gate` is `complete`, return to the parent. Do not load another gate.

## Boundaries

| Owner | Owns |
|---|---|
| `../open-point-detect-runner/SKILL.md` | Full-lens batch analysis |
| `../open-point-process-runner/SKILL.md` | Analysis of one active Open group |
| `fact-store-runner` | Fact landing through its public protocol |
| `$OPEN_POINT_CTL` | Open, batch, receipt, and loop transitions |
| `$INDUCTIVE_GATE_CTL` | G3 closure |

- Sub-agents do not interact with the human or mutate session state.
- On dispatch timeout, exception, or invalid output, record no runner
  result. Report, or retry while the relevant control context remains
  current.
- Do not close G3 through `$OPEN_POINT_CTL`.
- Do not paste Detect measurement, Process analysis, `--detect-json`
  fields, or close predicates into this gate.
