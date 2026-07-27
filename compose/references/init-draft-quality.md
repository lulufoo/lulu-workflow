# Init Draft Quality

> Referenced by: initializing-runner (Steps 2–6 chapter artifacts, Step 6 validate).  
> Theory: [`compose-theory.md`](compose-theory.md).

## Purpose

Chapter derive + body artifacts make Init synthesis inspectable and gate-able without replacing Round probe. Section-key I2 derive / `_title-display.json` / Partition retired (K3-d).

**Narrative-arc Init (archive-5.0):** visible titles come from `_narrative-arc.json` + `assemble-arc`. Derive **must not** carry spine titles; derive `display_title` is **retired** (ignored by validators). Archive-3.0 themes/framework/placement files are **retired** (presence is an Init validation error).

## Init positioning

| Must | Must not |
|------|----------|
| Operationalize fact substance into readable chapter bodies | Scope-external speculation |
| Mark gaps explicitly (`待决` in body when substance missing) | Decision verbatim paste |
| Produce listed write units with non-empty body (`list-chapters` cids) | Empty shell chapters / `section-key:` anchors / rely on derive `display_title` for titles |
| Preserve each placed fact's `anchors` into its chapter body (§ Anchor fidelity) | Abstract away a discovered fact's anchors (paths / symbols) |

Round still owns formal KW / upstream / intent gap closure.

## Per-chapter artifacts (fact-first)

```text
$REVISION_DIR/_facts.json                 # fact store (Step 2–3)
$REVISION_DIR/_narrative-arc.json         # Init spine (archive-5.0)
$REVISION_DIR/_chapter-write-state.json   # serial 4.W gate
$REVISION_DIR/_derive-{cid}.json          # Write metadata (lens + F/C); not spine titles
$REVISION_DIR/_body-{cid}.txt             # chapter body
$OUTPUT_DOC_PATH                          # assembled via assemble-arc (tree/leaf titles + <!-- chapter:{cid} -->)
```

`cid` = `{leaf_id}-{lens}` from `_narrative-arc.json` / `list-chapters`.

## `_derive-{cid}.json` (chapter)

| Field | Required | Rules |
|-------|----------|-------|
| `display_title` | **no** (retired) | Ignored by Init validators; do not write for narrative-arc Init |
| `lens` | yes (contract) | Unit lens key |
| `form.carrier` / `form.structure` | **yes** (hard gate) | Non-empty strings; gated by `complete` + Step 5 |
| `expression` | **yes** (hard gate) | Chapter C array (derive field — not lens registry `expression`). Pre-Write planning checklist (not post-hoc proof). Non-empty string array; joined text must contain `expression_conventions.register` / `.carriers` / `.scannability` / `.altitude`. Prefer `from expression_conventions.<key>: …` executable rules; fluency from `.scannability`. `expression_c` is retired |

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

`init_compose_validation.py` enforces the second line mechanically for `discovered` facts (anchor-coverage check; `code_ref` matches OR over its `path`/`symbol` segments). To avoid friendly fire, keep these distinctions:

1. "No verbatim" forbids whole-decision paste and `[Source:]` markers — it does **not** forbid retaining an `anchor.value` (a path / symbol) in prose.
2. A "no path pile-up in the opening" convention (where a lens defines one) stays scoped to that opening; it must not be widened into a whole-body ban on paths for structural / contract lenses.
3. Do not replace a registered anchor with a hypernym (e.g. "the task dir" for `tasks/{id}/attachments/`); the concrete token must appear.

## Validate command

`init_compose_validation.py validate` runs: `_facts.json` + `_narrative-arc.json` + chapter write-state `complete`, per-chapter F/C + `expression_conventions.*` provenance gate (same as `$CHAPTER_WRITE_STATE complete`), chapter anchors in the compose doc, and L6 fact-anchor coverage. Does **not** gate derive `display_title`. Presence of `_chapters.json` / `_lens-themes.json` / `_chapter-framework.json` / `_chapter-placement.json` is an error (retired). See script `--help` for exit codes and stderr format.

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

`_derive-A01-AR.json` (no spine title):

```json
{
  "lens": "AR",
  "form": { "carrier": "prose", "structure": "claim-then-evidence" },
  "expression": [
    "from expression_conventions.register: …",
    "from expression_conventions.carriers: …",
    "from expression_conventions.scannability: …",
    "from expression_conventions.altitude: …"
  ]
}
```
