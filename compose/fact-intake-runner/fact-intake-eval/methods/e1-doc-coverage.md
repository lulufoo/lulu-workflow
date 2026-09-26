# E1 — Doc → facts coverage (no weakening)

SoT (A) = Fact Intake source document (`scope_doc` / caller `$SOURCE_PATH`).
EvalTarget / RemediationTarget (B) = revision `_facts.json`.

## Contract

Every obligation unit from the input delivery doc must map to exactly one fact
disposition in `{carried, quarantined, not_needed}` (`derivation.disposition`
required on intake facts after Disposition).

For **carried** facts only: no weakening vs doc. Unitize doc via chapter anchors
and `##`/`###` headings (mixed); unstructured docs = whole doc + semantic
hard-contract scan.

Weakening (narrow list, blocking, carried only): quantity relaxations;
must/forbidden → optional; negative constraints removed; interface fields dropped.

`quarantined` / `not_needed` satisfy disposition coverage without requiring Plan
lens tags.

Remediate only `_facts.json`. Do not edit the SoT doc.
