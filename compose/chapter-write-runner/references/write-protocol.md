# Write protocol

Chapter quality contract: [`../../references/writing-draft-quality.md`](../../references/writing-draft-quality.md).  
Theory: [`../../references/compose-theory.md`](../../references/compose-theory.md).

## Operating Model

Write is a claim-current serial process over narrative-arc chapters.
`$CHAPTER_WRITE_STATE` owns chapter order and the sole current claim; the
writer owns semantic composition for that claim from its ticket. Each claim
must complete before the process advances.

## Prepare

Align write-state to the narrative-arc write units:

```bash
$CHAPTER_WRITE_STATE sync --revision-dir "$REVISION_DIR"
```

## Write

Loop: Begin → Compose → Complete. On non-zero from `begin`/`complete` → stop;
follow the command error.

### Begin

Claim the sole current chapter (no `--chapter`):

```bash
$CHAPTER_WRITE_STATE begin \
  --revision-dir "$REVISION_DIR" \
  --project-root "$PROJECT_ROOT" \
  --cycle-id "$CYCLE_ID"
# → work ticket (stdout)
```

### Compose

1. `lens` = ticket.lens; `facts_ℓ` = ticket.facts (authoritative substance —
   id set must match `fact_ids`; do not expand).
2. Use ticket.`writing_cognition` (`reading_axis`, `presentation`,
   `expression`) — What mechanisms; see `compose-theory.md`. Do **not** fetch
   full `section-form-registry` to “complete” this chapter.
3. Soft attention (not machine-gated): session `context.domain`
   `expression_conventions`, session `context.role` fields, ticket
   `lens_intent` (`intent` / `intent_boundary`), and that cognition's
   `reading_axis` / `presentation` / `expression` while choosing how to write.
4. Write `_body-{cid}.txt` once for this ticket: content ⊆ `facts_ℓ`; carry
   anchors (L6); resolve raw `F-id` citations; mark gaps with
   `> **待决：** …`.

### Complete

```bash
$CHAPTER_WRITE_STATE complete --revision-dir "$REVISION_DIR"
```

If stdout `status` is `complete` → exit the Write loop. Otherwise loop to
Begin for the next claim.

## Assemble

After Write completes, run once:

```bash
$COMPOSE_DOC_CONTROL assemble-arc \
  --path "$OUTPUT_DOC_PATH" \
  --revision-dir "$REVISION_DIR" \
  --preamble "<same substituted document_preamble as Phase 0>" \
  --lens-heading omit \
  --tree auto
```
