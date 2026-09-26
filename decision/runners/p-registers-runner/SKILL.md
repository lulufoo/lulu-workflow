---
name: decision/p-registers-runner
description: Internal runner for the Decision P global gate.
meta-skill-version: 1.0.0
---

# p-registers-runner

Capture newly identified Prior, hard constraints, and Assumptions without
changing the active gate. Complete when the entries are committed.

## Prerequisites

<HARD-GATE>
1. Confirm an S1 occurred this turn.
2. Use the interrupted flow's `$CTX` to confirm one of:
   - Session is InProgress.
   - Session is Frozen after reopen, and P interrupts RS before `$RS_COMMIT`.
</HARD-GATE>

- Active gate unchanged — resume after P. Do not call `gate-close`.
- The Frozen exception resumes the interrupted RS confirmation; do not resume a
  spine gate.

## Classification

| Signal in dialogue | Log | Also log |
|--------------------|-----|----------|
| Confirmed fact / non-negotiable given | Constraint | — |
| Judgment about the problem or solution | Prior · `judgment` | — |
| Preference between options or approaches | Prior · `preference` | — |
| Worry, risk, or blocker | Prior · `concern` | — |
| Ruled-out option | Prior · `excluded` | — |
| Explicit or implicit unverified premise | Assumption | — |
| Prior resting on an unverified premise | Prior (matching kind) | Assumption for the premise |

Classify on intake. Unverified claims must not become Constraint. Do not rewrite a scanned risk into a Constraint.

Constraint revise/remove uses `revise` / `remove` on `C#`. RS does not edit or
delete `C#`.

## Confirm

Briefly confirm the proposed Prior, Constraint, and Assumption entries before
persistence.

## Act

1. Classify every S1 (Classification).
2. Confirm the proposed entries.
3. Run `$REGISTER_COMMIT` with the required append/update/revise/remove
   operations. Persist only through this call; do not hand-edit registers or
   chain register commands. `$REGISTER_COMMIT` cannot write `risks[]`.
4. Pin `$CTX` from stdout.

Return `P_COMPLETE`.

## register-commit

Append example:

```json
[
  {"action": "append", "kind": "prior", "payload": {"kind": "concern", "text": "..."}},
  {"action": "append", "kind": "constraint", "payload": {"text": "..."}},
  {"action": "append", "kind": "assumption", "payload": {"text": "..."}}
]
```

## Exit

`P_COMPLETE` or `P_FAILED reason=...`
