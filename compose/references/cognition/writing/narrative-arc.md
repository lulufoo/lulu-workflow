> Compose cognition unit · loaded by the runner that names it.

# Narrative Arc

What the document spine is. Built once per revision; read by every writer
and renderer of that revision.

## Definition

1. The narrative arc is the document's reading order: a tree of groups and
   leaves whose titles name the stations of one through-line for the
   stage's audience.
2. A leaf holds facts; its chapters partition those facts by lens. The arc
   answers where a fact sits; the lens answers whose fact it is.
3. Titles name stations — an object, a surface, a behaviour area — never
   claims. Claims live in chapter bodies.
4. The arc is presentation, not substance. It invents no facts, stores no
   facts, and maps every settled fact exactly once.
5. The lens chain orders lenses; the arc orders chapters. An arc whose
   groups each hold one lens is a lens catalogue, not an arc.

## States

1. `mapped`: every fact is placed on a leaf; no chapters yet.
2. `write_ready`: every leaf is partitioned into chapters; writing may
   begin.

## Sample

One tree. Settled facts: `F-1` lens `CTX`, `F-2` lens `ST`. Both sit on one leaf. `mapped` is this tree with no `chapters`.

```json
{
  "version": "1",
  "kind": "narrative-arc",
  "status": "write_ready",
  "tree": {
    "id": "checkout",
    "title": "Checkout",
    "children": [
      { "id": "order-record", "title": "Order record" }
    ]
  },
  "leaves": [
    {
      "id": "order-record",
      "title": "Order record",
      "fact_ids": ["F-1", "F-2"],
      "chapters": [
        { "lens": "CTX", "fact_ids": ["F-1"] },
        { "lens": "ST", "fact_ids": ["F-2"] }
      ]
    }
  ]
}
```

- Group: `Checkout`. It is not a leaf and holds no facts.
- Leaf: `Order record`. `F-1` and `F-2` both sit here.
- Station: the titles `Checkout` and `Order record`.
- Chapter: `CTX`/`F-1` and `ST`/`F-2`.
- Splitting `Checkout` into a `CTX` group and an `ST` group would be a lens catalogue.
