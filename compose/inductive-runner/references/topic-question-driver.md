> Part of inductive-runner · optional topic-local question contract

# Topic Question Driver

## Goal

Ask this Topic's remaining commitments to closure and produce a
`Conclusion Candidate`. A Topic-local gap is one unresolved
commitment in the `Closure target`: ephemeral, not persisted.

## Preconditions

The Topic is human-adopted. Its `topic-portrait` has been presented.

## Inputs

Each invocation reads the induction context, settled facts, the adopted
Topic, the presented portrait's `Grounding`, `Closure target`, and `Boundary`,
and human-confirmed decisions visible in the current Topic dialogue.

## Core principle

Use a **minimum-judgment / closure-review loop**:

1. Ask internally: *Within the current Closure target, what minimum
   judgment is still required to close the current gap?*
2. Form one bounded candidate question for that judgment.
3. Apply `$SKILL_ROOT/shared/references/ask-protocol.md` to the candidate.
4. Deliver one `Next Question`.
5. After the user's answer, ask internally: *Did this decision close the gap?
   If not, what gap remains?*
6. Re-run from the current inputs until the Goal is met.

Remaining gap, not queue exhaustion, is the stop condition.

## Outputs

Emit `Next Question` or `Conclusion Candidate` when either applies.
If a judgment cannot be formed — missing or conflicting input, or a
question that would invent facts — do not emit a driver result; say
what is missing in ordinary dialogue.

No implementation hit alone does not withhold `Next Question`: Ask Protocol
permits noting that absence and continuing with a grounded recommendation.

### Next Question

Use when one real, evidence-supported minimum judgment remains.

The question must carry:

1. the current remaining gap;
2. the one minimum judgment this question will settle;
3. project grounding directly relevant to that judgment — when an
   implementation surface exists, an openable location already read;
4. what result becomes determinate after the judgment.

Reuse the portrait's Facts-first Grounding. Question language follows
Domain `cognitive_frame` in the induction context.

### Conclusion Candidate

Use when no Topic-local gap remains inside the current `Closure target`.
Summarize the resulting Topic conclusion for the caller's existing
human-confirmation flow.

## Constraints

- Do not persist driver state or intermediate decisions.
- Do not build a hidden queue or predetermine question count.
- Do not combine independent judgments into one question.
- Do not repeat a judgment the user already answered.
- Do not write facts, current-Topic state, landscape receipts, or exit receipts.
- Do not adopt a Topic, confirm its conclusion, or close a gate.
- Do not prevent free dialogue, direct decisions, question rewrites, or
  interruption and later re-entry.

## Boundaries

- `topic-portrait` ([`topic-portrait.md`](topic-portrait.md)) owns Grounding,
  Closure target, and Boundary.
- The caller owns invocation, free-dialogue routing, conclusion confirmation,
  fact production, and exit.
- `/converge` is neither required nor invoked by this contract.
