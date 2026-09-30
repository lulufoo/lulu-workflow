# Compose ontology

What a compose stage produces and how its parts relate. Loaded once by the
stage holder at Start. The holder uses it to read runner output and speak
with the user; judging facts, lenses, and presentation is the runners' work,
each from its own cognition units.

## Three layers

| Layer | Holds | Answers | Lives in |
|---|---|---|---|
| Substance | facts and their anchors | what is true in this stage | `_facts.json`, producer-written |
| Lens | intent, membership (`lens`), KW altitude | whose viewpoint owns a fact; how deep it must go | section registry, kw-criteria |
| Presentation | narrative arc, chapters, per-lens writing cognition | where and how substance is shown | `_narrative-arc.json`, form registry, the assembled document |

Invariant: substance carries no presentation. A fact carries one lens and is
rendered under that lens's charter; membership is stored,
rendering is applied at Write and never written back to the fact.

## Stance

Beside the layers sit two stage-level stances: Domain (what genre this stage
produces) and Role (who is writing). They shape how input is taken and how
chapters sound; they produce no facts.

## One execution, in order

```text
intake   cut the source into facts with lineage; the author's verdict on each
induce   ask what the facts do not state; a human decides; landed → facts
deduce   project known facts along lens edges into holes; leftovers → human
write    the arc places facts into chapters; chapters render facts per lens
eval     judge the document against intent, parent, and norm
```

Induce is optional per stage; deduce always runs. Every step reads and
writes the one stage-local fact set.

## Stage-local vs delivered

Within a revision, `_facts.json` is the substance every step reads. Across
stages the delivered document is the authority; the fact file is a process
artifact and travels nowhere.
