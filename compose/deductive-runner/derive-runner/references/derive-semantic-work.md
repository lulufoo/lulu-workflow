# Derive semantic work (Floor · Ceiling · Cascade)

Load from `derive-runner` Execution after Prepare.
Macros: `../SKILL.md`.

Path: Floor → Ceiling. A Ceiling pass that ran `$DERIVE_CTL append` enters
Cascade.

## Floor

Purpose: close graph holes without using KW.

A **Floor round** starts with `$DERIVE_CTL edge-scan` and ends after every
returned lens has been handled. One Floor invocation may run at most **three
rounds**. Cascade re-entry resets the Floor round count.

### Run a round

1. `$DERIVE_CTL edge-scan` → local `edge_holes`.
2. Empty `edge_holes` → Floor is complete; enter Ceiling.
3. For each lens `L` in `edge_holes`:
   - Projectable → write one lens batch (§ Derived batch), using exact upstream
     `F-id` in `origin.ref` (prefer `source`).
   - Not projectable → `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`).
4. Scan again after the round:
   - No holes → Ceiling.
   - Holes remain and fewer than three rounds have run → next Floor round.
   - Holes remain after the third round → use this scan only to record each
     remaining lens with `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`) →
     Ceiling.

## Ceiling

Purpose: thicken every required lens under its published KW criteria.

Walk required lenses in `$VAR_LENS_ORDER`; read `presence` from
`$VAR_SECTION_REGISTRY`. Finish all required lenses before Cascade.

### Process a required lens

1. `$DERIVE_BUILD_CTL lens-bundle --lens L …` → this lens’s `kw_criteria` and
   `facts` (`--help`).
2. Judge whether `facts` satisfy `kw_criteria`.
3. Satisfied → continue to the next required lens.
4. Unsatisfied → apply Means, then re-judge:
   - Derived produced → write one lens batch (§ Derived batch).
   - Means exhausted and still unsatisfied → `$DEDUCTIVE_CTL pending-add`
     (kind=`kw_shortfall`, `--lens L`, summary = table gap).
5. Continue to the next required lens.
6. After all required lenses: no `$DERIVE_CTL append` in this pass → Persist
   validate; one or more → Cascade.

### Means

1. List Intent should-cover / thicken opportunities.
2. Produce derived entries only if all hold: projectable · on `decompose` /
   `instantiate` edge · within table depth.
3. Still thin → recover: carried → quarantined ledger → not_needed ledger →
   pending.
4. Off-edge / undecided → `$DEDUCTIVE_CTL pending-add`
   (kind=`off_edge` \| `undecided`); never `origin.type=derived` off-edge.
5. Do not invent to pad KW with no edge.

## Cascade

After a Ceiling pass appended, `$DERIVE_CTL edge-scan` → local `edge_holes`.

- **No holes:** Persist validate.
- **Holes:** rerun Floor → Ceiling up to **three times**.
- **Holes still remain:** `$DEDUCTIVE_CTL pending-add` (kind=`edge_hole`) for
  each; Persist validate.

## Emit invariants

1. Must not produce `origin.type=discovered`.
2. Do not batch-retag quarantine / not_needed.

## Derived batch

For lens `CTX`, write one temporary `<derived-file>`:

```json
[
  {
    "text": "<projected fact>",
    "lens_tags": ["CTX"],
    "origin": {
      "type": "derived",
      "ref": ["F-7"],
      "derive_mode": "floor"
    },
    "source": ["F-7"]
  }
]
```

- Then `$DERIVE_CTL append --derived-file <derived-file> …`.
- Use one file and one append call per lens batch.
- `derive_mode` is `floor` (Floor) or `ceiling` (Ceiling).
