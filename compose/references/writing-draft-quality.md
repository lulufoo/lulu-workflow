# Writing Draft Quality

> Referenced by: writing-runner (chapter artifacts + package validate).  
> Theory: [`compose-theory.md`](compose-theory.md).

## Purpose

Chapter body artifacts make Writing synthesis inspectable and gate-able without replacing Round probe. Section-key I2 derive / `_title-display.json` / Partition retired (K3-d).

**Narrative-arc Writing (archive-5.0):** visible titles come from `_narrative-arc.json` + `assemble-arc`. Archive-3.0 themes/framework/placement files are **retired** (presence is a Writing validation error).

## Writing positioning

| Must | Must not |
|------|----------|
| Operationalize fact substance into readable chapter bodies | Scope-external speculation |
| Mark gaps explicitly (`待决` in body when substance missing) | Decision verbatim paste |
| Produce listed write units with non-empty body (`list-chapters` cids) | Empty shell chapters / `section-key:` anchors |
| Preserve each placed fact's `anchors` into its chapter body (§ Anchor fidelity) | Abstract away a discovered fact's anchors (paths / symbols) |
| Load lens writing cognition as Write input (What) | Invent beyond ticket facts; empty shell chapters |

Round still owns formal KW / upstream / intent gap closure.

## Per-chapter artifacts (fact-first)

```text
$REVISION_DIR/_facts.json                 # fact store (Step 2–3)
$REVISION_DIR/_narrative-arc.json         # Writing spine (archive-5.0)
$REVISION_DIR/_chapter-write-state.json   # serial 4.W gate
$REVISION_DIR/_body-{cid}.txt             # chapter body (hard gate: non-empty)
$OUTPUT_DOC_PATH                          # assembled via assemble-arc (tree/leaf titles + <!-- chapter:{cid} -->)
```

`cid` = `{leaf_id}-{lens}` from `_narrative-arc.json` / `list-chapters`.

## Writing cognition (What)

Use per-lens **writing cognition** from each chapter's `$CHAPTER_WRITE_STATE begin`
ticket (`writing_cognition`); do not re-fetch full `section-form-registry` for Write.

| Field | Role |
|-------|------|
| `reading_axis` | Abstract narrative axis (key required; empty string temporarily allowed) |
| `presentation.allowed[]` + `when` | Optional carriers and when to use them |
| `presentation.forbidden` | Excluded carriers/structures |
| `expression` | Manner-of-expression attention (not a persisted chapter C array) |

Selection among `allowed` is soft How; Writing does not hard-gate a chosen carrier/structure (F) artifact.

### Titles (narrative-arc)

`$COMPOSE_DOC_CONTROL assemble-arc` builds group/leaf visible titles from `_narrative-arc.json` and emits lens chapters as anchors + body (`--lens-heading omit` default).

### Body

- Non-drop chapters: non-empty `_body-{cid}.txt` and non-empty chapter segment in the compose doc (after stripping optional `##` / `####` heading lines).
- Scope / fact gaps → honest `待决` in body; do not invent fill.

## Body prohibitions

- `[Source:` (decision paste marker)
- `decision-doc-mapping`
- `<!-- section-key:… -->` anchors

## Anchor fidelity (L6)

A fact's `anchors` (§1.5 of `compose-theory.md`) are born-with substance and must survive into the chapter body. Write contract for each listed chapter:

```text
propositions ⊆ semantic(facts.text)          # existing: invent no propositions
AND
anchors(chapter) ⊆ tokens(body)              # new: keep this chapter's facts' anchors
```

`writing_compose_validation.py` enforces the second line mechanically for `discovered` facts (anchor-coverage check; `code_ref` matches OR over its `path`/`symbol` segments). To avoid friendly fire, keep these distinctions:

1. "No verbatim" forbids whole-decision paste and `[Source:]` markers — it does **not** forbid retaining an `anchor.value` (a path / symbol) in prose.
2. A "no path pile-up in the opening" convention (where a lens defines one) stays scoped to that opening; it must not be widened into a whole-body ban on paths for structural / contract lenses.
3. Do not replace a registered anchor with a hypernym (e.g. "the task dir" for `tasks/{id}/attachments/`); the concrete token must appear.

## Validate command

`writing_compose_validation.py validate` runs: `_facts.json` + `_narrative-arc.json` + chapter write-state `complete`, per-chapter non-empty body gate (same as `$CHAPTER_WRITE_STATE complete`), chapter anchors in the compose doc, and L6 fact-anchor coverage. Presence of `_chapters.json` / `_lens-themes.json` / `_chapter-framework.json` / `_chapter-placement.json` is an error (retired). See script `--help` for exit codes and stderr format.

## Minimal example (one chapter)

`_narrative-arc.json` (shape abbreviated):

```json
{
  "version": "1",
  "kind": "narrative-arc",
  "status": "write_ready",
  "leaves": [
    {
      "id": "A01",
      "title": "Architecture leaf",
      "fact_ids": ["F-1"],
      "chapters": [{ "lens": "AR", "fact_ids": ["F-1"] }]
    }
  ]
}
```

`_body-A01-AR.txt`:

```text
Architecture claim grounded in F-1 anchors…
```
