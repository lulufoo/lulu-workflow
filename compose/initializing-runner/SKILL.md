---
name: initializing-runner
description: >-
  Autonomous Initializing step for compose-profile drafting. Loads upstream scope
  doc and frameworks; atomizes facts (or validates discovery-written inductive
  `_facts.json`); organizes chapters; composes per-chapter bodies via fact-first
  display-layer pipeline (Steps 1–6); validates draft quality; persists each
  chapter incrementally.
---

# initializing-runner

Run this sub-skill only for the `Initializing` step inside a parent compose stage Drafting shell.

Use `$COMPOSE_PROFILE` from parent dispatch; kernel default applies only when omitted.

## Scope

**Pipeline:** Step 1 Load → Step 2 Atomize facts (inductive: validate discovery-written `_facts.json` only; deductive: atomize scope) → Step 3 Derive facts → Step 4 Organize chapters → Step 5 Write chapters → Step 6 Validate → Return.

Init substance: display-layer Steps 2–6. Inductive discovery loop owns `_facts.json` as engine state (K4; no projection). Deductive Init atomizes scope into facts.

- **Must:** operationalize display-layer facts (inductive: validate-only on discovery-written `_facts.json`; deductive: atomize scope); explicit 待决 for gaps; readable chapter bodies.
- **Must not:** invent beyond facts/scope/upstream-derivation sources; decide open choices during derivation; decision paste; empty shell chapters; recreate `_partition.json` or reassemble fact text by hand; write `section-key:` anchors (chapter anchors only); invoke retired `$INDUCTIVE_FACTS_PROJ project`.

Round still owns formal gap closure. Do not ask the user questions. Do not run InDialogue, Reopen, Evaluating, or delivery work.

## Theory (Compose)

See [`../references/compose-theory.md`](../references/compose-theory.md).

Derive artifact contract: [`../references/init-draft-quality.md`](../references/init-draft-quality.md).

## Parent-Provided Inputs

| Variable | Purpose |
|---|---|
| `$REVISION_DIR` | Absolute path to `revision{N}/` |
| `$SCOPE_REF_PATH` | Absolute path to compose scope SSOT (decision holders: `decision-fact.json` required; plan←design may be design-doc) |
| `$SCOPE_FACTS_PATH` | Absolute path to upstream fact package (design `_facts.json`); empty when upstream has no fact package |
| `$OUTPUT_DOC_PATH` | Absolute path to output document (design-doc.md or tech-doc.md) |
| `$COMPOSE_PROFILE` | Compose profile id from parent dispatch |
| `$CYCLE_TYPE` | `feature` |
| `$CYCLE_ID` | Active cycle id |

Self-resolved: `$PROJECT_ROOT` = `$(pwd)` · `$OUTPUT_DOC_PATH` from parent input (fallback `{REVISION_DIR}/tech-doc.md`) · `$CODE_GROUNDING` = profile `drafting.code_grounding` (boolean)

All macros that declare `--profile` **must** pass `--profile "$COMPOSE_PROFILE"` (prefer `--profile` before the subcommand on `$RESOLVE_*`). `$FACTS_CTL filter` does **not** take `--profile` — pass only `--revision-dir` / `--lens`. `$FETCH_COMPOSE` includes `--cycle-id` in the macro.

## Script Macros

| Macro | Command |
|-------|---------|
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" resolve-role --cycle-id "$CYCLE_ID"` |
| `$RESOLVE_DOMAIN` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" resolve-domain --cycle-id "$CYCLE_ID"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile "$COMPOSE_PROFILE" --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py"` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/init_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc "$OUTPUT_DOC_PATH" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` |
| `$CHAPTERS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/chapters_control.py"` |
| `$DERIVE_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/derive_control.py"` (K1 Step 3 mechanical shell) |
| `$DECISION_FACT_CLAIM_CTL` | `python3 "$SKILL_ROOT/compose/scripts/core/decision_fact_claim_control.py" --revision-dir "$REVISION_DIR"` |

`$COMPOSE_DOC_CONTROL` subcommands: `--help` · `init-doc` · `append-chapter`.

`$FACTS_CTL` subcommands: `--help` · `write` · `filter` · `validate` · `status`.

`$CHAPTERS_CTL` subcommands: `--help` · `write` · `validate` · `status`.

`$DERIVE_CTL` subcommands: `--help` · `plan` · `append` · `audit` · `classify`. Scripts never invent derived text — only triggers / topo-order / id append / self-audit.

> **K4:** `$INDUCTIVE_FACTS_PROJ project` is **retired**. Inductive `_facts.json` is written by the discovery loop (`seed-decision` / `settle-open`). Do not invoke projection from this runner.

## Execution Contract

### Step 1 — Load

1. `$RESOLVE_PLAN_ROLE` → Plan Scope Constraints (`### Role`, `### Role Fields`).
2. `$RESOLVE_DOMAIN` → `domain instance`.
3. `$FETCH_COMPOSE --role section-registry` (JSON) → `section_order`, `document_preamble`, per-section `heading` / `intent` (else `desc`) / `intent_boundary` / `relations` / `presence` (used at Step 4)
   `$FETCH_COMPOSE --role section-form-registry` → `sections.{key}.presentation` / `expression`
4. `$FETCH_COMPOSE --role outline-registry` → candidates-shaped: `candidates[].{block, anchor_lenses}` + `rules` (advisory text). Consumed at Step 4.
5. `$FETCH_COMPOSE --role section-kw-criteria` → each `## {section_key}` block (Fill completeness for **named** atoms only).
6. Read `$SCOPE_REF_PATH` once (JSON units or prose, depending on artifact).
7. Read profile `drafting.code_grounding` → `$CODE_GROUNDING`.
8. **Init document:** Substitute placeholders in `document_preamble`. Write via:

```bash
$COMPOSE_DOC_CONTROL init-doc \
  --path "$OUTPUT_DOC_PATH" \
  --preamble "<substituted document_preamble markdown>"
```

Prefer `--preamble-file` when content is multiline.

Do **not** append outline-registry content to the deliverable header. Do **not** fetch spec-template URLs.

**Done:** `$OUTPUT_DOC_PATH` exists with preamble only. Proceed to Step 2.

---

#### Pipeline invariants (Steps 2–6)

`section_order` means the profile's *lens* set (same registry, reframed as intent lenses — see [Theory](../references/compose-theory.md)).

**Precondition (pairing invariant):** outline-registry must be candidates-shaped (`candidates`/`rules`) — `$INIT_COMPOSE_VALIDATE` hard-errors otherwise.

**Handshake with `drafting.inductive` (K4):** operative branch is Step 2 Branch A (validate-only; never re-atomize).

**Must:** tag every atom with N:M `lens_tags` (zero, one, or many — never a single `home`); run Step 3 for zero-coverage required derivation lenses before Step 4; place every fact in exactly one non-drop chapter; keep chapter `anchor_lenses` a subset of `section_order`; before persisting `_body-{cid}.txt`, resolve every author-time `F-id` citation into a human-readable chapter reference (write-side discipline — `$INIT_COMPOSE_VALIDATE` does **not** scan for raw `F-id`; Eval owns residual checks); run `$INIT_COMPOSE_VALIDATE` before Return.
**Must not:** write a `fact:` or `section-key:` anchor into `$OUTPUT_DOC_PATH` (chapter anchors only — write-side / Eval; Step 6 does not substring-scan); invent a chapter with `derived_from` outside the outline-registry `candidates` set; decide open choices during Steps 2/3/4 (待决 same discipline).

### Step 2 — Atomize facts

**Branch A — inductive profile (`drafting.inductive=true`, K4):** discovery loop already wrote `_facts.json` (`seed-decision` / `settle-open`). **Do not** atomize `$SCOPE_REF_PATH`. Only validate:

```bash
$FACTS_CTL validate \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Missing / invalid `_facts.json` → Blocking (never re-atomize from scope). **Done:** validate exit 0 → proceed to Step 3.

**Branch B — deductive / non-inductive (`drafting.inductive` absent/false):**

1. **Materialize candidates** (exactly one branch; no new step number):
   - If `$SCOPE_FACTS_PATH` is non-empty → **Import**: read that `_facts.json`. For each upstream fact: assign a new contiguous local `F-n` (do not reuse upstream ids); keep `text` and `origin` (when present) verbatim; never carry upstream `lens_tags`. Match against this stage's Intent SSOT (`intent` else `desc`, `intent_boundary` when present): match → retag Plan `lens_tags` + `derivation.disposition="carried"`; no match → empty `lens_tags` + `derivation.disposition="quarantined"`. Always set `derivation.upstream_ref` to the upstream Design F-id(s).
   - Else if `$SCOPE_REF_PATH` is `decision-fact.json` → **Unit-import**: `$DECISION_FACT_CLAIM_CTL ensure`. Read units from `$SCOPE_REF_PATH`. For each unit pulled into this stage's lenses: `set-status --status claimed --by init` → emit a local fact `{text, origin:{type:seed, ref:[unit-id]}, lens_tags}` → `set-status --status settled --by init` (same pass). Units left unclaimed stay on the claim ledger (`check`); do not silently drop.
   - Else (`$SCOPE_FACTS_PATH` empty and `$SCOPE_REF_PATH` is prose) → **Atomize** `$SCOPE_REF_PATH` once (whole doc) — merge same-fact restatements into one atom; do not split by source section; a figure is one atom, kept intact. (Tags are applied in sub-step 2.)
2. **Tag / verify `lens_tags`:**
   - **Prose-line (Atomize):** for each atom, choose the set (zero, one, or many) of `section_order` keys whose intent the atom answers — using registry projection only. N:M: an atom may tag no lens (quarantine candidate, audited by Q1), one lens, or several.
   - **Fact-line (Import):** **verify-only** — check `derivation.disposition`↔`lens_tags` (`carried`⇔non-empty, `quarantined`⇔empty). Do **not** re-run match logic.
   - **Unit-import:** tag while importing (consumer lens map under I4); treat like Prose-line for Q1 quarantine rules.
3. **Persist** via `$FACTS_CTL write` (facts = JSON array `{id:F-n, text, lens_tags}` — optional `origin` / `derivation` for Import; optional `source` only for Step-3-derived facts later; Prose-line Step 2 atoms omit `source`/`derivation`; Unit-import carries `origin.type=seed` + `origin.ref=[unit-id]`):

```bash
$FACTS_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --facts-file "<path to facts JSON>"
```

4. `$FACTS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0.

**Import mis-match correction:** FreeEdit Tier A must **not** retag `lens_tags` / chapter placement to “fix” Import match vs quarantine. Correction path is FreeEdit Tier B — new revision, re-run Steps 2–6 (full re-Init).

**Done (Branch B):** `$REVISION_DIR/_facts.json` exists and validates — **Step 2 atoms only**; Step 3 may append derived facts before Step 4.

### Step 3 — Derive facts（演绎派生，仅有派生边的 required 视角）

Runs **between** Step 2 and Step 4. **Step 3 = AI semantic step + mechanical shell** (`$DERIVE_CTL`): CLI decides *which* lenses trigger and how ids append; **you** project work-item text from upstream **facts** (never prose).

**Must (CLI shell first):**
1. **Snapshot Step 2** (for audit): copy `$REVISION_DIR/_facts.json` → a temp `pre-derive-facts.json`.
2. **Plan triggers** (zero-only + topo order + true gaps):

```bash
$DERIVE_CTL plan \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Use stdout `order` (upstream-first). `true_gaps` → flag Round; do **not** invent. Partial coverage (`facts>0`) never appears in `triggered`. Cycle → Blocking (non-zero exit).
**If `order` is empty:** skip Emit / `$DERIVE_CTL append` / `$DERIVE_CTL audit`; run `$FACTS_CTL validate` only → Step 3 Done (no derivation lenses fired).
3. **Input:** for each `L` in `order`, read upstream facts from plan stdout `upstreams[L].upstream_facts` (or `$FACTS_CTL filter --revision-dir "$REVISION_DIR" --lens U` — no `--profile`). Optional code grounding when `$CODE_GROUNDING` is true. **Do not** read `_body` / `.md` prose.
4. **Emit (AI):** each work item → one object `{text, lens_tags:[L], source?}` (prefer upstream `F-id`s in `source`; freeform anchors allowed; no F-id integrity check). Undecided → embed `待决：…` in `text` (or a 待决 fact), never invent a choice. Write the array to a temp `derived.json`. Same-pass cascade: later lenses **see** facts you already decided for earlier lenses in `order`.
5. **Append once** (contiguous `F-(k+1)..`):

```bash
$DERIVE_CTL append \
  --revision-dir "$REVISION_DIR" \
  --derived-file "<path to derived.json>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

6. **Self-audit** (cascade-aware; Blocking on fail):

```bash
$DERIVE_CTL audit \
  --revision-dir "$REVISION_DIR" \
  --before-file "<path to pre-derive-facts.json>" \
  --triggered "<comma-separated order from plan>" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)"
```

Empty upstream → audit skips that lens; C1 at Step 6 is the backstop.
7. `$FACTS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0.

**Must not:** decide open choices; read prose; write facts for non-triggered lenses; strip/re-derive by `source` in-place (re-derive ⇒ full re-run — inductive: **Blocking** — return to inductive-runner to `seed-decision` / `settle-open` missing substance, then re-enter Init at Step 2 Branch A; do **not** run retired projection; deductive: re-run Step 2 then Step 3); skip `$DERIVE_CTL plan` when deriving; invent triggers or ids by hand. When `order` is non-empty, do not skip `append` / `audit`.

**Done:** `_facts.json` includes any Step-3-derived facts; when `order` was non-empty, `$DERIVE_CTL audit` exit 0; `$FACTS_CTL validate` exit 0.

### Step 4 — Organize chapters

- **Input:** `_facts.json` (compact index of `{id, text, lens_tags}` — never full prose; `lens_tags` is required here to derive each fact's `form_lens`) · outline-registry `candidates` (static, `{block, anchor_lenses}`) + `rules` (advisory merge/split/trim text) · `section_presence_map` (from section-registry `presence`, via `$FETCH_COMPOSE --role section-registry`).
- **Action (hybrid, semantic — AI, not script):** start from lens-anchored candidates; content-adaptively merge/split/drop/reorder using `rules` as heuristics and topic clustering as the north star. For each fact, assign exactly one chapter + one `form_lens` (∈ that fact's own `lens_tags` ∩ the chosen chapter's `anchor_lenses`) — priority-derive the placement using the placement heuristic (**content-kind memo, not a lens total order:** invariants > structure/contract > success > contact > context) as reference, not a mechanical lookup. A required lens with zero anchoring candidates is a modeling gap — do not silently drop it. An optional lens may legitimately end up with zero facts — do not fabricate content to fill it.
- **Output:** write `_chapters.json` (chapters = JSON array `{id, anchor_lenses, derived_from, op, facts:[{fid, form_lens}]}` only — `op` ∈ `keep|merge|split|drop`; `derived_from` cites the static `candidates[].block` id(s)):

```bash
$CHAPTERS_CTL write \
  --revision-dir "$REVISION_DIR" \
  --profile "$COMPOSE_PROFILE" \
  --project-root "$(pwd)" \
  --chapters-file "<path to chapters JSON>"
```

- `$CHAPTERS_CTL validate --revision-dir "$REVISION_DIR" --profile "$COMPOSE_PROFILE" --project-root "$(pwd)"` must exit 0 (structural shape only — L1/L3/L4/L5/C1 cross-file gates run at Step 6).
- **Done:** `$REVISION_DIR/_chapters.json` exists and validates; every fact with non-empty `lens_tags` is assigned to exactly one non-drop chapter.

### Step 5 — Write chapters (per non-`drop` chapter in `_chapters.json` order)

For each chapter, produce:

```text
_derive-{cid}.json   # {"display_title": "...", "lens_forms": [{"form_lens": "...", "carrier": "...", "structure": "...", "c": [{"d": "...", "c": "..."}]}]}
                     # (lens_forms is optional — one entry per distinct form_lens in this chapter, written at Step 5.2)
_body-{cid}.txt      # chapter prose (no H2 line, no anchor)
```

- **Input:** this chapter's `facts[]` (`{fid, form_lens}`) resolved against `_facts.json` · `section-form-registry` entries for each distinct `form_lens` (`{carrier, structure}`) · this chapter's `anchor_lenses`.
- **Action — five sub-steps in order, semantic (AI) unless noted:**
  1. **5.1 Group (mechanical):** partition this chapter's `facts[]` by `form_lens` — the highest-priority `anchor_lenses` entry (heuristic: invariants > structure/contract > success > contact > context) → primary-axis group; any other `anchor_lenses` entry's `form_lens` → cross-cut group (merged chapters only; single-anchor chapters have an empty cross-cut group). Step 4 already guarantees every fact's `form_lens` ∈ this chapter's `anchor_lenses` — do not place a fact under a `form_lens` outside that set.
  2. **5.2 Bind (semi-semantic — derived by priority rule, not free choice):** for each distinct `form_lens` ℓ present in this chapter, resolve `F_ℓ` `{carrier, structure}` from `section-form-registry[ℓ]` and `C_ℓ` (2–5 `(d,c)` pairs) from ℓ's `expression` + Role Fields + domain (F priority: `presentation` > domain `expression_conventions` > role `expressive_tendency` > intent text). **Required:** write `display_title` to `_derive-{cid}.json`. **Advisory (optional):** also write `lens_forms[]` (one entry per distinct `form_lens`) for observability — Step 6 / `append-chapter` only require `display_title`; omitting `lens_forms` still passes Init.
  3. **5.3 Arrange:** one orienting lead sentence derived from `anchor_lenses` intent + `covered_lenses` (`anchor_lenses` ∪ every placed fact's `lens_tags`); order the primary axis by priority; append cross-cut groups after the primary axis, bounded and clearly labeled — never interleaved into it.
  4. **5.4 Weave:** realize each group as prose under its own `F_ℓ`/`C_ℓ`; content ⊆ this chapter's `facts[]` — never invent a proposition. **Anchor fidelity:** carry each placed fact's `anchors` (§1.5 `compose-theory.md`) into the body — a `discovered` fact's anchors must appear (Step 6 L6 gate); do not replace an anchor token with a hypernym (see `init-draft-quality.md` § Anchor fidelity). While drafting, an author may cite another fact by `F-id`; before writing `_body-{cid}.txt` to disk, resolve every such citation into a human-readable chapter reference (e.g. "见「架构」章") — the persisted file must contain no raw `F-id` (write-side; not a Step 6 gate). Mark gaps with `> **待决：** …`. Write `_body-{cid}.txt` (no H2 line, no anchor).
  5. **5.5 Close (mechanical):** assemble into `$OUTPUT_DOC_PATH`:

```bash
$COMPOSE_DOC_CONTROL append-chapter \
  --path "$OUTPUT_DOC_PATH" \
  --chapter-id "{cid}" \
  --revision-dir "$REVISION_DIR"
```

- **Done:** `$OUTPUT_DOC_PATH` contains `<!-- chapter:{cid} -->` for this chapter with non-empty rendered content.

Chapter titles are flat `## {display_title}` from `_derive-{cid}.json`.

### Step 6 — Validate

1. Run `$INIT_COMPOSE_VALIDATE` (fact-first gate suite — L1/L3/L4/L5/C1 placement/coverage gates + chapter-artifact existence + assembly completeness + L6 fact-anchor coverage).
2. On failure → read stderr; route by gap type:
   - **C1 on a derivation lens** (required lens with `decompose`/`instantiate` edge still at zero facts) → **full re-run** (inductive: **Blocking** — return control to inductive-runner; add missing facts via `seed-decision` / `settle-open`, then re-enter Init Step 2 Branch A — never invoke retired `$INDUCTIVE_FACTS_PROJ project`; deductive: re-run Step 2 then Step 3 — do not patch in place) or flag Round;
   - **true coverage gap** (required, zero facts, **no** derivation edge) → Round / modeling fix — Step 3 will not invent;
   - **placement / candidate / L\*** issues → return to Step 4;
   - **L6 anchor coverage** (a `discovered` fact's anchor absent from its chapter body) → return to Step 5.4 and weave the missing anchor token into the body (do not weaken the anchor);
   - missing/empty chapter artifacts or missing chapter anchors → return to Step 5;
   then re-run Step 6.
3. On success → Return Summary.

**Done:** `$INIT_COMPOSE_VALIDATE` exit 0.

## Return Summary

```text
Initializing complete (fact-first display layer).
  Profile: <COMPOSE_PROFILE>
  Output: <OUTPUT_DOC_PATH>
  Facts: <REVISION_DIR>/_facts.json (<N> facts; Step 3 derived: <N>)
  Step 3: covered <M> required derivation lens(es); true gaps flagged: <ids or none>
  Chapters: <REVISION_DIR>/_chapters.json (<N> chapters, <N> dropped)
  Chapter artifacts: <REVISION_DIR>/_derive-*.json, _body-*.txt
  Quarantined facts (empty lens_tags, Q1 audit): <N> — <ids or none>
  Scope cross-check: <SCOPE_REF_PATH>
  Draft status: Initialized
  Next step: parent pause gate (options from profile drafting.post_init_options)
```
