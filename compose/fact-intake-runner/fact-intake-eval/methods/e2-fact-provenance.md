# E2 — Fact → doc provenance

SoT (A) = Fact Intake source document (`scope_doc` / caller `$SOURCE_PATH`).
EvalTarget / RemediationTarget (B) = revision `_facts.json`.

## Contract

Every fact (one unit per `F-n`) must have a locatable source span in the input
delivery doc (chapter/section/paragraph). Synonymous paraphrase allowed;
no-anchor guesses are failures.

Delete or weaken orphan facts in `_facts.json` only. Do not edit the SoT doc.

Run in parallel with E1; both gate Derive.
