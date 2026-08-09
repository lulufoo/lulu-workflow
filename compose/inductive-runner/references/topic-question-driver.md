> Part of inductive-runner · optional topic-local question contract

# Topic Question Driver

`topic-question-driver` is an optional, stateless cognitive tool for one
human-adopted Topic. It works toward complete closure of that Topic's remaining
design commitments.

It is not a Topic view, state machine, fact writer, or gate-exit mechanism.

## Goal

Within the current induction context, settled facts, and human-confirmed
decisions, leave no design commitment in the adopted Topic indeterminate and
produce a `Topic Closure Candidate`.

The Goal directs repeated invocations; one invocation need not close the Topic.
Reaching it produces a candidate only — not human confirmation or gate close.

## Topic-local design gap

A **Topic-local design gap** is an unresolved design commitment inside the
current adopted Topic.

It is ephemeral. It is not a Topic in `gap` state, a Topic DAG node, a G3 open,
`gap_remaining`, or any persisted object.

## Preconditions and inputs

The current Topic must be human-adopted and its `topic-portrait` must already
have been presented.

Each invocation reads:

- induction context;
- settled facts;
- the current adopted Topic and its presented portrait;
- human-confirmed decisions visible in the current Topic dialogue.

The driver does not persist intermediate decisions. If required decisions are
not visible after a context or window transition, return `Blocked` and request
a recap; do not reconstruct them from guesswork.

## Core principle

Use a **minimum-judgment / closure-review loop**:

1. Ask internally: *What minimum design judgment is still required to close
   the current gap?*
2. Form one bounded candidate question for that judgment.
3. Apply `$SKILL_ROOT/shared/references/ask-protocol.md` to the candidate.
4. Deliver one `Next Question`.
5. After the user's answer, ask internally: *Did this decision close the gap?
   If not, what gap remains?*
6. Re-run from the current inputs until the Goal is met or progress is blocked.

Question count is not predetermined. Remaining gap, not queue exhaustion, is
the stop condition.

## Outputs

Return exactly one result per invocation.

### `Next Question`

Use when one evidence-supported minimum design judgment remains.

The question must carry these semantics without requiring a fixed display
template:

1. the current remaining gap;
2. the one minimum design judgment this question will settle;
3. project grounding directly relevant to that judgment;
4. a self-contained question with explicit object, condition, and result;
5. exactly one recommended answer or option, with one-line rationale;
6. what design result becomes determinate after the judgment.

Apply Ask Protocol only after the candidate question is bounded. Grounding
locates and constrains the design judgment; implementation detail must not
replace design-level boundary, state, contract, or observable-result language.

### `Topic Closure Candidate`

Use when no Topic-local design gap remains under the current inputs. Summarize
the resulting Topic conclusion for the caller's existing human-confirmation
flow.

This result does not mutate Topic state, confirm a conclusion, produce facts,
or establish a gate-exit receipt.

### `Blocked`

Use when required input is missing or conflicting, or a question would require
invented facts. State what prevents safe progress.

No implementation hit alone is not a blocker: Ask Protocol permits noting that
absence and continuing with a grounded recommendation.

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

- `topic-portrait` establishes the adopted Topic's context and framing.
- `topic-question-driver` optionally works its Topic-local design gap.
- The caller owns invocation, free-dialogue routing, conclusion confirmation,
  fact production, and exit.
- `/converge` is neither required nor invoked by this contract.
