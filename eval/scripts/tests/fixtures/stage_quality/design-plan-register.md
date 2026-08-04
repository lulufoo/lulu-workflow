# Design Direction

<!-- chapter: direction -->

The design separates command parsing from command execution so that the
interaction boundary remains testable.

## Implementation Tasks

- [ ] Update `src/commands.py`.
- [ ] Run: `pytest tests/test_commands.py`.
