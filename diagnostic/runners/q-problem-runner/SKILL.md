---
name: diagnostic/q-problem-runner
description: >-
  Q gate runner for diagnostic. Executes problem clarification dialogue and
  gate-close Q with incremental decision-doc write. Invoked by diagnostic/SKILL.md.
meta-skill-version: 1.0.0
---

# q-problem-runner

Execute **Q — Problem Clarification** within a diagnostic session. Mechanical persistence via `$GATE_CONTROL` and `$REGISTER_CONTROL`.

## Blocking policy

If any control CLI exits non-zero: **stop**, report the error, wait for user direction. Do not continue the gate dialogue.

## Prerequisites

<HARD-GATE>
Do NOT proceed until you have read `../../../_runtime.md`
</HARD-GATE>

- `$SKILL_DIR` = `$SKILL_ROOT/diagnostic`
- Gate contract: `$SKILL_DIR/gates/q-problem-clarification.md`

## Pipeline

1. `$GATE_CONTROL resolve-context` — pin stdout JSON as `$CTX`
2. `$GATE_CONTROL gate-activate --gate Q` (from open channel)
3. Execute Q gate dialogue (G1/G7/G8; G0 → `$REGISTER_CONTROL register-append --kind prior|assumption`)
4. After user confirms problem + constraints: `$GATE_CONTROL gate-close --gate Q --payload '<json>'`
5. Return `GATE_COMPLETE Q` to parent

## gate-close payload

```json
{
  "problem_statement": "<agreed problem>",
  "constraints": "<enumerated constraints>"
}
```

## Register capture (G0)

After brief confirmation:

```bash
$REGISTER_CONTROL register-append --kind prior --payload '{"kind":"preference","text":"..."}'
$REGISTER_CONTROL register-append --kind assumption --payload '{"text":"..."}'
```

- `--kind prior` — User Prior Log; payload `kind`: `judgment` | `preference` | `concern` | `excluded`
- `--kind assumption` — Assumption Log; unverified premises extracted from judgments

See parent `## Script Macros` and rule **G0**.

## Exit

On success:

```
GATE_COMPLETE Q
```

On failure:

```
GATE_FAILED Q reason=<brief description>
```
