---
name: derive-runner
description: >-
  Compose deductive L1: Pd floor means + ceiling × KW ruler after fact-intake.
---

# derive-runner

Run Pd on intake-classified facts: edge-closure floor means and Intent ceiling
means under the published KW ruler. Finish when validate passes and every floor
hole / required lens is covered or pending.

## Boundaries

**Must:** bind Input; `$DERIVE_BUILD_CTL context` (requires `eval_status=done`);
`$DERIVE_CTL plan-edge` → floor / ceiling×KW (cascade in this run) →
`$DERIVE_CTL append` → `$FACTS_CTL validate`; `$DEDUCTIVE_CTL pending-add` for
gaps.  
**Must not:** Fact Intake / cut / eval / disposition / confirm; Pending Confirm
human gate; disposition-patch / promote; `$FETCH_COMPOSE` or paste framework
templates; `$SOURCE_PATH` / re-read upstream prose; write chapter prose;
`origin.type=discovered`; invent to pad KW with no edge; reuse intake Confirm
patch; cite `docs/**`.

## Input

```text
REVISION_DIR: <revision or focus-L dir>
PROJECT_ROOT: <abs project root>
COMPOSE_PROFILE: <profile id>
CYCLE_ID: <cycle id>
```

## Script Macros

| Macro | Command |
|-------|---------|
| `$DERIVE_BUILD_CTL` | `python3 "$SKILL_ROOT/compose/deductive-runner/derive-runner/scripts/derive_build_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` |
| `$DEDUCTIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/deductive/deductive_control.py" --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |

Build: `--help` · `context`.  
Derive / deductive / facts: see each `--help`. Scripts never invent derived
work-item text.

## Cognitive map

**Floor** = edge-closure **means** (no KW).  
**Ceiling** = Intent projection **means** driven by published **`KW_CRITERIA`** as
the **only thickness ruler**. Do **not** treat “edges closed” or “should-cover
ticked” as “thick enough.” Do **not** run a separate KW-first pass on the intake
pool.  
**Do not** batch-retag quarantine/not_needed inside Pd.

## Execution

1. **Context** — `$DERIVE_BUILD_CTL context --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"`. Use stdout projection (`section_order`, `section_registry`, `section_kw_criteria` as **`KW_CRITERIA`** ruler). Do **not** `$FETCH_COMPOSE` or paste templates.
2. **Plan-edge** — Mechanical plan first (edge floor + topo). **`$DERIVE_CTL plan-edge` hard-fails** unless intake eval `eval_status` is `done`.

```bash
$DERIVE_CTL plan-edge \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Use stdout: `order`, `edge_holes`, `true_gaps`, `materials_total` (carried-primary pool).

3. **Floor (means only — no KW)** — for each hole in `edge_holes`: if projectable from decided substance → emit derived fact `{text, lens_tags:[L], origin:{type:derived, ref:[upstream F-id, …]}, source?}` with **exact** upstream `F-id` in `origin.ref` (and prefer `source`). If not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`). KW upper/target does **not** apply here.
4. **Ceiling × KW ruler** — for each required lens in topo order (same `order`, then any remaining required):
   - Materials: **carried** (and legacy no-disposition) + Intent — **not** default `quarantined`/`not_needed` pool.
   - Ruler: that lens’s block in `KW_CRITERIA` (published table only; **no** separate target-thickness number).
   - Estimate whether current facts satisfy the table’s “can state…” rows (agent semantic judgment).
   - **If unsatisfied** → drive ceiling means: list Intent should-cover / thicken opportunities; projectable **and** on a `decompose`/`instantiate` edge **and** not past the depth the table asks for → `derived` with `F-id` refs. Gap recovery when still thin: carried → quarantined ledger → not_needed ledger → pending. Off-edge / undecided → `$DEDUCTIVE_CTL pending-add` (kind=`off_edge` \| `undecided`) — **never** `origin.type=derived` off-edge. **Forbidden:** inventing to pad KW with no edge.
   - **If satisfied** → stop thickening that lens (KW stop line).
   - **If means exhausted and still unsatisfied** → `$DEDUCTIVE_CTL pending-add` (kind=`kw_shortfall`, `--lens <L>`, summary = table gap). Do **not** silently pass.
5. **Cascade:** later lenses see facts appended earlier. If ceiling appends create new `edge_holes`, re-run floor for those holes (**still no KW**), then resume ceiling×KW for affected lenses. Complete cascade in this subagent run (parent does not re-dispatch mid-cascade).
6. **Must not** produce `origin.type=discovered`.
7. **Persist** — when you have a derived batch:

```bash
$DERIVE_CTL append \
  --revision-dir "$REVISION_DIR" \
  --derived-file "<path to derived.json>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

```bash
$FACTS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"
```

## Done

validate exit 0; every floor hole covered or pending; every required lens either
KW-satisfied or has open `kw_shortfall` / other pending.

## Summary

```text
Derive complete.
  Facts: <path>
  Pending gaps: <n open>
  Status: ok
```
