# Pending Confirm

Close post-Derive pending with the user. Preserve resolved items; rerun full
intake only after upstream material is replaced.

## 1. Settle Unreferenced Quarantine

List quarantined facts not cited by another fact:

```bash
$DEDUCTIVE_CTL quarantine-unref
```

For each returned id, ask the user to choose one exit:

- **Use the fact** (either path removes it from the unreferenced list):
  - **Cite:** another fact references this id.
  - **Promote:** apply `$DEDUCTIVE_CTL disposition-patch-*` with allowed
    `lens_tags` so it becomes `carried`. Then `$FACTS_CTL strip-derived
    --revision-dir "$DEDUCTIVE_OUT_DIR"` and rerun Derive (parent Step 2).
- **Leave it quarantined:** add a pending item with `kind=quarantine_unref` and
  `upstream_ref=<fact-id>`, then resolve it as `resolved`, `escalated`, or
  `out_of_scope`.

## 2. Resolve Open Pending

Present every open derivation gap, quarantine item, and `kw_shortfall`. For each
item, offer only options traceable to decided material, plus `insufficient`.

- **Local seed (default):** append a fact with `origin.type=seed` and a Confirm
  ref via `$DERIVE_CTL append`, or use `$FACTS_CTL write` with the full array per
  `--help`; then `$FACTS_CTL strip-derived --revision-dir "$DEDUCTIVE_OUT_DIR"`
  and rerun Derive (parent Step 2) before `$DEDUCTIVE_CTL pending-resolve`.
- **Escalate upstream:** resolve the item as deferred or escalated without
  inventing local substance.
- **Accept `kw_shortfall` (soft gate):** show the lens's KW table gap and ask the
  user explicitly. On acceptance, run `$DEDUCTIVE_CTL pending-resolve --status
  resolved` and record `accept-shortfall` in the return summary or conversation.

`$DEDUCTIVE_CTL pending-resolve` preserves incremental settlement; resolved ids
must not reappear.

## 3. Pass the Gate

```bash
$DEDUCTIVE_CTL gate-check
```

Exit 0 requires:

1. the pending store exists;
2. no pending item remains open, including `kw_shortfall`;
3. every unreferenced quarantined fact is settled through a
   `quarantine_unref` pending item as resolved, escalated, or out of scope.

A new fact citing a quarantined id also clears its unreferenced accounting.

**Done:** return to Step 4.
