---
name: clash
description: >-
  On-demand equal-footing collision: the user brings a view, question, or
  expectation and presses it against a named target. The assistant helps the
  user understand how things currently work, and — when it exists — surfaces
  the gap/contradiction between that status quo and the user's expectation.
  Does not assume the expectation is correct, invent friction, decide for the
  user, or persist findings. MANUAL TRIGGER ONLY. Use when: /clash, 碰撞,
  clash, 戳一下这个, 撬一下方案, stress-test this, probe this decision.
---

# clash

Equal-footing collision against something already on the table. The user
brings a probe; the assistant answers under verify-first discipline so the
user can see the status quo, and see any gap between that status quo and
their expectation.

## Purpose

1. **Help the user understand the status quo** — 帮助用户理解现状是怎么样的.
2. **Surface gaps/contradictions between status quo and the user's expectation** —
   暴露现状与用户预期之间的差距/矛盾.
   The user's expectation is not presumed correct; the point is to expose the
   gap when it exists, not to prove the user right or rewrite their expectation.

## Means

- The user names a target and brings a view, question, claim, or expectation
  against it (equal footing; not an AI-initiated audit).
- The assistant answers with verify-first honesty:
  - first help the user see the verified status-quo facts;
  - if a gap exists between user expectation and fact, fully surface the friction
    that gap creates — 充分暴露「用户预期 ↔ 事实」差距带来的摩擦;
  - **if no gap exists, only expose the facts** — do not invent friction.
- Default is one round; further rounds only if the user keeps probing.

## Principles

1. **Manual only** — 仅手动触发；无用户 probe 不自启.
2. **No invented friction** — 不编造摩擦；只陈述可核实的事实，及（若有）差距与矛盾.
3. **Expose over conclude** — 暴露优先于代用户下结论；不裁定「谁对」.
4. **Offer readings, don't decide** — 存在多读法/取舍时并列给出，不替用户做决定.
5. **Hand back, don't file** — 结果交还用户；不自动落盘.
6. **Self-correct when wrong** — 碰撞表明助手先前说法有误或过简时，诚实改口.

## Activation

- **Manual only.** User names a target and poses a challenge/question against it
  (`/clash`, 碰撞, or an explicit request to clash/stress-test).
- **Never self-activate.**
- Default one round; continue only while the user keeps probing.

## Pipeline

1. State plainly what is being tested (the target, in the user's own terms) and,
   when visible, what expectation the probe carries.
2. Answer under verify-first discipline:
   - Label claims ✅ (verifiable, cite source) / ⚠️ (inference — flag it) /
     ❌ (can't verify, say so).
   - Help the user see **how it currently works** (status-quo facts).
   - If expectation ↔ fact diverges, surface that gap/contradiction clearly.
   - If it does not, **state the verified facts only** — no friction theatre.
   - Offer multiple readings/trade-offs where they exist — do not decide for the user.
   - Self-correct if a prior assistant claim was wrong or oversimplified.
3. State the outcome explicitly: status-quo facts clarified; gap/contradiction
   exposed if any.
4. Hand the finding back as a plain statement. Do not file it anywhere automatically.
5. Close with one explicit line so the round does not trail off unresolved.

## Out of scope

- Does not gather new requirements (ordinary dialogue, not a clash).
- Does not reverse-probe the user's framing (see `lulu-brainstorm`).
- Does not persist findings into any store on its own.
- Does not redefine compose/brainstorm collision or probe logic — those stay independent.
- Does not invent friction when none exists.
