---
name: clash
description: >-
  On-demand equal-footing stress test of an existing artifact, decision, or
  claim. The user brings a view, claim, or fact and presses it against a named
  target; the assistant answers honestly under verify-first discipline so
  friction exposes inner defects — not so the claim feels safer. Does NOT
  self-start an audit, does NOT decide for the user, and does NOT persist the
  finding. MANUAL TRIGGER ONLY. Use when: /clash, 碰撞, clash, 戳一下这个,
  撬一下方案, stress-test this, probe this decision.
---

# clash

The user tests something already on the table. They bring a view, claim, or
fact and press it against that target — equal footing with the assistant —
to create friction that exposes inner defects.

## Core Principles

1. **User's probe tests the target** — 用户用自己的观点/信息测试事物（非 AI 自启）
2. **Friction exposes defects** — 制造摩擦以暴露内在缺陷，不造假缺陷
3. **Honest response makes friction inescapable** — 诚实应答让摩擦不可逃避
4. **Expose over conclude; hand back, don't file** — 暴露优先于下结论；结果交还，不自动落盘

## Activation

- **Manual only.** User names a target and poses a challenge/question against it
  (`/clash`, 碰撞, or an explicit request to clash/stress-test).
- **Never self-activate.** The assistant does not start a clash without the user's probe.
- Default is one round; further rounds only if the user keeps probing the same or another target.

## Pipeline

1. State plainly what is being tested (the target, in the user's own terms).
2. Answer the user's probe under this discipline:
   - Verify before concluding: label claims ✅ (verifiable, cite source) /
     ⚠️ (inference — flag it, stay open to challenge) / ❌ (can't verify, say so).
   - Inference is allowed only when flagged and re-questionable.
   - Offer multiple readings/trade-offs where they exist — do not decide for the user.
   - Self-correct honestly if the clash shows a prior assistant claim was wrong or oversimplified.
3. State the outcome explicitly: a gap, tension, or over-design was exposed — or
   explicitly state none was found and the target holds up.
4. Hand the finding back as a plain statement. Do not file it anywhere automatically —
   the user decides where (if anywhere) it should land.
5. Close with one explicit line so the round does not trail off unresolved.

## Out of scope

- Does not gather new requirements (ordinary dialogue, not a clash).
- Does not reverse-probe the user's framing (see `lulu-brainstorm`).
- Does not persist findings into any store on its own.
- Does not redefine compose/brainstorm collision or probe logic — those stay independent.
