# Delivery contract (chapter write + assemble)

Single delivery path for callers.

## Preconditions

- Do **not** Read `_facts.json` for Write substance.
- Do **not** accept `$CODE_GROUNDING` or `$SCOPE_REF_PATH` as Input.

## Phase 0 — Context and init-doc

1. `$CHAPTER_WRITE_BUILD context --revision-dir … --project-root …
   --cycle-id …` → capture `role`, `domain`, `document_preamble`.
2. `$COMPOSE_DOC_CONTROL init-doc --path "$OUTPUT_DOC_PATH" --preamble …`
   (or `--preamble-file`).

## Phase 1 — Write and assemble

Follow `references/write-protocol.md` from Prepare through Assemble.

## Summary (return exactly)

```text
status: done|failed
output_doc_path: <OUTPUT_DOC_PATH>
arc_path: <ARC_PATH>
wrote_bodies: true|false
assembled: true|false
write_state: complete|<other>
error: <empty or message>
```

## DONE / failure

- **DONE:** `wrote_bodies=true` · `assembled=true` · `write_state=complete`.
- **FAIL:** any phase incomplete.
