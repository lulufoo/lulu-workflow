---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads upstream scope
  doc and frameworks; optionally partitions scope into unique homes; composes
  per-section body via I* / F / C derive artifacts; refines outline block H2
  titles at block close; validates draft quality; persists each section
  incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** I1 Load → [I0 Partition when inductive absent] → I2 Compose (per section) → I3 Validate → Return.

Init writes a readable draft from substance resolved by `$RESOLVE_I_STAR` (keys off `drafting.inductive`: inductive `{S}.json` or `_partition.json`), then Write. I0 still builds Partition when inductive is absent. Design SSOT: `docs/biz/compose-section-partition-design.md`.

- **Must:** operationalize inductive/partition substance; explicit 待决 for gaps; readable `F` structure; single home per atom (no cross-section restatement of the same proposition).
- **Must not:** invent beyond inductive/partition/scope; decision paste; empty shell sections; inclusive re-scan of full scope when Partition or inductive SoT is present.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../references/compose-theory.md`](../references/compose-theory.md).

Derive artifact contract: [`../references/init-draft-quality.md`](../references/init-draft-quality.md).

**Order (strict):** [I0 when required] → I2a Filter `I*` → I2b Derive `F` → I2c Derive `C` → I2d Write body → I2e Derive display title → I2f Persist section → [when `last_in_block`] I2g Block close.

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_DOC_PATH` | Absolute path to compose intent SSOT (design-doc or decision-doc) |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |
| `$INDUCTIVE_DIR` | **Optional.** Dir of inductive per-section SoT (`<SECTION>.json` only). Absent → Partition path |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`) · `$CODE_GROUNDING` = profile `drafting.code_grounding` (boolean)

All compose and scope macros **must** pass `--profile "$COMPOSE_PROFILE"`. `$FETCH_COMPOSE` **must** also pass `--cycle-id "$CYCLE_ID"`.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" resolve-role --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" resolve-domain --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile "$COMPOSE_PROFILE"` |
| `$RESOLVE_OUTLINE_LAYOUT` | `python3 "$SKILL_ROOT/compose/scripts/section/outline_layout.py" resolve --section "{section_key}" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$PARTITION_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/partition_control.py"` |
| `$RESOLVE_I_STAR` | `python3 "$SKILL_ROOT/compose/scripts/section/i_star_control.py" resolve-i-star --revision-dir "$REVISION_DIR" --section "{section_key}" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` (+ `--inductive-dir "$INDUCTIVE_DIR"` when set) |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py"` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/init_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |

`$PARTITION_CTL` subcommands: `--help` · `write` · `filter-i-star` · `validate` · `status`.

`$RESOLVE_I_STAR`: unified I* resolve (keys off profile `drafting.inductive`; add `--inductive-dir "$INDUCTIVE_DIR"` when `$INDUCTIVE_DIR` is set).

Internal only (not for I2a): `scope_resolver resolve-inductive` / `resolve-inductive-fidelity` — used by `$RESOLVE_I_STAR` implementation; do not call from runner prose.

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `set-display-title` · `set-block-title` · `append-intent` · `patch-block-heading`.

## Execution Contract

### Step I1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE section-registry --cycle-id "$CYCLE_ID"` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `intent` (else `desc`) / `intent_boundary`
   `$FETCH_COMPOSE section-form-registry --cycle-id "$CYCLE_ID"` → `sections.{key}.presentation` / `expression`
4. `$FETCH_COMPOSE outline-registry --cycle-id "$CYCLE_ID"` → `outline_order`, per-block `heading` / `intents`.
5. `$FETCH_COMPOSE section-kw-criteria --cycle-id "$CYCLE_ID"` → each `## {section_key}` block (Fill completeness for **named** atoms only — do not pull foreign homes to satisfy KW).
6. Read `$SCOPE_DOC_PATH` full text once (shared across I0/I2).
7. Read profile `drafting.code_grounding` → `$CODE_GROUNDING`.
8. **Init document:** Substitute placeholders in `document_preamble`. Write via:

```bash
$COMPOSE_DOC_CONTROL init-doc \
  --path "$OUTPUT_DOC_PATH" \
  --preamble "<substituted document_preamble markdown>"
```

Prefer `--preamble-file` when content is multiline.

Do **not** append outline-registry content to the deliverable header. Do **not** fetch spec-template URLs.

**Done:** `$OUTPUT_DOC_PATH` exists with preamble only.

### Step I0 — Partition (only when `$INDUCTIVE_DIR` is absent)

When inductive SoT is present, **skip I0** (homes already live in per-section `decisions[]`).

When absent:

1. **Atomize** `$SCOPE_DOC_PATH` once (whole doc). Merge same-fact restatements into one atom. Do not split by source section-key. Treat a **figure** (a block whose meaning is its whole topology/layout) as **one atom**, text kept intact; never split it into edge/node claims. Boundary aids (fences, titled blocks, box-drawing runs) are heuristics, not an allowlist.
2. **Assign `home`:** for each atom, choose exactly one key in current `section_order` using registry projection only: `section_order` + intent text (`intent` else `desc`) + `intent_boundary` when present. Tie-break: invariants > structure/contract > success > contact > context; **figures → structural key (usually AR), never SK/T by default**; AR vs SK/T → structure→AR, phase/task→SK/T, ties prefer AR. May map into SK/T even if upstream lacked those keys.
3. **Persist** via `$PARTITION_CTL write` (atoms = JSON array `{id:A-n, text, home}` only):

```bash
$PARTITION_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --atoms-file "<path to atoms JSON>"
```

4. `$PARTITION_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0.

**Done:** `$REVISION_DIR/_partition.json` exists and validates. Do not invent paths here (grounding is I2d when `$CODE_GROUNDING`).

### Step I2 — Compose (per `section_key`, strict I2a → I2f [→ I2g])

For each key in `section_order`, produce section artifacts under `$REVISION_DIR`:

```text
_derive-{section_key}.json   # I2a–I2c (must exist before I2d)
_body-{section_key}.txt      # I2d
_title-display.json          # I2e (section_key → display title)
_title-block.json            # I2g (block_key → reader H2; last_in_block only)
```

Field schema: [`init-draft-quality.md`](../references/init-draft-quality.md).

After each I2f, resolve layout and run **I2g** when the current key is the last intent in its outline block (`last_in_block` from `$RESOLVE_OUTLINE_LAYOUT` JSON). Single-intent blocks (`first_in_block == last_in_block`) close in the same iteration.

#### I2a — Filter `I*`

- **Input:** `$RESOLVE_I_STAR` · scope doc (completeness cross-check only) · `intent` / `intent_boundary` · kw `## {key}` (named-atom completeness only)
- **Action:** Mechanical resolve only — do **not** branch on partition vs inductive in prose; do **not** inclusive-match full scope:

```bash
# When $INDUCTIVE_DIR is set, append: --inductive-dir "$INDUCTIVE_DIR"
$RESOLVE_I_STAR
```

Stdout → `i_star`. Empty stdout with exit 0 → `i_star=""` + `scope_absent` gap. Non-zero exit → Blocking (contract source missing/illegal). Implementation keys off `drafting.inductive` (`false` → `_partition.json` by `home`; `true` → `inductive-scope/<SECTION>.json` `decisions[].text` only; JSON only, no `.md`).
- **Output:** write `i_star`, `scope_refs`, `code_refs` (`[]` for now), `gaps` into `_derive-{key}.json`. **Do not** write `kw_init`.
- **Done:** derive file exists with `i_star` / `scope_refs` / `code_refs` / `gaps` per contract

#### I2b — Derive `F`

- **Input:** `### Role Fields` · domain instance · `intent` · `intent_boundary` · `sections.{key}.presentation` (`guidance`, `allowed`, `forbidden`)
- **Action:** Three-step narrowing (section presentation > domain > role > intent). See compose-theory · Form (F). Select `f.carrier` from `presentation.allowed`; `f.structure` from selected entry's `structure` field; `f.forbidden` from `presentation.forbidden` plus substance `intent_boundary` defers elsewhere.
- **Output:** write `f.carrier`, `f.structure`, `f.forbidden` into `_derive-{key}.json`
- **Done:** `f.carrier` non-empty in derive file

#### I2c — Derive `C`

- **Input:** `### Role Fields` · domain instance · `intent` · `sections.{key}.expression` · `F`
- **Action:** Derive 2–5 `(d, c, source)` pairs traceable to Role, intent, expression, or `expression_conventions`. If a KW dimension lacks named-atom substance, add `scope_absent` gap (no `kw_init`).
- **Output:** write `c` into `_derive-{key}.json`
- **Done:** derive file complete; **do not start I2d until derive validates mentally against init-draft-quality**

#### I2d — Write body

- **Input:** `_derive-{key}.json` · `intent` · `intent_boundary` · upstream bodies in `$OUTPUT_DOC_PATH` (cross-section **reference**, never restate foreign homes) · registry `relations` for incremental cross-refs
- **Action:** Scaffold per `F`; rewrite `I*` into slots; obey every `C` pair, `intent`, and `intent_boundary`. Mark gaps with `> **待决：** …`. Foreign propositions → anchor cite only (e.g.「见 `I-2`」).
- **Code grounding (only when `$CODE_GROUNDING` is true):** For body increments that need concrete paths/symbols named in `i_star` or registry, Grep/Glob/Read under `$PROJECT_ROOT` with bounded queries. Success → append `code_refs` as `path` or `path#symbol`. Failure → do not invent; add `gaps` (`scope_absent` or note) + `待决`. Never write grounding results back to `_partition.json`.
- **Unfounded:** If a claim would enter body with neither scope nor code provenance → do not author as fact; `gaps.kind=unfounded` + `待决`.
- **Output:** `$REVISION_DIR/_body-{section_key}.txt` (no H2 line); update derive `code_refs` / `gaps` if grounding ran
- **Done:** body file exists; non-empty; ≥3 non-blank lines when `i_star` non-empty

#### I2e — Derive display title

- **Input:** `sections.{key}.heading` · body file · `i_star` substance
- **Action:** Short localized title (~8–20 chars): type anchor from `heading` + one domain theme from substance.
- **Forbidden:** verbatim registry `heading`; file paths; API names; copying first body sentence
- **Output:** persist via `set-display-title`; empty `i_star` → `（待补）`
- **Done:** `set-display-title` exits 0

```bash
$COMPOSE_DOC_CONTROL set-display-title \
  --revision-dir "$REVISION_DIR" \
  --section "{section_key}" \
  --title "<localized display title>"
```

#### I2f — Persist section

```bash
$COMPOSE_DOC_CONTROL append-intent \
  --path "$OUTPUT_DOC_PATH" \
  --section "{section_key}" \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

- **Done:** `$OUTPUT_DOC_PATH` contains `<!-- section-key:{key} -->` for this section

Block-first keys still write English `## {blocks.{id}.heading}` placeholder via `append-intent`; no block title args on this step.

#### I2g — Block close (when `last_in_block`)

At the last intent in an outline block: infer reader H2 from whole-block substance, then replace the English placeholder.

**1. Derive block title**

- **Input:** `block_intents[]` bodies (`_body-*.txt`) · optional `_title-display.json` entries · registry `intent` per intent · `blocks.{block_key}.heading` (semantic anchor)
- **Action:** One localized reader-facing H2 title for the whole block; may include numbering aligned with v4-style docs.
- **Forbidden:** verbatim English `block.heading`; summarizing a single intent only
- **Output:** persist via `set-block-title`; no block substance → `（待补）`
- **Done:** `set-block-title` exits 0

```bash
$COMPOSE_DOC_CONTROL set-block-title \
  --revision-dir "$REVISION_DIR" \
  --block-key "{block_key}" \
  --title "<localized block H2>"
```

**2. Patch block H2**

```bash
$COMPOSE_DOC_CONTROL patch-block-heading \
  --path "$OUTPUT_DOC_PATH" \
  --block-key "{block_key}" \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

- **Action:** Replace the unique `## {blocks.{block_key}.heading}` placeholder with the block title derived in step 1.
- **Done:** `patch-block-heading` exits 0; H3 anchors unchanged
- **Failure:** blocking; stderr cites `block_key`

All sections remain draft until Round probe.

### Step I3 — Validate

1. When Partition was required: `$PARTITION_CTL validate` must still pass.
2. Run `$INIT_COMPOSE_VALIDATE`.
3. On failure → read stderr; fix cited sections (return to I2 for those keys; block title failures → re-run I2g for that block's last intent); re-run I3.
4. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Initializing complete.
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Partition: <REVISION_DIR>/_partition.json or none (inductive)
  Derive artifacts: <REVISION_DIR>/_derive-*.json
  Display titles: <REVISION_DIR>/_title-display.json
  Block titles: <REVISION_DIR>/_title-block.json
  Synthesized sections: <space-separated section keys from section_order>
  Inductive SoT: <INDUCTIVE_DIR or none>
  Code grounding: <true|false>
  Scope cross-check: <SCOPE_DOC_PATH>
  Draft status: Initialized
  Next step: parent pause gate (options from profile drafting.post_init_options)
```
