# Derive semantic work (Floor · Ceiling · Cascade)

Load from `derive-runner` Execution after Prepare.
Macros: `../SKILL.md`.

Path: Floor → Ceiling → Cascade. Cascade is the only persist exit.

## Floor

Purpose: close graph holes without using KW.

A **Floor round** starts with `$DERIVE_CTL edge-scan` and ends after every
returned lens has been handled. One Floor invocation may run at most **three
rounds**. Cascade re-entry resets the Floor round count. Floor does not write
pending.

### Run a round

1. `$DERIVE_CTL edge-scan` → local `edge_holes`.
2. Empty `edge_holes` → Floor is complete; enter Ceiling.
3. For each lens `L` in `edge_holes`:
  - Projectable → write one lens batch (§ Derived batch), using exact upstream
   `F-id` in `origin.ref` (prefer `source`).
  - Not projectable → skip this lens.
4. Scan again after the round:
  - No holes or third-round leftover → Ceiling.
  - Holes remain, under three rounds → next Floor round.

## Ceiling

Purpose: one KW thicken pass per required lens.

Walk required lenses in `$VAR_LENS_ORDER` (`presence` from
`$VAR_SECTION_REGISTRY`).

1. `$DERIVE_BUILD lens-bundle --lens L …` → `kw_criteria` and `facts`
   (`--help`).
2. Satisfied → next lens.
3. Unsatisfied → one compensate: project only if projectable · on
   `decompose` / `instantiate` · within table depth. Derived → one lens batch
   (§ Derived batch). Otherwise skip.
4. After the walk: Cascade.

## Cascade

After every Ceiling pass, `$DERIVE_CTL edge-scan` → local `edge_holes`.

- **No holes:** Persist validate.
- **Holes** and under three reruns: Floor → Ceiling.
- **Otherwise:** `$DEDUCTIVE_CTL pending-replace` from this scan's
  `edge_holes` (`--help`) → Persist validate.

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
