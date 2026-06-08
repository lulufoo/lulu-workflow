---
version: 1
cycle_id: "{cycle_id}"
# Legend ref: lulu-dev-workflow/tech-plan/templates/20-tech-plan-spec-meta.md → ## Section Status Legend
# Section statuses: X | I | N/A-s | N/A-c | D | V | ! | S
# I     = seeded from decision-doc (Initializing) or re-opened by user (Reopen); has content, needs dialogue confirmation
# X     = skeleton placeholder only, no content yet
# N/A-s = not applicable: excluded by change type (structural)
# N/A-c = not applicable: excluded by decision-doc content analysis (content)
# !     = expired: user triggered Reopen on an upstream section; must re-review
sections:
  §1: X
  §2: X
  §3: X
  §4: X
  §5: X
  §6: X
  §7: X
  §8: X
  §9: X
  §10: X
# na_evidence: citable source for each N/A determination (populated by scoping-runner)
# Keys are sub-section granularity (e.g. §1.3, §4.5); top-level section status derived from strictest sub-section.
# N/A-s example: "Intent: 'add new feature' — keyword 'bugfix' or 'refactor' not found"
# N/A-c example: "decision-doc §Scope: 'no API contract changes; internal data layer only'"
na_evidence: {}
# reopen_reasons: populated when user triggers Reopen
# §N (re-opened section): user's stated reason
# downstream sections: "reopened: §N — <§N section title>"
reopen_reasons: {}
---
