# Init Draft Quality

> Referenced by: initializing-runner (Steps 2–6 chapter artifacts, Step 6 validate).  
> Theory: [`compose-theory.md`](compose-theory.md).

## Purpose

Chapter derive + body artifacts make Init synthesis inspectable and gate-able without replacing Round probe. Section-key I2 derive / `_title-display.json` / Partition retired (K3-d).

## Init positioning

| Must | Must not |
|------|----------|
| Operationalize fact substance into readable chapter bodies | Scope-external speculation |
| Mark gaps explicitly (`待决` in body when substance missing) | Decision verbatim paste |
| Produce listed chapters (framework ∩ placement with facts) with non-empty body + `display_title` copied from framework | Empty shell chapters / `section-key:` anchors |
| Preserve each placed fact's `anchors` into its chapter body (§ Anchor fidelity) | Abstract away a discovered fact's anchors (paths / symbols) |

Round still owns formal KW / upstream / intent gap closure.

## Per-chapter artifacts (fact-first)

```text
$REVISION_DIR/_facts.json                 # fact store (Step 2–3)
$REVISION_DIR/_lens-themes.json           # Step 4.A lens themes
$REVISION_DIR/_chapter-framework.json     # Step 4.B chapter topology + H2 titles
$REVISION_DIR/_chapter-placement.json     # Step 4.C placement SoT (fid → chapter × FL); Step 6 reads this
$REVISION_DIR/_derive-{cid}.json          # Step 5.A (display_title copy + lens_forms)
$REVISION_DIR/_body-{cid}.txt             # Step 5.A assembled chapter body
$OUTPUT_DOC_PATH                          # assembled via append-chapter (<!-- chapter:{cid} -->)
```

`cid` is the chapter id from `_chapter-framework.json` / placement (not a registry section key).

## `_derive-{cid}.json` (chapter)

| Field | Required | Rules |
|-------|----------|-------|
| `display_title` | yes | **Copy** from `_chapter-framework.json` for this `cid`; do not invent at Write; `（待补）` when framework says so |
| `lens_forms` | yes | One entry per FL/`form_lens` in the chapter; F then C before that FL's body (Step 5.W) |
| other fields | per runner | Validator hard-gates non-empty `display_title` on every rendered chapter |

### Display title

**SoT:** `_chapter-framework.json` `chapters[].display_title` for that `cid`.  
`_derive-{cid}.json.display_title` is a **copy** for `append-chapter` (not an independent title authority).

`$COMPOSE_DOC_CONTROL append-chapter` reads derive `display_title` and renders `## {display_title}` under `<!-- chapter:{cid} -->`. Step 6 requires derive title **≡** framework title.

1. Concise reader-facing H2 — optionally one theme phrase. Keep it short.
2. Must not paste a full body / substance sentence.
3. Must not contain raw code tokens (file paths, API / symbol names, file extensions).
4. Empty substance → `（待补）` (same string in framework and derive).
5. FreeEdit Tier A: change the H2 by editing framework `display_title` **and** the derive copy (or edit framework then re-copy into derive before rebuild).

### Body

- Non-drop chapters: non-empty `_body-{cid}.txt` and non-empty chapter segment in the compose doc (after stripping the rendered `##` heading).
- Scope / fact gaps → honest `待决` in body; do not invent fill.

## Body prohibitions

- `[Source:` (decision paste marker)
- `decision-doc-mapping`
- `<!-- section-key:… -->` anchors

## Anchor fidelity (L6)

A fact's `anchors` (§1.5 of `compose-theory.md`) are born-with substance and must survive into the chapter body. Write-by-FL (5.W) contract for each listed chapter:

```text
propositions ⊆ semantic(facts.text)          # existing: invent no propositions
AND
anchors(chapter) ⊆ tokens(body)              # new: keep this chapter's facts' anchors
```

`init_compose_validation.py` enforces the second line mechanically for `discovered` facts (anchor-coverage check; `code_ref` matches OR over its `path`/`symbol` segments). To avoid friendly fire, keep these distinctions:

1. "No verbatim" forbids whole-decision paste and `[Source:]` markers — it does **not** forbid retaining an `anchor.value` (a path / symbol) in prose.
2. `display_title` still forbids raw code tokens — a title is not the body.
3. A "no path pile-up in the opening" convention (where a lens defines one) stays scoped to that opening; it must not be widened into a whole-body ban on paths for structural / contract lenses.
4. Do not replace a registered anchor with a hypernym (e.g. "the task dir" for `tasks/{id}/attachments/`); the concrete token must appear.

## Validate command

`init_compose_validation.py validate` runs: `_facts.json` + themes/framework/placement SoT, placement gates, chapter derive/body files, chapter anchors in the compose doc, and L6 fact-anchor coverage. Presence of `_chapters.json` is an error (retired). See script `--help` for exit codes and stderr format.

## Minimal example (one chapter, one FL)

`_lens-themes.json`:

```json
{
  "version": "1",
  "lens_themes": [
    {
      "form_lens_id": "FL-0",
      "lens_key": "AR",
      "theme": "Architecture theme",
      "desc": "Clustering signal for architecture facts."
    }
  ]
}
```

`_chapter-framework.json`:

```json
{
  "version": "1",
  "chapters": [
    {
      "id": "chap-1",
      "display_title": "架构",
      "anchor_form_lens_ids": ["FL-0"],
      "sections": [{ "form_lens_id": "FL-0", "heading": "Architecture theme" }]
    }
  ]
}
```

`_chapter-placement.json`:

```json
{
  "version": "1",
  "$schema_id": "chapter-placement",
  "chapters": [
    {
      "id": "chap-1",
      "facts": [
        { "fid": "F-1", "form_lens_id": "FL-0", "placement": "mechanical" }
      ]
    }
  ]
}
```

`_derive-chap-1.json` (display_title **copy** of framework):

```json
{ "display_title": "架构", "lens_forms": [] }
```
