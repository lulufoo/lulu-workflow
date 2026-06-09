# Section State Legend

States used in `section-progress.md` → `sections` map.

## Status Table

| Status  | Name             | Description                                                       |
|---------|------------------|-------------------------------------------------------------------|
| `X`     | Skeleton         | Placeholder only, no content yet                                  |
| `I`     | Initialized      | Has content seeded or re-opened; needs dialogue confirmation      |
| `D`     | In-Dialogue      | Currently being drafted in active dialogue session                |
| `V`     | Verified         | User confirmed the section content; complete                      |
| `!`     | Expired          | Upstream section re-opened; must re-review in new context         |
| `N/A-s` | N/A (structural) | Not applicable: excluded by change type                           |
| `N/A-c` | N/A (content)    | Not applicable: excluded by decision-doc content analysis         |
| `S`     | Skipped          | User confirmed N/A during SkipConfirming step                     |

## Lifecycle Order

    X / I  →  D  →  V
                ↑
                !  (re-review trigger)

    N/A-s / N/A-c  →  S

## Notes

- `D` is transient: only one section is `D` at a time; interruption rewrites it back to `X` or `I`.
- `!` propagates downstream: when a `V` section is re-opened, all downstream `V` sections become `!`.
- `S` is terminal: a skipped section will not be revisited unless explicitly restored to `X`.
