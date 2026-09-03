# Write protocol

Chapter body contract: [`chapter-body-contract.md`](chapter-body-contract.md).  
Cognition: `../SKILL.md` § Cognition.

## Operating Model

Write is a claim-current serial process over narrative-arc chapters.
`$CHAPTER_WRITE_STATE` owns chapter order and the sole current claim; the
writer owns semantic composition for that claim from its ticket.

## Prepare

```bash
$CHAPTER_WRITE_STATE sync --revision-dir "$REVISION_DIR"
```

## Write

Loop: Begin → Compose → Complete. On non-zero from `begin`/`complete` → stop;
follow the command error. If stdout `status` is `complete` → exit the Write
loop; otherwise next Begin.

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
   `expression`) — What mechanisms; see `writing-cognition.md`.
3. Soft attention (not machine-gated) while choosing how to write:
   - session `context.domain`
   - session `context.role`
   - ticket `lens_intent` (`intent` / `intent_boundary`)
4. Write `_body-{cid}.txt` once for this ticket: content ⊆ `facts_ℓ`; carry
   anchors (L6); resolve raw `F-id` citations; mark gaps with
   `> **待决：** …`.

### Complete

```bash
$CHAPTER_WRITE_STATE complete --revision-dir "$REVISION_DIR"
```

## Assemble

```bash
$COMPOSE_DOC_CONTROL assemble-arc \
  --path "$OUTPUT_DOC_PATH" \
  --revision-dir "$REVISION_DIR" \
  --preamble "<same substituted document_preamble as Phase 0>" \
  --lens-heading omit \
  --tree auto
```
