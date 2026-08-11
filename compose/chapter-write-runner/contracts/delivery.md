# Delivery contract (chapter write + assemble)

Single delivery path for callers. Load only after
`references/write-protocol.md`.

## Preconditions

- Input bound: `REVISION_DIR`, `PROJECT_ROOT`, `COMPOSE_PROFILE`, `CYCLE_ID`,
  `OUTPUT_DOC_PATH`, `ARC_PATH`.
- **This wave:** `ARC_PATH` **must** be `_narrative-arc.json`. Controls use the
  default basename only (no alternate `--arc-path` yet).
- Arc at that path is `status=write_ready` (same precondition as Writing Step 4).
- Do **not** paste fact bodies in the caller prompt — substance only via
  `$CHAPTER_WRITE_STATE begin`.

## Phase 0 — Session context + doc shell

1. `$CHAPTER_WRITE_BUILD_CTL context --revision-dir … --project-root …
   --profile … --cycle-id …` → capture `role`, `domain`, `document_preamble`.
2. If context reports residual `{Feature Name}` / `{Topic Name}` placeholders,
   finish them from cycle/topic knowledge before `init-doc`.
3. `$COMPOSE_DOC_CONTROL init-doc --path "$OUTPUT_DOC_PATH" --preamble …`
   (or `--preamble-file`). Prefer the same substituted preamble later for
   `assemble-arc`.

## Phase 1 — Write-by-sub-topic-chapter (4.W)

Follow `references/write-protocol.md` § Write. Soft attention uses session
`context.role` / `context.domain` and each ticket's `writing_cognition` /
`lens_intent`.

## Phase 2 — Assemble-from-arc (4.A)

Follow `references/write-protocol.md` § Assemble. Hard gate: write-state
`complete`.

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
- **FAIL:** any phase incomplete — do not claim assemble success mid-loop.
