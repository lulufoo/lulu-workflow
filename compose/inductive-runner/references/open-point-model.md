# Open-point Model

## Purpose

Define the shared meaning of Open, Batch, Detect receipt, and loop state. These
objects describe unresolved work and its evidence without deciding substance.

## Open

An Open is one unresolved question that matters to the current slice.

- It records whether it came from human dialogue or AI detection.
- It belongs to one registry lens. It does not record KW altitude.
- Its blocking character states whether unresolved work prevents closure.
- `open` means unresolved.
- `settled` means its conclusion landed in facts.
- `deferred` means the human chose not to land it now.
- `rejected` means the question was false or outside the slice.
- Skipping preserves `open`; it changes only batch order.

## Batch

A Batch is an ordered, processable group of Opens.

- A Batch does not distinguish human and AI ownership.
- Open source remains an Open property.
- At most one Batch is active.
- New Opens join the active Batch tail.
- The first new Open creates a Batch when none is active.
- A Batch is completed when none of its members remains `open`.
- An abandoned Batch preserves its membership as history.

## Detect receipt

A Detect receipt is immutable evidence of one complete lens inspection.

- It binds the inspected facts, lenses, existing Opens, and the lens-frontier digest.
- It preserves the raw detection outcome and the final registered Open
  identities.
- A zero result means the raw detection produced no candidates.
- Removing every candidate after detection does not create a zero result.
- A receipt supports closure only while all bound inputs remain current.

## State invariants

- Loop state is `idle` or `processing`.
- `idle` has no active Batch or active Open.
- `processing` has one active Batch.
- An active Open, when present, belongs to the active Batch and remains `open`.
- One active Open never displaces another.
- Skipping moves the active Open to the Batch tail.
- Batch completion returns loop state to `idle`.
- A stale receipt proves no current coverage claim.

## Boundaries

This model owns shared semantics and invariants only. It does not define
orchestration, persistence, analysis methods, commands, or user interaction.
