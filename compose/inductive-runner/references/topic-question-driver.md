> Part of inductive-runner · optional topic-local question contract

# Topic Question Driver

`topic-question-driver` is an optional, stateless cognitive tool for one
human-adopted Topic. It works toward complete closure of that Topic's remaining
design commitments.

It is not a Topic view, state machine, fact writer, or gate-exit mechanism.

## Goal

Within the `Closure target` established by the presented `topic-portrait`,
settled facts, and human-confirmed decisions, leave no design commitment
indeterminate and produce a `Topic Closure Candidate`.

The Goal directs repeated invocations; one invocation need not close the Topic.
Reaching it produces a candidate only — not human confirmation or gate close.

## Topic-local design gap

A **Topic-local design gap** is an unresolved design commitment inside the
current portrait's `Closure target`.

It is ephemeral. It is not a Topic in `gap` state, a Topic DAG node, a G3 open,
`gap_remaining`, or any persisted object.

## Preconditions and inputs

The current Topic must be human-adopted and its `topic-portrait` must already
have been presented.

Each invocation reads:

- induction context;
- settled facts;
- the current adopted Topic;
- the presented portrait's `Grounding`, `Closure target`, and `Boundary`;
- human-confirmed decisions visible in the current Topic dialogue.

The driver does not persist intermediate decisions. If required decisions are
not visible after a context or window transition, do not emit `Next Question`;
ask for a recap in ordinary dialogue. Do not reconstruct them from guesswork.

## Core principle

Use a **minimum-judgment / closure-review loop**:

1. Ask internally: *Within the current Closure target, what minimum design
   judgment is still required to close the current gap?*
2. Form one bounded candidate question for that judgment.
3. Apply `$SKILL_ROOT/shared/references/ask-protocol.md` to the candidate.
4. Deliver one `Next Question`.
5. After the user's answer, ask internally: *Did this decision close the gap?
   If not, what gap remains?*
6. Re-run from the current inputs until the Goal is met.

Question count is not predetermined. Remaining gap, not queue exhaustion, is
the stop condition.

## Outputs

Emit `Next Question` or `Topic Closure Candidate` when either applies. If the
remaining gap is not a real Topic-local design gap — missing or conflicting
input, or a question that would invent facts — do not emit a driver result;
say what is missing in ordinary dialogue.

No implementation hit alone does not withhold `Next Question`: Ask Protocol
permits noting that absence and continuing with a grounded recommendation.

### `Next Question`

Use when one real, evidence-supported minimum design judgment remains.

The question must carry these semantics without requiring a fixed display
template:

1. the current remaining gap;
2. the one minimum design judgment this question will settle;
3. project grounding directly relevant to that judgment — when an
   implementation surface exists, an openable location already read;
4. a self-contained question with explicit object, condition, and result;
5. exactly one recommended answer or option, with one-line rationale;
6. what design result becomes determinate after the judgment.

Apply Ask Protocol only after the candidate is bounded. Reuse the portrait's
Facts-first Grounding: settled target facts outrank project evidence, which
only locates the current state Domain `cognitive_frame` requires and
constrains the judgment. Question
language follows Domain `cognitive_frame` in the induction context.

### `Topic Closure Candidate`

Use when no Topic-local design gap remains inside the current `Closure target`.
Summarize the resulting Topic conclusion for the caller's existing
human-confirmation flow.

This result does not mutate Topic state, confirm a conclusion, produce facts,
or establish a gate-exit receipt.

## Constraints

- Do not persist driver state or intermediate decisions.
- Do not build a hidden queue or predetermine question count.
- Do not combine independent design judgments into one question.
- Do not repeat a judgment the user already answered.
- Do not write facts, current-Topic state, landscape receipts, or exit receipts.
- Do not adopt a Topic, confirm its conclusion, or close a gate.
- Do not prevent free dialogue, direct decisions, question rewrites, or
  interruption and later re-entry.

## Boundaries

- `topic-portrait` ([`topic-portrait.md`](topic-portrait.md)) establishes the
  adopted Topic's Grounding, Closure target, and Boundary.
- `topic-question-driver` optionally works its Topic-local design gap.
- The caller owns invocation, free-dialogue routing, conclusion confirmation,
  fact production, and exit.
- `/converge` is neither required nor invoked by this contract.
