# R risk classification

Use during R `prepare` to classify the complete assumption table. This reference
defines row semantics only; R owns persistence and exit selection.

## Row invariant

- Every row has `risk_level`, `risk_class`, `risk_state`, and
  `risk_consequence`.
- A non-risk row uses `none` for the first three fields;
  `risk_consequence` may be empty or `—`.

## Draft defaults

- H / M → `risk_state=open`
- L → `risk_state=ignore`
- The user may override a draft at expose confirm.

## Classification

| Field | Values | Meaning |
|-------|--------|---------|
| `risk_level` | H | Failure seriously undermines or overturns the delivered decision. |
| `risk_level` | M | Failure requires a significant adjustment without necessarily overturning the decision. |
| `risk_level` | L | Failure has limited, absorbable execution impact. |
| `risk_class` | `decision` | Risk concerns the decision itself. |
| `risk_class` | `implementation` | Risk concerns later implementation. |
| `risk_class` | `pending` | Class is not yet judged. |
| `risk_class` | `none` | Row is not a risk. |

## Delivery gate

`risk_class` is a judgment label only. Only `risk_state=open` blocks `exit=dc`.
