> Compose cognition unit · loaded by the runner that names it.

# Provenance

Where a fact comes from. Needed only by producers — the runners that bring
facts into the set. Readers of facts do not load this unit.

## Origin

1. Every fact has exactly one `origin.type`, set at birth and never changed.
2. `seed`: declared directly from the intake source; no Open was involved.
   `ref` names the source scope.
3. `discovered`: one settled Open expanded into this fact. `ref` names the
   Open.
4. `derived`: deductive Derive projected this fact from upstream facts.
   `ref` names those facts; `derive_mode` says which pass made it, `floor`
   or `ceiling`.
5. Anchors follow origin: declared on a `seed` or `discovered` fact,
   inherited by a `derived` fact from the facts in its `ref`.

## Derivation

1. `derivation` is an intake fact's lineage to the source document.
   `upstream_ref` names the source units it was cut from.
2. `disposition` is the author's verdict on that input: `carried` enters
   this stage's substance and carries one lens; `quarantined` and
   `not_needed` stay out and carry none.
3. `not_needed` must cite one rule of the Role's `consume_policy`
   (`../profile/role.md`) by `rule_id`. Without a rule the verdict is
   `quarantined`, not `not_needed`.
4. Cut sets lineage; disposition sets the verdict. A fact cut without a
   verdict is unclassified, not carried.

## Judgment

1. Origin says how a fact was born; disposition says whether it was taken.
   Neither changes what the fact states.
2. Downstream reads carried facts as this slice's substance. Quarantined
   and not_needed facts are provenance records, not substance.
