> Compose cognition unit · loaded by the runner that names it.

# Lens

What a lens is, and how a stage's lenses connect into one chain.

## Lens

1. A lens is a viewpoint that owns a subset of substance. It decides which
   facts belong to it, not how they are shown.
2. `intent` is the lens's inclusion charter: what substance belongs here.
3. `intent_boundary` is its exclusion list: substance named there belongs
   to other lenses and is never authored under this one.
4. Each fact carries one lens. Choose it from the fact's source context: the
   document section it was cut from, or the Open it landed from. If context
   still leaves several lenses, choose the lens whose intent is closest to the
   fact. Whether to split a fact is decided by the fact standard, not here.
   Storage keeps `lens_tags` as an array; one lens is a producer constraint,
   not a storage shape.
5. A lens is neither a chapter nor a writing style. Membership is stored;
   presentation is applied later, per lens.

## Lens chain

1. A stage's lenses form one ordered chain declared by its section
   registry: `section_order` gives the order, each lens's `upstream` gives
   the lenses it builds on. Each `upstream` link is one edge of the chain.
2. `upstream` points only to earlier lenses in the order. A downstream lens
   presupposes its upstream substance and does not restate it.
3. `intent_boundary` names where a lens hands substance off; `upstream`
   names what it builds on. Together they place one lens in the whole.
4. The chain orders lenses, not chapters. Chapter order is decided later by
   the narrative arc.
