---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads upstream scope
  doc and frameworks; optionally partitions scope into unique homes; composes
  per-section body via I* / F / C derive artifacts; refines outline block H2
  titles at block close; validates draft quality; persists each section
  incrementally. When profile `drafting.display_layer` is true, runs the
  fact-first display-layer pipeline (P0–Pd–P3) instead — see Step P0–P3.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline (display_layer absent/false — default):** I1 Load → [I0 Partition when inductive absent] → I2 Compose (per section) → I3 Validate → Return.

**Pipeline (display_layer=true):** I1 Load → P0 Fact atomization (inductive: validate projected `_facts.json` only; deductive: atomize scope) → Pd Deductive derivation → P1 Global organization → P2 Per-chapter write → P3 Validate → Return. See Step P0–P3 below; I0/I2/I3 do not run on this branch. Design SSOT: `docs/biz/compose-fact-first-display-layer-design.md` §4/§11.4 (M4a); Pd: `compose-fact-first-k1-pd-design.md`; K2 inductive handshake: `compose-fact-first-k2-inductive-design.md`.

Init writes a readable draft from substance resolved by `$RESOLVE_I_STAR` (keys off `drafting.inductive`: inductive `{S}.json` or `_partition.json`), then Write. I0 still builds Partition when inductive is absent. Design SSOT: `docs/biz/compose-section-partition-design.md`.

- **Must:** operationalize inductive/partition substance; explicit 待决 for gaps; readable `F` structure; single home per atom (no cross-section restatement of the same proposition); on the Partition path, derive work items for derivation sections by decomposing committed upstream bodies (I2d Upstream derivation).
- **Must not:** invent beyond inductive/partition/scope/upstream-derivation sources; decide open choices during derivation; decision paste; empty shell sections; inclusive re-scan of full scope when Partition or inductive SoT is present.

The **Must**/**Must not** bullets above describe the `display_layer=false` (section-keyed) branch; the `display_layer=true` branch has its own rules under Step P0–P3.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../references/compose-theory.md`](../references/compose-theory.md).

Derive artifact contract: [`../references/init-draft-quality.md`](../references/init-draft-quality.md).

**Order (strict):** [I0 when required] → I2a Filter `I*` → I2b Derive `F` → I2c Derive `C` (+ author `display_title`) → I2d Write body → I2f Persist section (renders H3 from derive `display_title`) → [when `last_in_block`] I2g Block close.

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

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`) · `$CODE_GROUNDING` = profile `drafting.code_grounding` (boolean) · `$DISPLAY_LAYER` = profile `drafting.display_layer` (boolean, default `false`; selects the Pipeline branch above)

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
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` (display_layer=true only) |
| `$CHAPTERS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/chapters_control.py"` (display_layer=true only) |
| `$PD_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/pd_control.py"` (display_layer=true only; K1 Pd mechanical shell) |
| `$INDUCTIVE_FACTS_PROJ` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_facts_projection.py"` (K2; inductive + display_layer) |

`$PARTITION_CTL` subcommands: `--help` · `write` · `filter-i-star` · `validate` · `status`.

`$RESOLVE_I_STAR`: unified I* resolve (keys off profile `drafting.inductive`; add `--inductive-dir "$INDUCTIVE_DIR"` when `$INDUCTIVE_DIR` is set).

Internal only (not for I2a): `scope_resolver resolve-inductive` / `resolve-inductive-fidelity` — used by `$RESOLVE_I_STAR` implementation; do not call from runner prose.

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `set-display-title` · `set-block-title` · `append-intent` · `patch-block-heading` · `append-chapter` (display_layer=true only).

`$FACTS_CTL` subcommands: `--help` · `write` · `filter` · `validate` · `status`.

`$CHAPTERS_CTL` subcommands: `--help` · `write` · `validate` · `status`.

`$PD_CTL` subcommands: `--help` · `plan` · `append` · `audit` · `classify`. Scripts never invent derived text — only triggers / topo-order / id append / self-audit.

`$INDUCTIVE_FACTS_PROJ` subcommands: `--help` · `project` (decisions[] → `_facts.json`; invoked by parent compose engine after inductive-complete, not by this runner).

## Execution Contract

### Step I1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE section-registry --cycle-id "$CYCLE_ID"` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `intent` (else `desc`) / `intent_boundary` / `relations` / `presence` (used at Step P1 when `$DISPLAY_LAYER` is `true`; ignored otherwise)
   `$FETCH_COMPOSE section-form-registry --cycle-id "$CYCLE_ID"` → `sections.{key}.presentation` / `expression`
4. `$FETCH_COMPOSE outline-registry --cycle-id "$CYCLE_ID"` → shape depends on `$DISPLAY_LAYER`:
   - `false` (default): `outline_order`, per-block `heading` / `intents`.
   - `true`: candidates-shaped instead — `candidates[].{block, anchor_lenses}` + `rules` (advisory text). Do **not** expect `outline_order`/`blocks`/`intents` on this branch; consumed at Step P1, not here.
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

**Branch:** when `$DISPLAY_LAYER` is `true`, skip Steps I0/I2/I3 below entirely — go to Step P0 (fact-first display layer) after Step I1. Steps I0–I3 below are the `display_layer=false` (default) branch.

### Step I0 — Partition (display_layer=false only; and only when `$INDUCTIVE_DIR` is absent)

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

### Step I2 — Compose (display_layer=false only; per `section_key`, strict I2a → I2f [→ I2g])

For each key in `section_order`, produce section artifacts under `$REVISION_DIR`:

```text
_derive-{section_key}.json   # I2a–I2c (must exist before I2d); holds display_title
_body-{section_key}.txt      # I2d
_title-display.json          # I2f projection of derive display_title (section_key → H3)
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

- **Input:** `### Role Fields` · domain instance · `intent` · `sections.{key}.expression` · `F` · `sections.{key}.heading` · `i_star`
- **Action:** Derive 2–5 `(d, c, source)` pairs traceable to Role, intent, expression, or `expression_conventions`. If a KW dimension lacks named-atom substance, add `scope_absent` gap (no `kw_init`). Then author `display_title` (reader H3) here from this section's substance (`i_star` + `C`) — the only creative title decision; I2f consumes it mechanically. **Derivation section with empty `i_star`:** write `display_title = （待补）` provisionally and finalize it in I2d from the derived work items. Empty `i_star` with no derivation → `display_title = （待补）` (final). See init-draft-quality Display title rules.
- **Output:** write `c` and `display_title` into `_derive-{key}.json`
- **Done:** derive file complete; **do not start I2d until derive validates mentally against init-draft-quality**

#### I2d — Write body

- **Input:** `_derive-{key}.json` · `intent` · `intent_boundary` · upstream bodies in `$OUTPUT_DOC_PATH` (cross-section **reference**, never restate foreign homes) · registry `relations` for incremental cross-refs
- **Action:** Scaffold per `F`; rewrite `I*` into slots; obey every `C` pair, `intent`, and `intent_boundary`. Mark gaps with `> **待决：** …`. Foreign propositions → anchor cite only (e.g.「见 `I-2`」).
- **Upstream derivation (Partition path, derivation sections):** a *derivation section* has a registry `relations` edge `decompose` / `instantiate` to an upstream key (e.g. `SK` ← `AR`; `T` ← `SK`/`AR`). When mapped atoms underspecify the breakdown, derive the missing work items (phases, tasks, per-file edits, commands, ordering) from `own i_star + committed upstream-section bodies + code grounding` only — projection of decided content, not invention. Rules:
  - **Decompose, never decide:** a work item hitting an undecided choice → `待决` (cite its VF Must-Close row when one exists), do not pick.
  - **Cite the source anchor** per item (e.g.「按 `AR` 契约」·「对应 `SK` P1」) and append it to derive `scope_refs`.
  - Empty `i_star`: keep the I2a `scope_absent` gap and note the derivation source in it.
  - Never write derivation results back to `_partition.json`.
- **Code grounding (only when `$CODE_GROUNDING` is true):** For body increments that need concrete paths/symbols named in `i_star` or registry, Grep/Glob/Read under `$PROJECT_ROOT` with bounded queries. Success → append `code_refs` as `path` or `path#symbol`. Failure → do not invent; add `gaps` (`scope_absent` or note) + `待决`. Never write grounding results back to `_partition.json`.
- **Unfounded:** If a claim would enter body with neither scope, upstream-derivation anchor, nor code provenance → do not author as fact; `gaps.kind=unfounded` + `待决`.
- **Output:** `$REVISION_DIR/_body-{section_key}.txt` (no H2 line); update derive `scope_refs` / `code_refs` / `gaps` if derivation or grounding ran. **On a derivation section, overwrite the provisional `display_title` from the derived work items** (still per Display title rules).
- **Done:** body file exists; non-empty; ≥3 non-blank lines when `i_star` non-empty or derivation produced content

#### I2f — Persist section

Mechanical — `append-intent` reads the derive `display_title` (authored in I2c), renders the H3, and persists it to `_title-display.json`. There is no separate title step; do **not** re-author the title here.

```bash
$COMPOSE_DOC_CONTROL append-intent \
  --path "$OUTPUT_DOC_PATH" \
  --section "{section_key}" \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

- **Done:** `$OUTPUT_DOC_PATH` contains `<!-- section-key:{key} -->` for this section, and `_title-display.json` holds this section's H3

Block-first keys still write English `## {blocks.{id}.heading}` placeholder via `append-intent`; no block title args on this step.

#### I2g — Block close (when `last_in_block`)

At the last intent in an outline block: derive a neutral reader H2 from the outline block heading, then replace the English placeholder.

**1. Derive block title**

- **Input:** `blocks.{block_key}.heading`
- **Action:** `{n}. {neutral Chinese label from heading}` (`n` = 1-based `outline_order` index)
- **Forbidden:** English `heading` as the title; feature-specific or body-derived H2 text
- **Output:** persist via `set-block-title`; missing/empty outline heading → `（待补）`
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

### Step I3 — Validate (display_layer=false only)

1. When Partition was required: `$PARTITION_CTL validate` must still pass.
2. Run `$INIT_COMPOSE_VALIDATE`.
3. On failure → read stderr; fix cited sections (return to I2 for those keys; block title failures → re-run I2g for that block's last intent); re-run I3.
4. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

---

## display_layer=true branch: Steps P0–P3

Design SSOT: `docs/biz/compose-fact-first-display-layer-design.md` (§2–§11.4). Runs **instead of** Steps I0/I2/I3 when `$DISPLAY_LAYER` is `true`; Step I1 Load above is shared by both branches. `section_order` here means the profile's *lens* set (same registry, reframed as intent lenses — §2).

**Precondition (pairing invariant, §11.4 Major#6):** `$DISPLAY_LAYER=true` requires this profile's outline-registry to already be candidates-shaped (`candidates`/`rules`, §3.3) — `$INIT_COMPOSE_VALIDATE` hard-errors otherwise. Do not attempt this branch against a legacy `outline_order`/`blocks` outline.

**Handshake with `drafting.inductive` (K2):** when both `drafting.display_layer` and `drafting.inductive` are true, the inductive discovery loop remains the fact producer. Its settled `decisions[]` are projected once (at inductive completion) into the unified `_facts.json`. Init's P0 therefore **does not re-atomize `$SCOPE_DOC_PATH`**; it consumes the already-projected `_facts.json` (validate-only), then proceeds to Pd/P1. If `_facts.json` is absent, this is a hard error (projection must run first) — never silently fall back to re-atomization.

**Must:** tag every atom with N:M `lens_tags` (zero, one, or many — never a single `home`); run Step Pd for zero-coverage required derivation lenses before P1; place every fact in exactly one non-drop chapter; keep chapter `anchor_lenses` a subset of `section_order`; resolve every author-time `F-id` citation into a human-readable chapter reference before persisting `_body-{cid}.txt`; run `$INIT_COMPOSE_VALIDATE` before Return.
**Must not:** write a `fact:` or `section-key:` anchor into `$OUTPUT_DOC_PATH` (chapter anchors only, §11.4 item 1); invent a chapter with `derived_from` outside the outline-registry `candidates` set; decide open choices during P0/Pd/P1 (待决 same discipline as I2d); run I0/I2/I3 or their macros (`$PARTITION_CTL`, `$RESOLVE_I_STAR`, `append-intent`, `set-display-title`, `set-block-title`, `patch-block-heading`) on this branch.

### Step P0 — Fact atomization

**Branch A — inductive profile (`drafting.inductive=true`, K2):** projection already wrote `_facts.json` (parent ran `$INDUCTIVE_FACTS_PROJ project` after inductive-complete). **Do not** atomize `$SCOPE_DOC_PATH`. Only validate:

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Missing / invalid `_facts.json` → Blocking (never re-atomize from scope). **Done:** validate exit 0 → proceed to Pd.

**Branch B — deductive / non-inductive (`drafting.inductive` absent/false):**

1. **Atomize** `$SCOPE_DOC_PATH` once (whole doc) — same atomization discipline as I0 step 1 (merge same-fact restatements into one atom; do not split by source section-key; a figure is one atom, kept intact).
2. **Tag `lens_tags`:** for each atom, choose the set (zero, one, or many) of `section_order` keys whose intent the atom answers — using registry projection only (`intent` else `desc`, `intent_boundary` when present). This is N:M, not the I0 single-`home` choice: an atom may tag no lens (quarantine candidate, audited by Q1 — never invented into a lens to avoid emptiness), one lens, or several.
3. **Persist** via `$FACTS_CTL write` (facts = JSON array `{id:F-n, text, lens_tags}` — optional `source` only for Pd-derived facts later; P0 atoms omit `source`):

```bash
$FACTS_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --facts-file "<path to facts JSON>"
```

4. `$FACTS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0.

**Done (Branch B):** `$REVISION_DIR/_facts.json` exists and validates — **P0 atoms only**; Step Pd may append derived facts before P1.

### Step Pd — Deductive derivation（演绎派生，仅有派生边的 required 视角）

Design SSOT: `docs/biz/compose-fact-first-theory/compose-fact-first-k1-pd-design.md` §2. Runs **between** P0 and P1. **Pd = AI semantic step + mechanical shell** (`$PD_CTL`): CLI decides *which* lenses trigger and how ids append; **you** project work-item text from upstream **facts** (never prose).

**Must (CLI shell first):**
1. **Snapshot P0** (for audit): copy `$REVISION_DIR/_facts.json` → a temp `p0-facts.json`.
2. **Plan triggers** (zero-only + topo order + true gaps):

```bash
$PD_CTL plan \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Use stdout `order` (upstream-first). `true_gaps` → flag Round; do **not** invent. Partial coverage (`facts>0`) never appears in `triggered` (intentional vs I2d underspecify). Cycle → Blocking (non-zero exit).
3. **Input:** for each `L` in `order`, read upstream facts from plan stdout `upstreams[L].upstream_facts` (or `$FACTS_CTL filter --lens U`). Optional code grounding when `$CODE_GROUNDING` is true (same discipline as I2d). **Do not** read `_body` / `.md` prose.
4. **Emit (AI):** each work item → one object `{text, lens_tags:[L], source?}` (prefer upstream `F-id`s in `source`; freeform anchors allowed; no F-id integrity check). Undecided → embed `待决：…` in `text` (or a 待决 fact), never invent a choice. Write the array to a temp `derived.json`. Same-pass cascade: later lenses **see** facts you already decided for earlier lenses in `order`.
5. **Append once** (contiguous `F-(k+1)..`):

```bash
$PD_CTL append \
  --revision-dir "$REVISION_DIR" \
  --derived-file "<path to derived.json>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

6. **Self-audit** (cascade-aware; Blocking on fail):

```bash
$PD_CTL audit \
  --revision-dir "$REVISION_DIR" \
  --before-file "<path to p0-facts.json>" \
  --triggered "<comma-separated order from plan>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Empty upstream → audit skips that lens; C1 at P3 is the backstop.
7. `$FACTS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0.

**Must not:** decide open choices; read prose; write facts for non-triggered lenses; strip/re-derive by `source` in-place (re-derive ⇒ re-run atomization then Pd — inductive: re-run `$INDUCTIVE_FACTS_PROJ project` then Pd; deductive: re-run P0 then Pd — full re-run model); skip `$PD_CTL plan` / `append` / `audit` and invent triggers or ids by hand.

**Done:** `_facts.json` includes any Pd-derived facts; `$PD_CTL audit` and `$FACTS_CTL validate` exit 0.

### Step P1 — Global organization

- **Input:** `_facts.json` (compact index of `{id, text, lens_tags}` — never full prose; `lens_tags` is required here to derive each fact's `form_lens`, see Action) · outline-registry `candidates` (static, `{block, anchor_lenses}`) + `rules` (advisory merge/split/trim text) · `section_presence_map` (from section-registry `presence`, via `$FETCH_COMPOSE section-registry`).
- **Action (D1 hybrid, semantic — AI, not script):** start from lens-anchored candidates; content-adaptively merge/split/drop/reorder using `rules` as heuristics and topic clustering as the north star (§5 D1). For each fact, assign exactly one chapter + one `form_lens` (∈ that fact's own `lens_tags` ∩ the chosen chapter's `anchor_lenses`) — priority-derive the placement using the §7.4 heuristic (invariants > structure/contract > success > contact > context) as reference, not a mechanical lookup (§5 D2/§8.1). A required lens with zero anchoring candidates is a modeling gap — do not silently drop it; either add a candidate-anchored chapter or flag it as a gap for Round. An optional lens may legitimately end up with zero facts (需求2, D6) — do not fabricate content to fill it.
- **Output:** write `_chapters.json` (chapters = JSON array `{id, anchor_lenses, derived_from, op, facts:[{fid, form_lens}]}` only — `op` ∈ `keep|merge|split|drop`; `derived_from` cites the static `candidates[].block` id(s) this chapter descends from):

```bash
$CHAPTERS_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --chapters-file "<path to chapters JSON>"
```

- `$CHAPTERS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0 (structural shape only — L1/L3/L4/L5/C1 cross-file gates run at P3).
- **Done:** `$REVISION_DIR/_chapters.json` exists and validates; every fact with non-empty `lens_tags` is assigned to exactly one non-drop chapter.

### Step P2 — Per-chapter write (per non-`drop` chapter in `_chapters.json` order)

For each chapter, produce:

```text
_derive-{cid}.json   # chapter H2 title: {"display_title": "..."}
_body-{cid}.txt      # chapter prose (no H2 line, no anchor)
```

- **Input:** this chapter's `facts[]` (`{fid, form_lens}`) resolved against `_facts.json` · `section-form-registry` entries for each distinct `form_lens` (`{carrier, structure}`, same registry as I2b) · this chapter's `anchor_lenses`.
- **Action — D4 four-piece container (§9), semantic (AI):**
  1. **Lead sentence:** one orienting sentence derived from `anchor_lenses` intent + `covered_lenses` (anchor_lenses ∪ every placed fact's `lens_tags`).
  2. **Primary axis:** the main `anchor_lenses` entry's form (highest §7.4 priority when the chapter has multiple anchors) carries facts whose `form_lens` matches an anchor lens.
  3. **Nested cross-cut groups:** facts whose `form_lens` is not an anchor lens go into bounded, clearly labeled sub-blocks (H4 or a callout) appended after the primary axis — never interleaved into it (anti-scatter discipline, §9.3).
  4. **Ordering:** within the primary axis, order by §7.4 priority; cross-cut groups after.
  - **Cross-chapter references (D3):** an author may cite another fact by `F-id` while drafting; before this body is finalized, resolve every such citation into a human-readable chapter reference (e.g. "见「架构」章") — never leave a raw `F-id` in persisted `_body-{cid}.txt`.
  - **Gaps:** mark with `> **待决：** …`, same discipline as I2d.
- **Output:** write `_derive-{cid}.json` (title only) and `_body-{cid}.txt`, then assemble into `$OUTPUT_DOC_PATH`:

```bash
$COMPOSE_DOC_CONTROL append-chapter \
  --path "$OUTPUT_DOC_PATH" \
  --chapter-id "{cid}" \
  --revision-dir "$REVISION_DIR"
```

- **Done:** `$OUTPUT_DOC_PATH` contains `<!-- chapter:{cid} -->` for this chapter with non-empty rendered content.

No title sidecar, no block H2 grouping on this branch (Steps I2f/I2g and their macros do not run here) — chapter titles are flat `## {display_title}` from `_derive-{cid}.json`.

### Step P3 — Validate

1. Run `$INIT_COMPOSE_VALIDATE` (same macro as I3; internally dispatches on `drafting.display_layer` to the fact-first gate suite — L1/L3/L4/L5/C1 placement/coverage gates + chapter-artifact existence + assembly completeness).
2. On failure → read stderr; route by gap type:
   - **C1 on a derivation lens** (required lens with `decompose`/`instantiate` edge still at zero facts) → **re-run atomization then Pd** (inductive: `$INDUCTIVE_FACTS_PROJ project` then Pd; deductive: P0 then Pd — full re-run; do not patch in place) or flag Round;
   - **true coverage gap** (required, zero facts, **no** derivation edge) → Round / modeling fix — Pd will not invent;
   - **placement / candidate / L\*** issues → return to P1;
   - missing/empty chapter artifacts or missing chapter anchors → return to P2;
   then re-run P3.
3. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

`display_layer=false` (default):

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

`display_layer=true`:

```text
Initializing complete (fact-first display layer).
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Facts: <REVISION_DIR>/_facts.json (<N> facts; Pd derived: <N>)
  Pd: covered <M> required derivation lens(es); true gaps flagged: <ids or none>
  Chapters: <REVISION_DIR>/_chapters.json (<N> chapters, <N> dropped)
  Chapter artifacts: <REVISION_DIR>/_derive-*.json, _body-*.txt
  Quarantined facts (empty lens_tags, Q1 audit): <N> — <ids or none>
  Scope cross-check: <SCOPE_DOC_PATH>
  Draft status: Initialized
  Next step: parent pause gate (options from profile drafting.post_init_options)
```
