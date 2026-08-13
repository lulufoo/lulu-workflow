---
name: compose
description: >-
  Internal compose engine; load only via stage holder HARD-GATE — do not invoke directly.
---

# compose

Shared compose engine consumed by stage holder skills (`lulu-arch`, `lulu-blueprint`, `lulu-design`, `lulu-plan`, `lulu-spec`). Holders bind the engine Inputs and HARD-GATE to Read this file in full; this engine owns the reusable orchestration, scripts, and schemas so holders stay thin.

## Inputs

| Variable | Required | Source | Use |
|---|---|---|---|
| `$CYCLE_ID` | yes | Holder runtime foundation | Active cycle |
| `$PROFILE_PATH` | yes | Holder | Runtime `compose-profile.json` |

---

## Session bootstrap

Start compose when directed by the holder, then load the active session context.

### Start

Confirm Inputs, then run `$START_COMPOSE`.

### Bind context

Run `$SESSION_INFO --view session`, then bind:

| Cite | JSON field | Use |
|------|------------|-----|
| `$INDUCTIVE` | `pipeline.inductive` | Split / Working route |
| `$CODE_GROUNDING` | `pipeline.code_grounding` | Writing / Deductive runner Input |
| `$POST_WRITING_OPTIONS` | `pipeline.post_writing_options` | Pause / FreeEdit options |
| `$DEMAND_MANIFEST` | `demand_manifest` | Delivery Rules producer atomization (`unit_rule`); skip when null |
| `$ROLE_PROMPT` | `role.role_prompt` | Scope Constraints persona |
| `$REVISION_DIR` | `revision_dir` | revision-scoped tools and runner Input |

### Scope constraints

Before producer / evaluation work:

1. Treat `$ROLE_PROMPT` as authoritative **Scope Constraints** (persona).

---

## Split Rules

**Session state:** `$START_COMPOSE` lands in **`Split`**. Topology lock is revision-level; single-req still locks an explicit **L1** tree. No `split-skip`.

1. Use `$REVISION_DIR`.
2. `$MULTI_SLICE check-split-ready` — if ok, go to step 6.
3. **Scope-package already converted** (primary `$SCOPE_REF` is `scope-package.json`): L topology was locked at start via convert — do **not** soft-split or hard-mirror. Non-zero check-split-ready → **Blocking**.
4. **Deductive hard-mirror** (when `$INDUCTIVE` is `false` and primary `$SCOPE_REF` is compose `*-package.json`, not `scope-package.json`):
   - Present the package `order` / titles (no cut edits). Human confirms once.
   - `$MULTI_SLICE lock-hard-mirror --package-path <absolute SCOPE_REF> --confirm`
   - Missing / invalid package / missing slice docs → **Blocking** (return upstream to re-deliver). Do **not** fall back to soft split-runner.
5. **Inductive soft split** (only when `$INDUCTIVE` is `true`) dispatch **split-runner** inline (not a subagent):

```text
Load {actual $SKILL_ROOT}/compose/split-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
REVISION_DIR=$REVISION_DIR
CYCLE_ID=$CYCLE_ID
```

   Human confirms stay on existing intake / `lock-tree --confirm`. Locked trees are immutable this iteration — re-split means a new revision. Multi-L lock requires rulers; single-L rulers exempt.
6. `$MULTI_SLICE check-split-ready` — non-zero → Blocking.
7. `$SESSION_CONTROL split-complete` — Split → Working. On failure → Blocking.

**Done:** workflow-state `current_state=Working` and check-split-ready exits 0.

CLI: `$MULTI_SLICE --help`, `$SESSION_CONTROL` (`split-complete`).

---

## Working Rules

**Session state:** `Working` after Split Rules (`split-complete`).

**Shape:** N L each hold an independent sub-state (`by_id[Lx].phase` + `intake`/`acceptance`); **one focus thread** (sibling L may be `ready` in parallel — that is not parallel editing). Steps below run **only on the current focus L**.

```text
Split → Working
loop (single focus):
  Inductive|Deductive → Writing → FreeEdit → Evaluating → Accept L
       → (suggested next ready) human --confirm → switch → continue loop
       → (all L accepted) leave Working
→ ReadyForDelivery → Delivered
```

### L-slice scheduling

Pointer maturity (`pending|done`): `intake` = Inductive|Deductive closed; `acceptance` = Accept L closed. Per-L `phase`: `pending|in_progress|evaluating|accepted`. Not Split intake slots.

- Single focus; switch only via `$L_SLICE switch --to <L> --confirm` (EnterPolicy: deps `intake: done`).
- Per focus L: Inductive|Deductive → Writing → FreeEdit → Evaluating → `$L_SLICE accept-l --confirm` (requires `## Boundary`). Optional `--switch` to suggested next ready L (human confirm; never auto-switch).
- Fix L: `$L_SLICE fix-l --confirm` or `$SESSION_CONTROL resume-after-eval` (evaluating → in_progress; same L) → **FreeEdit**.
- Do not cut L inside inductive-runner.
- **Fact writes (multi-L):** split facts against locked rulers first; each fact must carry `home_l` (+ short `home_rationale`); `$FACTS_CTL write --target-l <home_l>` (G1 divert ok; demotes accepted targets). Untagged writes hard-reject. Ambiguous ownership → rare human confirm. `home_l=package` only after human confirm with `--package-confirm`.
- Enter evaluating only when StageGate passes (deps `acceptance: done` — `$SESSION_CONTROL start-evaluating`); also requires locked topology and focus `intake: done`.
- `$L_SLICE resume` / `status` / `ready` — no illegal focus moves (hand-editing pointer JSON is forbidden).
- skip-eval is forbidden.

CLI: `$L_SLICE --help`. `$L_STEP --help` (per-L step machine).

### Inductive (only when `$INDUCTIVE` is `true`)

**Hard gate:** `$L_STEP begin-inductive` requires session `Working` and locked topology.

**Inductive-runner** dispatches shared `fact-intake-runner`, then a human-driven gate
spine (Shape → Topic Loop → Refine → Recompose → Provenance): AI recommends; the
**user** closes each gate. Run **inline in this conversation**. **Subagent
exceptions via `$SUBAGENT_TOOL`:** (a) **read-only** — G3 Class 1B →
`g3-shallow-grounding-runner` (optional); G3 Class 2 → `g3-deep-grounding-runner`
(optional); (b) **Topic Loop arc rebuild** — `narrative-arc-runner` (unified
`write_ready` arc to caller `OUTPUT_PATH`, optional Viewer mount). Do not treat
(b) as grounding.

1. Run `$L_STEP begin-inductive`. On failure → Blocking. On success → follow inductive-runner with stdout as `## Input`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
{begin-inductive stdout}
```

2. After G4 and G5 close, run `$L_STEP inductive-complete`. On failure → Blocking. `_facts.json` must exist (intake + discovery).

### Deductive (only when `$INDUCTIVE` is `false`)

**Hard gate:** `$L_STEP begin-deductive` requires session `Working` and locked topology.

**Deductive-runner** dispatches shared `fact-intake-runner`, then completes lenses
(intent ceiling + edge floor) + human pending confirm. Run **inline in this
conversation** (interactive confirm — NOT a subagent).

1. Run `$L_STEP begin-deductive`. On failure → Blocking. On success → follow deductive-runner with stdout as `## Input`:

```text
Load {actual $SKILL_ROOT}/compose/deductive-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
{begin-deductive stdout}
```

2. After Steps 1–4 complete (confirm gate clear), run `$L_STEP deductive-complete`. On failure → Blocking. `_facts.json` must exist and pending must be clear.

### Writing

Compose the document via fact-first Writing (see writing-runner). No mapping paste. Writing **validate-only** on producer-written `_facts.json` — never Import / fact-intake / Derive. `begin-writing` hard-errors if the producer step did not complete or `_facts.json` is missing.

1. Run `$L_STEP begin-writing`.
   - On failure → Blocking.
   - On success → Load writing-runner and follow its instructions
     (stdout → `## Input`):

```text
Load {actual $SKILL_ROOT}/compose/writing-runner/SKILL.md and follow its instructions.

## Input
{begin-writing stdout}
```

2. Run `$L_STEP writing-complete`. On failure → Blocking.

3. **Pause gate:** Present runner return summary and the compose document path. Offer **only** `$POST_WRITING_OPTIONS` (do not invent options absent from the list).
   - **freeedit** (when listed) → run `$L_STEP advance-to-freeedit`. On failure → Blocking. Proceed to **FreeEdit**.
   - **evaluate** (when listed) → **Evaluating** below (skip FreeEdit).
   - **deliver** (when listed) → only if every L is already accepted; else prefer **evaluate**. Then **Leave Working** / **ReadyForDelivery Rules**.
   - If `deliver` is listed without Accept L for this focus, prefer **evaluate** first.

### FreeEdit

Entry: `advance-to-freeedit` success, or Fix L resume.

- User drives edits; AI assists on request.
- Prefer **structured** edits over hand-editing the assembled compose `.md` (`.md` is a one-way projection):
  - **Tier A (same revision, presentation):** edit `_body-{cid}.txt` (optionally sync existing fact `text` in `_facts.json`). Narrative-arc: visible group/leaf titles come from `_narrative-arc.json` via `$COMPOSE_DOC_CONTROL assemble-arc` (default `--lens-heading omit`). Writing cognition (What) is disclosed on the Writing/`chapter-write-runner` path via `$CHAPTER_WRITE_STATE begin.writing_cognition`; Fix-L body edits do **not** require re-running claim-current. Never use `_chapters.json` / `_lens-themes.json` / `_chapter-framework.json` / `_chapter-placement.json` (retired). Skip Inductive|Deductive / Writing.
  - **Tier B (new revision, structure/facts topology):** do **not** patch chapter set / `lens_tags` in place — run `$START_COMPOSE` for a new revision, re-run Inductive|Deductive then Writing. Leave Fix-L resume.
  - If the user insists on editing the assembled `.md`: warn that the next rebuild / new revision will overwrite; do not reverse-parse `.md` into JSON.
- When user signals done, ask using remaining `$POST_WRITING_OPTIONS` that still apply (typically Evaluate; Deliver package only if listed and all L already accepted):
  - **Evaluate** → **Evaluating** below.
  - **Deliver** (only if listed) → **Leave Working** only when all L are accepted; otherwise Blocking / continue the L loop.

### Evaluating

Before handoff: `$SESSION_CONTROL start-evaluating` requires locked Split topology, then StageGate (deps of current focus must be `acceptance: done`). On failure → Blocking; fix topology / finish or re-evaluate predecessor L (`$L_SLICE status` / `can-enter-evaluate`). See **L-slice scheduling**.

Eval paths are per focus L: `{revision}/{L}/evaluate-state.md` and `{revision}/{L}/evaluate{M}/` (legacy revision-root sessions keep root paths until they end). `$EVAL_CONTROL` obtains those absolute paths via `$EVAL_HANDOFF` (`request-handoff`) on every control command — do not derive L directories in Eval or stage adapters.

Read `{$SKILL_ROOT}/eval/SKILL.md` and follow its instructions (only when the user explicitly chooses Evaluate).

When Eval completes, follow its exit branch:

- **Accept L** → `$L_SLICE accept-l --confirm` (optional `--switch` to suggested next). If all L accepted → **Leave Working**. Otherwise stay in Working and continue the L-slice loop on the next focus.
- **Fix L** → `$L_SLICE fix-l --confirm` (or `$SESSION_CONTROL resume-after-eval`) → **FreeEdit** (skip Inductive|Deductive / Writing).
- **Deliver package** → only when all L are accepted → **Leave Working**. Partial Accept must not route here.

Dimension set, evaluation framework, and eval-mode branching (e.g. tech vs product mode dimension gating) are owned by `eval/SKILL.md` and this profile's eval adapter — this engine performs a single handoff and does not enumerate dimensions.

### Leave Working

When every L is `phase=accepted`:

1. `$MULTI_SLICE assemble-package --confirm` → `$L_SLICE seam-report` (advisory).
2. Proceed to **ReadyForDelivery Rules** (delivery marker: `document.filename` `*-doc.md` → `*-package.json`; `deliver` also writes/records the same marker).

---

## ReadyForDelivery Rules

1. Run `$SESSION_CONTROL ready-for-delivery`. On failure → Blocking.

2. Run `$SESSION_INFO --view delivery-preview`. On failure → Blocking. On success: show a delivery preview; full compose document only if asked.

3. Wait for explicit delivery confirmation.

4. Run `$SESSION_CONTROL deliver`. On failure → Blocking (including open stage-agenda blockers — resolve via `$AGENDA_CTL` then retry). On success → **Delivery Rules** below.

Stage-agenda items (design-external blockers/notes) live under the revision dir; orchestration: `$SKILL_ROOT/agenda/SKILL.md`. Humans must instruct writes; `deliver` mechanically lists blocking items.

## Delivery Rules

1. **Demand manifest (only when `$DEMAND_MANIFEST` is present):** enumerate the delivered document's demands per `$DEMAND_MANIFEST.unit_rule` (one unit per the described decision granularity), each carrying its target `section` + a one-line `summary`; then run `$SESSION_CONTROL write-demand-manifest --units-json '<JSON array>'`. This atomization is the semantic step **you** perform — the script only mints ids, validates, and writes `<prefix>-demands.json` beside the delivered doc for a downstream stage's `intent_baseline`. When `$DEMAND_MANIFEST` is null: skip this step (the script no-ops if called anyway). On failure → Blocking.

2. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. On success: prompt next stages when present.

---

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/split-runner/SKILL.md` | Split Rules — multi-subdesign split (intake → lock tree+rulers) |
| `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` | Working → Inductive — inductive-runner (`$INDUCTIVE: true`) |
| `{SKILL_ROOT}/compose/deductive-runner/SKILL.md` | Working → Deductive — deductive-runner (`$INDUCTIVE: false`) |
| `{SKILL_ROOT}/compose/fact-intake-runner/SKILL.md` | Deductive Step 1 / Inductive Fact Intake — shared doc→`_facts.json` |
| `{SKILL_ROOT}/compose/narrative-arc-runner/SKILL.md` | Working → Inductive G2 / Writing — unified narrative-arc pipeline |
| `{SKILL_ROOT}/compose/chapter-write-runner/SKILL.md` | Working → Writing Step 5 — chapter write + assemble |
| `{SKILL_ROOT}/compose/inductive-runner/g3-shallow-grounding-runner/SKILL.md` | Working → Inductive — optional G3 shallow grounding subagent (detect facts only; parent `add-open`) |
| `{SKILL_ROOT}/compose/inductive-runner/g3-deep-grounding-runner/SKILL.md` | Working → Inductive — optional G3 deep grounding subagent (one open; parent settles) |
| `{SKILL_ROOT}/compose/inductive-runner/g4-recompose-runner/SKILL.md` | Working → Inductive — Gate 4 internal-audit subagent (section JSON + shape checkpoint) |
| `{SKILL_ROOT}/compose/inductive-runner/g5-provenance-runner/SKILL.md` | Working → Inductive — Gate 5 external-audit subagent (section JSON provenance) |
| `{SKILL_ROOT}/compose/writing-runner/SKILL.md` | Working → Writing — writing-runner |
| `{$SKILL_ROOT}/eval/SKILL.md` | Working → Evaluating (user-initiated) |

---

## Script Macros

Macro expansion: `{$SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion. Non-zero exit → Blocking: stop, report (stderr / exit code), wait for user direction.

Fetch compose framework templates on demand; **do not** read `workflow-config.json` directly. Scheme roles: `schemes/compose-template-scheme.json` (mapped per profile in `compose-profile.json` → `framework_templates`).

| Macro | Command |
|-------|---------|
| `$START_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/core/start.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID" --profile-path "$PROFILE_PATH"` |
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` — session transitions (`split-complete` / `start-evaluating` / …) via `compose/transitions/compose-session.json`; do not load that file directly |
| `$L_STEP` | `python3 "$SKILL_ROOT/compose/scripts/section/l_step_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$INDUCTIVE_FACTS_PROJ` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_facts_projection.py"` (K4 retired — `project` fail-fast; facts written by discovery loop) |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$EVAL_HANDOFF` | `python3 "$SKILL_ROOT/compose/scripts/core/eval_handoff_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` — Compose→Eval context (`request-handoff` / `commit-artifacts` / `commit-evaluate-state` / `discard-staging`); Eval entry requests this per command |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/core/compose_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" -- <subcommand>` — passthrough stage `compose-profile.json.eval` to Eval |
| `$FACT_INTAKE_EVAL_CTL` | `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-intake-eval/scripts/fact_intake_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" -- <subcommand>` — Fact Intake Eval (doc→`_facts.json`); independent of delivery Evaluating; `completion_mode=return_to_caller` |
| `$ATOMIZE_EVAL_CONTROL` | Same command as `$FACT_INTAKE_EVAL_CTL` (retired name; prefer `$FACT_INTAKE_EVAL_CTL`): `python3 "$SKILL_ROOT/compose/fact-intake-runner/fact-intake-eval/scripts/fact_intake_eval_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" -- <subcommand>` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py" <subcommand> [args...]` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/narrative-arc-runner/scripts/narrative_arc_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_write_state_control.py"` — chapter-write-runner claim-current gate: `sync` / `status` / `begin` (ticket + writing_cognition + lens_intent) / `complete` (current) |
| `$WRITING_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/writing_compose_validation.py" validate --revision-dir "$REVISION_DIR" --compose-doc <path> --project-root "$(pwd)"` |
| `$AGENDA_CTL` | `python3 "$SKILL_ROOT/agenda/scripts/agenda_control.py" <subcommand> --project-root "$(pwd)" --cycle-id "$CYCLE_ID" [args...]` — stage agenda; resolves `revision{N}` from session-state (see `$SKILL_ROOT/agenda/SKILL.md`) |
| `$MULTI_SLICE` | `python3 "$SKILL_ROOT/compose/scripts/core/multi_slice_control.py" --revision-dir "$REVISION_DIR" --project-root "$(pwd)" <subcommand>` — see `--help` (`lock-hard-mirror` / `assemble-package` / …) |
| `$L_SLICE` | `python3 "$SKILL_ROOT/compose/scripts/core/discussion_pointer_control.py" --revision-dir "$REVISION_DIR" --project-root "$(pwd)" <subcommand>` — `status` / `resume` / `ready` / `can-admit` / `can-enter-evaluate` / `switch` / `mark-done` / `accept-l` / `fix-l` / `demote-acceptance` / `seam-report` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` — `write` / `validate` / `status` (multi-L: `write` requires `home_l`; package bucket needs `--package-confirm`) |

Subcommands and stdout: script module docstrings or `--help`.
