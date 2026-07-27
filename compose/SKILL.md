---
name: compose
description: >-
  Profile-driven compose engine (facts / chapters / F·C), session control, start
  orchestration, drafting control, evaluation handoff, and delivery for structured
  document stages (lulu-design, lulu-plan, lulu-spec). Consumed by stage holder
  skills — holders declare identity (profile id, HARD-GATEs, produced
  document); all Drafting/Evaluating/Delivery orchestration lives here.
---

# compose

Shared compose engine consumed by stage holder skills (`lulu-design`, `lulu-plan`, `lulu-spec`). Holders declare their profile id and a HARD-GATE to Read this file in full; this engine owns the reusable orchestration, scripts, and schemas so holders stay thin.

Wherever this document says `<profile_id>`, substitute the calling holder's stage id (e.g. `lulu-design`).

`DEFAULT_COMPOSE_PROFILE_ID` (`lulu-plan`) is for kernel tests and `load_profile()` fallbacks only. Production invocations must pass `--profile` via the macros below.

## Compose profiles

Authoring SSOT: `{WORKFLOW_ROOT}/{stage}/compose-profile.json` (lulu-plan, lulu-design, lulu-spec). At session start, `start` writes `.compose-profile-path` under `{cache_subdir}/` pointing at that file. Runtime `load_profile()` resolves via the pointer when `project_root` and `cycle_id` are set; delivery/schema tools read the authoring file directly.

This engine reads `drafting.inductive` from the profile directly to conditionalize Drafting Step 0 below (static editorial configuration, not session state — direct SKILL reads are allowed for this field).

---

## Principles

**Blocking** — Cannot advance → stop, report (stderr / exit code), wait for user direction.

---

<HARD-GATE name="Plan Scope Constraints">
Before drafting or evaluation:

1. Run `$RESOLVE_PLAN_ROLE`.
2. Read stdout as authoritative **Plan Scope Constraints** (domain + role).

</HARD-GATE>

---

## start — Session-level, run before each compose document

**Start 1:** Identify active cycle — `_runtime.md` § Session Foundation. Do not run `$START_COMPOSE` until `$CYCLE_ID` is confirmed.

**Start 2:** Run `$START_COMPOSE`.

```bash
python3 "$SKILL_ROOT/compose/scripts/core/start.py" \
  --project-root "$(pwd)" \
  --cycle-id "<cycle_id>" \
  --profile <profile_id> \
  --profile-path "$SKILL_DIR/compose-profile.json" \
  [--carry-forward-ref "<absolute-path-to-previous-revision>"]  # optional, if this profile's adapter supports it
```

- `start.py` validates required upstream entries via this profile's `StartAdapter`, infers `run_mode` (`product` or `tech`) from cycle `delivered-refs.json`, then writes two per-revision artifacts: a frozen full copy of the cycle `delivered-refs.json` (audit baseline) and the resolver-materialized `resolved-refs.json` (scope/intent/norm); Initializing reads the resolved scope from the latter.
- **Run-mode inference is this profile's `StartAdapter.infer_run_mode`'s responsibility** — typically `product` when a valid `lulu-spec` entry exists, otherwise `tech`. Do not pass `--run-mode`; it is not a CLI parameter.
- On non-zero exit ("Gate blocked: ..." or a validation error list): tell the user which prior stage must be delivered first. Do not retry start.

To resume an in-progress document on the **same revision**, do not run start again — run `$SESSION_INFO --view session` (producer resume: `resolve-context` on the active revision).

To **abandon a partial revision** and begin fresh after fixes, run `$START_COMPOSE` again — it bumps `active_doc`, creates a new `revision{N}/`, and Drafting Step 0 (Inductive or Deductive) seeds a new state bundle there (prior revision artifacts remain on disk but are not read).

---

## Drafting Rules

**Entry:** Drafting Step 0 (producer) → Drafting Step 1 → Drafting Step 2; or Evaluating fix resume → Drafting Step 2; or resume via `$SESSION_INFO --view session`.
**Drafting states:** `[Inductive|Deductive →] Initialized → FreeEdit` — Inductive when `drafting.inductive` is `true`; Deductive when `false`.

### Drafting Step 0 — Producer facts

Always run — no opt-in prompt. Step 0.1 first; then exactly one of Step 0.2 / Step 0.3, branching on `drafting.inductive`.

#### Step 0.1 — Split into multi-subdesign slices (Lx package layout)

Required for `lulu-design` multi-subdesign packages (unified `revision/Lx/` layout; single-req = L1 only). **Do not** run `begin-inductive` until `$MULTI_SLICE check-split-ready` succeeds.

1. Resolve `<revision_dir>` from `$SESSION_INFO`.
2. `$MULTI_SLICE check-split-ready` — if ok, skip to step 4 (already locked).
3. Otherwise dispatch **split-runner** inline (not a subagent):

```text
Load {actual $SKILL_ROOT}/compose/split-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
REVISION_DIR=<revision_dir from $SESSION_INFO>
CYCLE_ID=$CYCLE_ID
COMPOSE_PROFILE=<profile_id>
```

   Locked trees are immutable this iteration — re-split means a new revision. Multi-L lock requires rulers; single-L rulers exempt.
4. `$MULTI_SLICE check-split-ready` — non-zero → Blocking.
5. **DAG + `$L_SLICE` (v1.1):** single session focus; switch only via `$L_SLICE switch --to <L> --confirm` (EnterPolicy: deps `inductive: done`). Per focus L, default pipeline is inductive → Init → FreeEdit → Evaluating → `$L_SLICE mark-done --kind production --confirm` (requires `## Boundary`). Sibling L may become `ready` in parallel; do not cut L inside inductive-runner. **Fact writes (multi-L):** split facts against locked rulers first; each fact must carry `home_l` (+ short `home_rationale`); `$FACTS_CTL write --target-l <home_l>` (G1 divert ok; demotes evaluated targets). Untagged writes hard-reject. Ambiguous ownership → rare human confirm. `home_l=package` only after human confirm with `--package-confirm`. Enter Evaluating only when StageGate passes (deps `production: done` — enforced by `$SESSION_CONTROL start-evaluating`). When all relevant L are `production: done` → `$MULTI_SLICE assemble-index --confirm` → `$L_SLICE seam-report` (advisory) → deliver with entry `design-index.md`.
6. `$L_SLICE resume` / `status` / `ready` — no illegal focus moves (hand-editing pointer JSON is forbidden).

CLI contracts: `$MULTI_SLICE --help`, `$L_SLICE --help`.

#### Step 0.2 — Produce facts inductively (only when `drafting.inductive` is `true`)

**Inductive-runner** is a human-driven gate spine (Shape → Grounding → Refine → Recompose → Provenance): AI recommends; the **user** closes each gate. Run **inline in this conversation**. **Exceptions (subagents via `$SUBAGENT_TOOL`, read-only):** deprecated G2 → `g2-grounding-runner`; G3 Class 1B → `g3-shallow-grounding-runner` (optional); G3 Class 2 → `g3-deep-grounding-runner` (optional).

1. Run `$DRAFT_CONTROL begin-inductive`. On failure → Blocking. On success → follow inductive-runner with stdout as `## Input`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
{begin-inductive stdout}
```

2. After G4 and G5 close, run `$DRAFT_CONTROL inductive-complete`. On failure → Blocking. `_facts.json` must exist (discovery-written).

#### Step 0.3 — Produce facts deductively (only when `drafting.inductive` is `false`)

**Deductive-runner** materializes upstream + completes lenses (intent ceiling + edge floor) + human confirm gate. Run **inline in this conversation** (interactive confirm — NOT a subagent).

1. Run `$DRAFT_CONTROL begin-deductive`. On failure → Blocking. On success → follow deductive-runner with stdout as `## Input`:

```text
Load {actual $SKILL_ROOT}/compose/deductive-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
{begin-deductive stdout}
```

2. After Steps 1–4 complete (confirm gate clear), run `$DRAFT_CONTROL deductive-complete`. On failure → Blocking. `_facts.json` must exist and pending must be clear.

### Drafting Step 1 — Initializing

Compose the document via fact-first Init (see initializing-runner). No mapping paste. Init **validate-only** on producer-written `_facts.json` — never Import/Atomize/Derive. `begin-init` hard-errors if the producer step did not complete or `_facts.json` is missing.

1. Run `$DRAFT_CONTROL begin-init`.
   - On failure → Blocking.
   - On success → dispatch initializing-runner (stdout → `## Input`):

```text
Load {actual $SKILL_ROOT}/compose/initializing-runner/SKILL.md and follow its instructions.

## Input
{begin-init stdout}
```

Await completion (`$SUBAGENT_AWAIT_SYNC`).

2. Run `$DRAFT_CONTROL init-complete`. On failure → Blocking.

3. **Pause gate:** Present runner return summary and the compose document path. Offer **only** the options listed in this profile's `drafting.post_init_options` (do not invent options absent from the list).
   - **freeedit** (when listed) → run `$DRAFT_CONTROL advance-to-freeedit`. On failure → Blocking. Proceed to **Drafting Step 2 — FreeEdit**.
   - **evaluate** (when listed) → **Evaluating Rules** below (skip FreeEdit).
   - **deliver** (when listed) → **ReadyForDelivery Rules** below (skip FreeEdit).
   - If `deliver` is listed without a prior Evaluating round in this revision, prefer routing the user to **evaluate** first (Eval is the delivery quality gate).
### Drafting Step 2 — FreeEdit

Entry: `advance-to-freeedit` success, or Evaluating fix resume.

- User drives edits; AI assists on request.
- Prefer **structured** edits over hand-editing the assembled compose `.md` (`.md` is a one-way projection):
  - **Tier A (same revision, presentation):** edit `_body-{cid}.txt` / `_derive-{cid}.json` (optionally sync existing fact `text` in `_facts.json`). Narrative-arc Init: visible group/leaf titles come from `_narrative-arc.json` via `$COMPOSE_DOC_CONTROL assemble-arc` (default `--lens-heading omit`); derive holds F/C (`form` / `expression_c`), not spine titles. Never use `_chapters.json` / `_lens-themes.json` / `_chapter-framework.json` / `_chapter-placement.json` (retired). Skip Drafting Step 0 / Drafting Step 1.
  - **Tier B (new revision, structure/facts topology):** do **not** patch chapter set / `lens_tags` in place — run `$START_COMPOSE` for a new revision, re-run Drafting Step 0 (producer) then Init (Steps 2–5). Leave Evaluating-fix-resume.
  - If the user insists on editing the assembled `.md`: warn that the next rebuild / new revision will overwrite; do not reverse-parse `.md` into JSON.
- When user signals done, ask using remaining `drafting.post_init_options` that still apply (typically Evaluate; Deliver only if listed and Evaluating already completed for this revision):
  - **Evaluate** → **Evaluating Rules** below.
  - **Deliver** (only if listed) → **ReadyForDelivery Rules** below.

---

## Evaluating Rules

Before handoff: for multi-L revisions, `$SESSION_CONTROL start-evaluating` enforces StageGate (deps of current focus must be `production: done`). On failure → Blocking; finish or re-evaluate predecessor L first (`$L_SLICE status` / `can-enter-evaluate`).

Read `{$SKILL_ROOT}/eval/eval-rules.md` and follow its instructions (only when the user explicitly chooses Evaluate).

When eval-rules completes, follow its exit branch:

- **Deliver** → **ReadyForDelivery Rules** below.
- **Continue editing** → enter **Drafting Step 2 — FreeEdit** (Evaluating fix resume; skip Drafting Step 0 / Drafting Step 1).

Dimension set, evaluation framework, and eval-mode branching (e.g. tech vs product mode dimension gating) are owned by `eval/eval-rules.md` and this profile's eval adapter — this engine performs a single handoff and does not enumerate dimensions.

---

## ReadyForDelivery Rules

1. Run `$SESSION_CONTROL ready-for-delivery`. On failure → Blocking.

2. Run `$SESSION_INFO --view delivery-preview`. On failure → Blocking. On success: show a delivery preview; full compose document only if asked.

3. Wait for explicit delivery confirmation.

4. Run `$SESSION_CONTROL deliver`. On failure → Blocking (including open stage-agenda blockers — resolve via `$AGENDA_CTL` then retry). On success → **Delivery Rules** below.

Stage-agenda items (design-external blockers/notes) live under the revision dir; orchestration: `$SKILL_ROOT/agenda/SKILL.md`. Humans must instruct writes; `deliver` mechanically lists blocking items.

## Delivery Rules

1. **Demand manifest (producer profiles only — those whose `compose-profile.json` declares a `demand_manifest` block):** enumerate the delivered document's demands per the block's `unit_rule` (one unit per the described decision granularity), each carrying its target `section` + a one-line `summary`; then run `$SESSION_CONTROL write-demand-manifest --units-json '<JSON array>'`. This atomization is the semantic step **you** perform — the script only mints ids, validates, and writes `<prefix>-demands.json` beside the delivered doc for a downstream stage's `intent_baseline`. Profiles without the block: skip this step (the script no-ops if called anyway). On failure → Blocking.

2. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. On success: prompt next stages when present.

---

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/split-runner/SKILL.md` | Drafting Step 0.1 — multi-subdesign split (intake → lock tree+rulers) |
| `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` | Drafting Step 0.2 — inductive-runner (`drafting.inductive: true`) |
| `{SKILL_ROOT}/compose/deductive-runner/SKILL.md` | Drafting Step 0.3 — deductive-runner (`drafting.inductive: false`) |
| `{SKILL_ROOT}/compose/inductive-runner/g2-grounding-runner/SKILL.md` | Drafting Step 0 — **deprecated** optional G2 topology subagent (prefer `attach-code-refs` in Class 2 processing) |
| `{SKILL_ROOT}/compose/inductive-runner/g3-shallow-grounding-runner/SKILL.md` | Drafting Step 0 — optional G3 shallow grounding subagent (detect facts only; parent `add-open`) |
| `{SKILL_ROOT}/compose/inductive-runner/g3-deep-grounding-runner/SKILL.md` | Drafting Step 0 — optional G3 deep grounding subagent (one open; parent settles) |
| `{SKILL_ROOT}/compose/inductive-runner/g4-recompose-runner/SKILL.md` | Drafting Step 0 — Gate 4 internal-audit subagent (section JSON + shape checkpoint) |
| `{SKILL_ROOT}/compose/inductive-runner/g5-provenance-runner/SKILL.md` | Drafting Step 0 — Gate 5 external-audit subagent (section JSON provenance) |
| `{SKILL_ROOT}/compose/initializing-runner/SKILL.md` | Drafting Step 1 — initializing-runner |
| `{$SKILL_ROOT}/eval/eval-rules.md` | Evaluating (user-initiated) |

---

## Script Macros

Macro expansion: `{$SKILL_ROOT}/_runtime.md` § Script Macros → Macro expansion. Non-zero exit → Blocking (Principles). Substitute `<profile_id>` with the calling holder's stage id.

Fetch compose framework templates on demand; **do not** read `workflow-config.json` directly. Scheme roles: `schemes/compose-template-scheme.json` (mapped per profile in `compose-profile.json` → `framework_templates`).

| Macro | Command |
|-------|---------|
| `$START_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/core/start.py" --project-root "$(pwd)" --cycle-id "$CYCLE_ID" --profile <profile_id> --profile-path "$SKILL_DIR/compose-profile.json"` |
| `$SESSION_INFO` | `python3 "$SKILL_ROOT/compose/scripts/core/session_info.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile <profile_id> --view <view>` |
| `$SESSION_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/core/session_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile <profile_id> <subcommand>` — drives outer session transitions via `compose/transitions/compose-session.json`; do not load that file directly |
| `$DRAFT_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/draft_control.py" --cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile <profile_id> <subcommand>` |
| `$INDUCTIVE_FACTS_PROJ` | `python3 "$SKILL_ROOT/compose/scripts/inductive/inductive_facts_projection.py"` (K4 retired — `project` fail-fast; facts written by discovery loop) |
| `$RESOLVE_PLAN_ROLE` | `python3 "$SKILL_ROOT/compose/scripts/scope/scope_resolver.py" --profile <profile_id> --project-root "$(pwd)" resolve-role --cycle-id "$CYCLE_ID"` |
| `$FETCH_COMPOSE` | `python3 "$SKILL_ROOT/compose/scripts/io/fetch_compose_framework.py" --role <role> --profile <profile_id> --project-root "$(pwd)" --cycle-id "$CYCLE_ID"` |
| `$EVAL_CONTROL` | `python3 "$SKILL_ROOT/eval/scripts/eval_entry.py" --workflow <profile_id> --cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>` |
| `$FIDELITY_EVAL_CONTROL` | `python3 "$SKILL_ROOT/compose/fidelity/scripts/fidelity_control.py" --revision-dir <revision_dir>` — compose-internal doc→facts gate (not stage Evaluating); see `compose/fidelity/README.md` |
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py" <subcommand> [args...]` |
| `$NARRATIVE_ARC_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/narrative_arc_control.py"` |
| `$CHAPTER_WRITE_STATE` | `python3 "$SKILL_ROOT/compose/scripts/section/chapter_write_state_control.py"` — Init 4.W claim-current gate: `sync` / `status` / `begin` (ticket) / `complete` (current) |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/init_compose_validation.py" validate --revision-dir <dir> --compose-doc <path> --profile <profile_id> --project-root "$(pwd)"` |
| `$AGENDA_CTL` | `python3 "$SKILL_ROOT/agenda/scripts/agenda_control.py" <subcommand> --project-root "$(pwd)" --cycle-id "$CYCLE_ID" --profile <profile_id> [args...]` — stage agenda; resolves `revision{N}` from session-state (see `$SKILL_ROOT/agenda/SKILL.md`) |
| `$MULTI_SLICE` | `python3 "$SKILL_ROOT/compose/scripts/core/multi_slice_control.py" --revision-dir <revision_dir> <subcommand>` — `check-root-facts` / `migrate-root-facts` / `write-intake` / `complete-intake` / `lock-tree` / `check-split-ready` / `assemble-index` |
| `$L_SLICE` | `python3 "$SKILL_ROOT/compose/scripts/core/discussion_pointer_control.py" --revision-dir <revision_dir> <subcommand>` — `status` / `resume` / `ready` / `can-admit` / `can-enter-evaluate` / `switch` / `mark-done` / `demote-production` / `seam-report` |
| `$FACTS_CTL` | `python3 "$SKILL_ROOT/compose/scripts/section/facts_control.py"` — `write` / `filter` / `validate` / `status` (multi-L: `write` requires `home_l`; package bucket needs `--package-confirm`) |

Subcommands and stdout: script module docstrings or `--help`.
