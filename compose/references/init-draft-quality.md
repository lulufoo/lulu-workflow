# Init Draft Quality

> Referenced by: initializing-runner (P0–P3 chapter artifacts, P3 validate).  
> Theory: [`compose-theory.md`](compose-theory.md).

## Purpose

Chapter derive + body artifacts make Init synthesis inspectable and gate-able without replacing Round probe. Section-key I2 derive / `_title-display.json` / Partition retired (K3-d).

## Init positioning

| Must | Must not |
|------|----------|
| Operationalize fact substance into readable chapter bodies | Scope-external speculation |
| Mark gaps explicitly (`待决` in body when substance missing) | Decision verbatim paste |
| Produce non-drop chapters with non-empty body + `display_title` | Empty shell chapters / `section-key:` anchors |

Round still owns formal KW / upstream / intent gap closure.

## Per-chapter artifacts (fact-first)

```text
$REVISION_DIR/_facts.json              # fact store (P0; K2 projects inductive decisions[])
$REVISION_DIR/_chapters.json           # chapter plan (P1)
$REVISION_DIR/_derive-{cid}.json       # P2 chapter derive (display_title, …)
$REVISION_DIR/_body-{cid}.txt          # P2 chapter body
$OUTPUT_DOC_PATH                       # assembled via append-chapter (<!-- chapter:{cid} -->)
```

`cid` is the chapter id from `_chapters.json` (not a registry section key).

## `_derive-{cid}.json` (chapter)

| Field | Required | Rules |
|-------|----------|-------|
| `display_title` | yes | Reader H2 under the chapter anchor; concise localized string, no code tokens; `（待补）` when substance missing |
| other fields | per runner | As authored in P2; validator hard-gates non-empty `display_title` on every non-drop chapter |

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

## Validate command

`init_compose_validation.py validate` always runs the display-layer suite: candidates-shaped outline pairing, `_facts.json` / `_chapters.json`, placement/coverage gates, chapter derive/body files, and chapter anchors in the compose doc. See script `--help` for exit codes and stderr format.
