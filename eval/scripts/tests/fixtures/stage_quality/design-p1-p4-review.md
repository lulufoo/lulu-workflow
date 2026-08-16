---
schema_version: 3
dimension_id: solution-quality
round_token: round-1
---

# Tech Review — solution-quality | revision1 round 1

**Date:** 2026-08-04
**Refs:** controlled local Method/SoT fixture

| ID | root_cause | handling_mode | sot_ref | location | severity | evidence | description | status | decision | resolution |
|----|------------|---------------|---------|----------|----------|----------|-------------|--------|----------|------------|
| solution-quality-P1-intent-1 | WO-ERROR | direct | lulu-dev-workflow/lulu-design/eval/sots/solution-quality.md#P1 | intent#1 | critical | `The service must behave appropriately.` | P1 — semantic drift: the behavior cannot be restated without guessing. | pending | — | |
| solution-quality-P2-admission-1 | WO-ERROR | direct | lulu-dev-workflow/lulu-design/eval/sots/solution-quality.md#P2 | admission#1 | critical | `required security level` | P2 — boundary unclear: the required level is not defined. | pending | — | |
| solution-quality-P3-interface-1 | WO-ERROR | direct | lulu-dev-workflow/lulu-design/eval/sots/solution-quality.md#P3 | interface#1 | critical | `The public interface is gRPC.` | P3 — logic chain broken: prior chapters do not derive the interface choice. | pending | — | |
| solution-quality-P4-recovery-1 | WO-ERROR | direct | lulu-dev-workflow/lulu-design/eval/sots/solution-quality.md#P4 | recovery#1 | critical | `recovery is handled appropriately` | P4 — boundary unanswerable: recovery actions and outcomes are not specified. | pending | — | |
