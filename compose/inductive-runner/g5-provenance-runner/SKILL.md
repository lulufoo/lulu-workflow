---
name: g5-provenance-runner
description: Performs read-only provenance detection over current inductive facts and Opens.
---

# g5-provenance-runner

Analyze one supplied provenance context and return all detected deltas. Complete
with one structured result bound to the supplied digests.

## Inputs

Require one control-generated context containing:

- facts and Opens snapshots;
- scope content;
- intent-baseline content, which may be empty;
- norm-constraint content, which may be empty;
- demand metadata when available; and
- digests for all bound inputs.

Treat the supplied context as complete. Read
[`../../references/provenance-algorithm-semantics.md`](../../references/provenance-algorithm-semantics.md)
for A/B/C postures, axes, and bucket vocabulary.

## Analysis

### Axis 1

Group facts by `lens_tags`. For every lens group:

- **A — intent-baseline:** detect product-visible additions or conflicts under
  the default-deny posture.
- **B — scope:** detect contradictions with explicit scope decisions.
- **C — norm-constraint:** detect rule violations.

Use supplied Opens to resolve discovered origins and reuse related code
references. Skip A or C when its supplied upstream set is empty.

### Axis 2

After all lens groups:

- detect intent-baseline items not fulfilled anywhere;
- detect explicit scope decisions neither carried forward, elaborated, nor
  explicitly deferred;
- omit this axis for norm constraints.

When supplied demand metadata already marks an intent as deferred, omit that
intent. Do not infer deferral from Open fields.

## Output

Return:

- `echoed_digests`: every received input digest;
- `deltas`: structured findings grouped by upstream role, preserving axis,
  bucket, lens when applicable, upstream anchor, description, and supplied
  code references;
- `summary`: ran or skipped status and delta count for each role.

## Boundaries

- Remain stateless and read-only.
- Analyze only the supplied context.
- Do not read paths or hidden session state.
- Do not invoke controls or write traces.
- Do not interact with the user.
- Do not fix decisions, route findings, or collect sign-off.
- Failure has no side effects.

## Return

Return exactly one structured object. Echo all digests unchanged. Incomplete
analysis or malformed output is failure.
