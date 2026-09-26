# Code Log — t{X}

> **Append-only** task action log. Header format: `### <ISO8601> · <action>[ · <target>]`.
> Actions: `enter` (phase name), `test_run` (`PASS|FAIL` in header), `git_commit` (`initial` | `amend`). Do not use red-run/green-run filenames.

---

### 2026-05-27T10:00:00Z · enter · WriteTests

### 2026-05-27T10:02:00Z · enter · VerifyRed

### 2026-05-27T10:02:30Z · test_run · FAIL

command: npm test
cwd: /abs/path/.cache/worktrees/slug/
exit_code: 1
duration_ms: 120

```output
FAIL …
```

### 2026-05-27T10:06:00Z · enter · WriteImpl

### 2026-05-27T10:10:00Z · enter · VerifyGreen

### 2026-05-27T10:10:30Z · test_run · PASS

command: npm test
cwd: /abs/path/.cache/worktrees/slug/
exit_code: 0
duration_ms: 95

```output
PASS …
```

### 2026-05-27T10:11:00Z · git_commit · initial

sha: a1b2c3d
message: feat(code): t1 …

### 2026-05-27T10:15:00Z · enter · Done
