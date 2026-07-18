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
| Produce non-drop chapters with non-empty body + `display_title` | Empty shell chapters / `section-key:` anchors |
| Preserve each placed fact's `anchors` into its chapter body (§ Anchor fidelity) | Abstract away a discovered fact's anchors (paths / symbols) |

Round still owns formal KW / upstream / intent gap closure.

## Per-chapter artifacts (fact-first)

```text
$REVISION_DIR/_facts.json              # fact store (Step 2; K2 projects inductive decisions[])
$REVISION_DIR/_chapters.json           # chapter plan (Step 4)
$REVISION_DIR/_derive-{cid}.json       # Step 5 chapter derive (display_title, …)
$REVISION_DIR/_body-{cid}.txt          # Step 5 chapter body
$OUTPUT_DOC_PATH                       # assembled via append-chapter (<!-- chapter:{cid} -->)
```

`cid` is the chapter id from `_chapters.json` (not a registry section key).

## `_derive-{cid}.json` (chapter)

| Field | Required | Rules |
|-------|----------|-------|
| `display_title` | yes | Reader H2 under the chapter anchor; concise localized string, no code tokens; `（待补）` when substance missing |
| other fields | per runner | As authored in Step 5; validator hard-gates non-empty `display_title` on every non-drop chapter |

### Display title

`$COMPOSE_DOC_CONTROL append-chapter` reads `display_title` and renders `## {display_title}` under `<!-- chapter:{cid} -->`.

1. Concise reader-facing H2 — optionally one theme phrase. Keep it short.
2. Must not paste a full body / substance sentence.
3. Must not contain raw code tokens (file paths, API / symbol names, file extensions).
4. Empty substance → `（待补）`.
5. Derive `display_title` is the single SoT for the rendered chapter H2.

### Body

- Non-drop chapters: non-empty `_body-{cid}.txt` and non-empty chapter segment in the compose doc (after stripping the rendered `##` heading).
- Scope / fact gaps → honest `待决` in body; do not invent fill.

## Body prohibitions

- `[Source:` (decision paste marker)
- `decision-doc-mapping`
- `<!-- section-key:… -->` anchors

## Anchor fidelity (L6)

A fact's `anchors` (§1.5 of `compose-theory.md`) are born-with substance and must survive into the chapter body. Weave contract for each non-drop chapter:

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

`init_compose_validation.py validate` always runs the display-layer suite: candidates-shaped outline pairing, `_facts.json` / `_chapters.json`, placement/coverage gates, chapter derive/body files, chapter anchors in the compose doc, and fact-anchor coverage (L6: every `discovered` fact's anchors present in its chapter body). See script `--help` for exit codes and stderr format.
