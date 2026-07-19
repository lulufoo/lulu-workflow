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

To resume an in-progress document on the **same revision**, do not run start again — run `$SESSION_INFO --view session` (Inductive resume: `resolve-context` on the active revision).

To **abandon a partial revision** and begin fresh after fixes, run `$START_COMPOSE` again — it bumps `active_doc`, creates a new `revision{N}/`, and Drafting Step 0 Inductive seeds a new state bundle there (prior revision artifacts remain on disk but are not read).

---

## Drafting Rules

**Entry:** Drafting Step 0 (if enabled) → Drafting Step 1 → Drafting Step 2; or Evaluating fix resume → Drafting Step 2; or resume via `$SESSION_INFO --view session`.
**Drafting states:** `[Inductive →] Initialized → FreeEdit` — Inductive only when this profile's `drafting.inductive` is `true`.

### Drafting Step 0 — Inductive (only when `drafting.inductive` is `true` for this profile)

Anchor the upstream scope doc in code before composing. Always run when enabled — no opt-in prompt. Profiles with `drafting.inductive: false` skip directly to Drafting Step 1.

**Inductive-runner** is a human-driven gate spine (Shape → Grounding → Refine → Recompose → Provenance): AI recommends; the **user** closes each gate. Run the gate spine **inline in this conversation** (same as `/decision` gate runners). **Exceptions (subagents via `$SUBAGENT_TOOL`, read-only, no user interaction):** deprecated G2 → `g2-grounding-runner`; G3 Class 1B → `g3-shallow-grounding-runner` (optional); G3 Class 2 → `g3-deep-grounding-runner` (optional). All leanings, EP registration, and gate closes stay inline; subagents cannot interact with the user.

1. Run `$DRAFT_CONTROL begin-inductive`.
   - On failure → Blocking.
   - On success → read the runner SKILL and follow its gate spine **interactively in this conversation**, with `begin-inductive` stdout as its `## Input`:

```text
Load {actual $SKILL_ROOT}/compose/inductive-runner/SKILL.md and follow its instructions in this conversation (interactive, human-driven — NOT a subagent).

## Input
{begin-inductive stdout}
```

2. After the gate spine completes (G4 recompose and G5 provenance both closed), run `$DRAFT_CONTROL inductive-complete`. On failure → Blocking. After inductive-complete, `_facts.json` must already have been written by the discovery loop (seed / settle-open); `begin-init` will validate it exists. Maturity ledgers under `revision{active_doc}/inductive-scope/` are not Init prose input.

### Drafting Step 1 — Initializing

Compose the compose document via fact-first Init (see initializing-runner Steps 1–6). No mapping paste. Init reads **`_facts.json`**, not `inductive-scope/*.json` prose. When `drafting.inductive` is true (K4), the discovery loop must have written `_facts.json` first — `begin-init` hard-errors if it is missing; initializing-runner then skips its Step 2 atomization and validates the facts. The upstream scope doc is a **completeness cross-check only**.

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
  - **Tier A (same revision, presentation):** edit `_body-{cid}.txt` / `_derive-{cid}.json` (optionally sync existing fact `text` in `_facts.json`); validate; rebuild the compose doc via `$COMPOSE_DOC_CONTROL init-doc` then per-chapter `append-chapter` in `_chapters.json` order. Skip Drafting Step 0 / Drafting Step 1.
  - **Tier B (new revision, structure/facts topology):** do **not** patch chapter set / `lens_tags` in place — run `$START_COMPOSE` for a new revision (initializing-runner Steps 2–6). Leave Evaluating-fix-resume.
  - If the user insists on editing the assembled `.md`: warn that the next rebuild / new revision will overwrite; do not reverse-parse `.md` into JSON.
- When user signals done, ask using remaining `drafting.post_init_options` that still apply (typically Evaluate; Deliver only if listed and Evaluating already completed for this revision):
  - **Evaluate** → **Evaluating Rules** below.
  - **Deliver** (only if listed) → **ReadyForDelivery Rules** below.

---

## Evaluating Rules

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

4. Run `$SESSION_CONTROL deliver`. On failure → Blocking. On success → **Delivery Rules** below.

## Delivery Rules

1. **Demand manifest (producer profiles only — those whose `compose-profile.json` declares a `demand_manifest` block):** enumerate the delivered document's demands per the block's `unit_rule` (one unit per the described decision granularity), each carrying its target `section` + a one-line `summary`; then run `$SESSION_CONTROL write-demand-manifest --units-json '<JSON array>'`. This atomization is the semantic step **you** perform — the script only mints ids, validates, and writes `<prefix>-demands.json` beside the delivered doc for a downstream stage's `intent_baseline`. Profiles without the block: skip this step (the script no-ops if called anyway). On failure → Blocking.

2. Run `$SESSION_INFO --view stage-transitions`. On non-zero exit → Blocking. On success: prompt next stages when present.

---

## Reference documents

| Document | When |
|----------|------|
| `{SKILL_ROOT}/compose/inductive-runner/SKILL.md` | Drafting Step 0 — inductive-runner (`drafting.inductive: true` profiles only) |
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
| `$COMPOSE_DOC_CONTROL` | `python3 "$SKILL_ROOT/compose/scripts/section/compose_doc_control.py" <subcommand> [args...]` |
| `$INIT_COMPOSE_VALIDATE` | `python3 "$SKILL_ROOT/compose/scripts/section/init_compose_validation.py" validate --revision-dir <dir> --compose-doc <path> --profile <profile_id> --project-root "$(pwd)"` |

Subcommands and stdout: script module docstrings or `--help`.
