# Delivery contract (unified)

Single delivery path for all callers. Load only after
`references/semantic-build-protocol.md`.

## Preconditions

- Input bound: `REVISION_DIR`, `PROJECT_ROOT`, `CYCLE_ID`,
  `OUTPUT_PATH`, `MOUNT` (`true`|`false`; default `false` if omitted).
- Semantic build protocol completed for the current phase candidate.
- Do **not** paste fact bodies in the caller prompt — use `context`.

## Phase 1 — `status=mapped`

1. Author a `kind=narrative-arc` candidate with `status=mapped` (tree + leaf
   `fact_ids`; no chapters required).
2. Run pre-persist self-check (protocol step 5).
3. `$NARRATIVE_ARC_BUILD_CTL validate-candidate --revision-dir … --file <candidate>`
   → capture `digest`.
4. `$NARRATIVE_ARC_CTL write --revision-dir … --project-root …
   --file <candidate> --output-path "$OUTPUT_PATH" --digest <digest>`
5. On failure: do not claim write; rebuild candidate; do not run a follow-up
   `validate` solely because write succeeded.

## Phase 2 — `status=write_ready`

1. Partition each leaf into chapters `{lens, fact_ids}`. Every leaf fact in
   exactly one chapter; each chapter `lens` ∈ that fact's `lens_tags`; empty
   tags / non-empty `unresolved` block `write_ready`.
2. Self-check + `validate-candidate` → `digest`.
3. `$NARRATIVE_ARC_CTL write … --file <candidate> --output-path "$OUTPUT_PATH"
   --digest <digest> --require-write-ready`
4. Delete temporary transport candidate file after successful write.

## Mount (optional)

When `MOUNT=true`:

```bash
$COMPOSE_VIEWER_CTL mount \
  --revision-dir "$REVISION_DIR" \
  --arc-file "$OUTPUT_PATH"
```

- Mount requires on-disk arc at `OUTPUT_PATH` with unified schema and
  `status=write_ready` (enforced by mount control).
- Do **not** change Viewer HTML in this contract.
- When `MOUNT=false`: skip mount; Summary `mounted=false`, `viewer_url` empty.

## Summary (return exactly)

```text
status: done|failed
output_path: <OUTPUT_PATH>
wrote: true|false
write_ready: true|false
mounted: true|false
viewer_url: <url or empty>
error: <empty or message>
```

## DONE / failure

- **DONE:** `wrote=true` · `write_ready=true` · (`MOUNT=false` **or**
  (`mounted=true` · non-empty `viewer_url`)).
- **Partial:** `wrote=true` · `write_ready=true` · `MOUNT=true` ·
  `mounted=false` — arc on disk; do not claim Viewer updated.
- **FAIL:** `wrote=false` — prior file at `OUTPUT_PATH` unchanged (backup kept
  only after a successful overwrite attempt's pre-backup; failed digest/validate
  leaves existing file untouched).
