---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads upstream scope
  doc and frameworks; composes per-section body via I* / F / C derive artifacts;
  refines outline block H2 titles at block close; validates draft quality;
  persists each section incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** I1 Load → I2 Compose (per section) → I3 Validate → Return.

Init writes a readable draft from scope substance only.

- **Must:** operationalize scope content; explicit 待决 for scope gaps; readable `F` structure.
- **Must not:** scope-external speculation; decision paste; empty shell sections.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../../references/compose-theory.md`](../../references/compose-theory.md).

Derive artifact contract: [`../../references/init-draft-quality.md`](../../references/init-draft-quality.md).

**Order (strict):** I2a Filter `I*` → I2b Derive `F` → I2c Derive `C` → I2d Write body → I2e Derive display title → I2f Persist section → [when `last_in_block`] I2g Block close.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_DOC_PATH` | Absolute path to compose intent SSOT (design-doc or decision-doc) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |
| `$INDUCTIVE_DIR` | **Optional.** Dir of inductive per-section scope slices (`<section>.md`). Absent → SSOT-only behavior |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`)

All compose and scope macros **must** pass `--profile "$COMPOSE_PROFILE"`. `$FETCH_COMPOSE` **must** also pass `--cycle-id "$CYCLE_ID"`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-domain --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$RESOLVE_OUTLINE_LAYOUT` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/outline_layout.py" resolve --section "{section_key}" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$RESOLVE_INDUCTIVE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/scope/scope_resolver.py" resolve-inductive --section "{section_key}" --inductive-dir "$INDUCTIVE_DIR" --project-root "$(pwd)"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/compose_doc_control.py"` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose-kernel/scripts/section/init_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-intent` · `patch-block-heading`.

## Execution Contract

### Step I1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE section-registry --cycle-id "$CYCLE_ID"` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `intent` (else `desc`) / `intent_boundary`
   `$FETCH_COMPOSE section-form-registry --cycle-id "$CYCLE_ID"` → `sections.{key}.presentation` / `expression`
4. `$FETCH_COMPOSE outline-registry --cycle-id "$CYCLE_ID"` → `outline_order`, per-block `heading` / `intents`.
5. `$FETCH_COMPOSE section-kw-criteria --cycle-id "$CYCLE_ID"` → each `## {section_key}` block.
6. Read `$SCOPE_DOC_PATH` full text once (shared across I2).
7. **Init document:** Substitute placeholders in `document_preamble`. Write via:

```bash
$COMPOSE_DOC_CONTROL init-doc \
  --path "$OUTPUT_DOC_PATH" \
  --preamble "<substituted document_preamble markdown>"
```

Prefer `--preamble-file` when content is multiline.

Do **not** append outline-registry content to the deliverable header. Do **not** fetch spec-template URLs.

**Done:** `$OUTPUT_DOC_PATH` exists with preamble only.

### Step I2 — Compose (per `section_key`, strict I2a → I2f [→ I2g])

For each key in `section_order`, produce section artifacts under `$REVISION_DIR`:

```text
_derive-{section_key}.json   # I2a–I2c (must exist before I2d)
_body-{section_key}.txt      # I2d
_title-{section_key}.txt     # I2e
_title-block-{block_key}.txt # I2g (last_in_block only)
```

Field schema: [`init-draft-quality.md`](../../references/init-draft-quality.md).

After each I2f, resolve layout and run **I2g** when the current key is the last intent in its outline block (`last_in_block` from `$RESOLVE_OUTLINE_LAYOUT` JSON). Single-intent blocks (`first_in_block == last_in_block`) close in the same iteration.

#### I2a — Filter `I*`

- **Input:** scope doc (`$SCOPE_DOC_PATH`, the SSOT) · **optional** inductive scope slice · `sections.{key}.intent` (else `desc`) · `intent_boundary` · kw `## {key}`
- **Inductive slice (only when `$INDUCTIVE_DIR` is set):** run `$RESOLVE_INDUCTIVE` for this `{section_key}`. If it prints a path, read that slice as **secondary, code-anchored substance** for this section. The scope doc stays the **SSOT and completeness anchor**: judge `gaps` against the scope doc, not the slice; the inductive slice **enriches** `i_star` (adds code-anchored HOW), it never overrides or substitutes a scope decision. Empty output → SSOT only.
- **Action:** Include scope substance matching `intent` and at least one KW dimension (semantic; do not label KW numbers). Fold in the grounding slice's matching substance when present. Exclude content belonging to other sections. **Must-effort:** extract all matching scope substance; use `gaps` for scope absences — do not silently omit.
- **Output:** write `i_star`, `scope_refs`, `gaps`, `kw_init` into `_derive-{key}.json`
- **Done:** derive file exists with `i_star` / `scope_refs` / `gaps` populated per contract

#### I2b — Derive `F`

- **Input:** `### Role Fields` · domain instance · `intent` · `sections.{key}.presentation` (`guidance`, `allowed`, `forbidden`)
- **Action:** Three-step narrowing (section presentation > domain > role > intent). See compose-theory · Form (F). Select `f.carrier` from `presentation.allowed`; `f.structure` from selected entry's `structure` field; `f.forbidden` from `presentation.forbidden`.
- **Output:** write `f.carrier`, `f.structure`, `f.forbidden` into `_derive-{key}.json`
- **Done:** `f.carrier` non-empty in derive file

#### I2c — Derive `C`

- **Input:** `### Role Fields` · domain instance · `intent` · `sections.{key}.expression` · `F`
- **Action:** Derive 2–5 `(d, c, source)` pairs traceable to Role, intent, expression, or `expression_conventions`. Finalize `kw_init` booleans with matching `gaps` for false dimensions when scope lacks substance.
- **Output:** write `c` and finalized `kw_init` into `_derive-{key}.json`
- **Done:** derive file complete; **do not start I2d until derive validates mentally against init-draft-quality**

#### I2d — Write body

- **Input:** `_derive-{key}.json` · `intent` · `intent_boundary` · upstream bodies in `$OUTPUT_DOC_PATH` (de-duplication)
- **Action:** Scaffold per `F`; rewrite `I*` into slots; obey every `C` pair and `intent`. Mark scope gaps with `> **待决：** …` when `gaps` present.
- **De-duplication:** Do not repeat boundary constraints deferred by `intent_boundary`. Read upstream via `compose_doc_schema.py --section-body` when needed.
- **Output:** `$REVISION_DIR/_body-{section_key}.txt` (no H2 line)
- **Done:** body file exists; non-empty; ≥3 non-blank lines when `i_star` non-empty

#### I2e — Derive display title

- **Input:** `sections.{key}.heading` · body file · `i_star` substance
- **Action:** Short localized title (~8–20 chars): type anchor from `heading` + one domain theme from substance.
- **Forbidden:** verbatim registry `heading`; file paths; API names; copying first body sentence
- **Output:** `$REVISION_DIR/_title-{section_key}.txt`; empty `i_star` → `（待补）`
- **Done:** title file exists with one non-empty line

#### I2f — Persist section

```bash
$COMPOSE_DOC_CONTROL append-intent \
  --path "$OUTPUT_DOC_PATH" \
  --section "{section_key}" \
  --display-title-file "$REVISION_DIR/_title-{section_key}.txt" \
  --body-file "$REVISION_DIR/_body-{section_key}.txt" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

- **Done:** `$OUTPUT_DOC_PATH` contains `<!-- section-key:{key} -->` for this section

Block-first keys still write English `## {blocks.{id}.heading}` placeholder via `append-intent`; no block title args on this step.

#### I2g — Block close (when `last_in_block`)

At the last intent in an outline block: infer reader H2 from whole-block substance, then replace the English placeholder.

**1. Derive block title**

- **Input:** `block_intents[]` bodies (`_body-*.txt`) · optional `_title-*.txt` · registry `intent` per intent · `blocks.{block_key}.heading` (semantic anchor)
- **Action:** One localized reader-facing H2 title for the whole block; may include numbering aligned with v4-style docs.
- **Forbidden:** verbatim English `block.heading`; summarizing a single intent only
- **Output:** `$REVISION_DIR/_title-block-{block_key}.txt` (one line); no block substance → `（待补）`
- **Done:** block title file exists with one non-empty line

**2. Patch block H2**

```bash
$COMPOSE_DOC_CONTROL patch-block-heading \
  --path "$OUTPUT_DOC_PATH" \
  --block-key "{block_key}" \
  --title-file "$REVISION_DIR/_title-block-{block_key}.txt" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

- **Action:** Replace the unique `## {blocks.{block_key}.heading}` placeholder with the block title file content.
- **Done:** document H2 for the block matches `_title-block-{block_key}.txt`; H3 anchors unchanged
- **Failure:** blocking; stderr cites `block_key`

All sections remain draft until Round probe.

### Step I3 — Validate

1. Run `$INIT_COMPOSE_VALIDATE`.
2. On failure → read stderr; fix cited sections (return to I2 for those keys; block title failures → re-run I2g for that block's last intent); re-run I3.
3. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0. When outline-registry is present: each block H2 ≠ English placeholder (unless `（待补）`); `_title-block-*.txt` matches document H2.

## Return Summary

```text
Initializing complete.
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Derive artifacts: <REVISION_DIR>/_derive-*.json
  Block titles: <REVISION_DIR>/_title-block-*.txt
  Synthesized sections: <space-separated section keys from section_order>
  Scope SSOT: <SCOPE_DOC_PATH>
  Draft status: Initialized
  Next step: parent pause gate (FreeEdit, Evaluate, or Deliver according to profile options)
```
