# Write protocol (claim-current + assemble)

Semantic write rules migrated from Init Step 4. Field **sources** follow the
session `context` + thickened `begin` contract; writing **semantics** are
unchanged.

Chapter quality contract: [`../../references/init-draft-quality.md`](../../references/init-draft-quality.md).  
Theory: [`../../references/compose-theory.md`](../../references/compose-theory.md).

## Artifacts

Keep chapter body shell (`_body-{cid}.txt`); Assemble via `assemble-arc`.

**Presentation layers (archive-5.0):** `tree` group → arc leaf → lens chapter
(`cid`). Visible titles stop at group/leaf; lens chapters are anchors + body
(default omit lens heading).

```text
_body-{cid}.txt      # body for one (arc-leaf, lens) chapter; no leading ##
```

Visible group/leaf titles come from the narrative arc via `assemble-arc`.

## Write (4.W)

Serial gate (claim-current): `$CHAPTER_WRITE_STATE` owns which chapter is
current. Do **not** pick chapters from `list-chapters` / `status.next` for
Write.

```bash
$CHAPTER_WRITE_STATE sync --revision-dir "$REVISION_DIR"
```

Loop (claim → write → complete):

```bash
$CHAPTER_WRITE_STATE begin \
  --revision-dir "$REVISION_DIR" \
  --project-root "$PROJECT_ROOT" \
  --profile "$COMPOSE_PROFILE" \
  --cycle-id "$CYCLE_ID"
# → work ticket: chapter_id, leaf_id, leaf_title, lens, fact_ids, facts,
#   writing_cognition, lens_intent
# already_running → stop; complete current first (do not begin again)
# missing_fact_ids → stop; fix arc/_facts.json (chapter not claimed)
# chapter_id null + status=complete → exit loop
```

For **that ticket only** (`chapter_id` / `fact_ids` / `facts` / `lens` /
`writing_cognition` / `lens_intent` from `begin` stdout):

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

```bash
$CHAPTER_WRITE_STATE complete --revision-dir "$REVISION_DIR"
# → next chapter_id (or null); then loop to begin
```

`complete` hard-gates (same rules re-checked at Init Step 5): non-empty
`_body-{cid}.txt`. On `begin`/`complete` failure → stop; fix artifacts or redo
the current chapter; do not skip ahead. Resume: `complete` current if needed,
then `begin` again (never `begin --chapter`).

**Must not:** treat `list-chapters` as the Write todo list; `begin --chapter` /
`complete --chapter` on the main path; Write another chapter while
`already_running`.

**Must not (Write substance source):** use memory (including Step 3 full-store
recall) as Write fact source; Read `_facts.json` (or any out-of-ticket fetch)
for Write; use any substance source other than this round's `begin.facts`.

**Note:** Encourage sectioning in the body. If using heading levels for
structure, headings may start at `####`.

## Assemble (4.A)

**Hard gate:** `$CHAPTER_WRITE_STATE` must be `complete` (enforced by
`assemble-arc` and Init Step 5). Do not assemble mid-loop.

One shot (tree packaging + omit lens headings by default):

```bash
$COMPOSE_DOC_CONTROL assemble-arc \
  --path "$OUTPUT_DOC_PATH" \
  --revision-dir "$REVISION_DIR" \
  --preamble "<same substituted document_preamble as Phase 0>" \
  --lens-heading omit \
  --tree auto
```

(`--preamble-file` OK for multiline. Overwrites `$OUTPUT_DOC_PATH`. Debug:
`--lens-heading show` adds `####` under each anchor.)

**Done:** compose doc has group/leaf visible titles when `tree` present (else
leaf `##`); every listed `cid` has `<!-- chapter:{cid} -->` + non-empty body;
**no** spine titles of the form `{leaf} · {LENS}` or `Context（CTX）` lens
H2/H3.
