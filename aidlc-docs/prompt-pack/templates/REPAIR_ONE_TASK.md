# Bounded repair prompt

```text
Repair only the defects listed by the reviewer for the assigned OsteoPatch task. First inspect the failing evidence and current diff. Reproduce the defect with a regression test before changing implementation. Preserve unrelated and concurrent work. Use the task’s original domain contracts and file boundary; do not broaden scope, weaken assertions, suppress errors, alter frozen scientific evidence, or fake a passing status.

Implement the smallest justified correction. Re-run the failing test, all task acceptance tests, and affected existing regressions. Record the actual command, terminal exit code, and candidate identity. After two unsuccessful attempts at the same failure, stop with the exact blocker and diagnostic evidence. Return a revised receipt and diff for independent review. Do not begin another task or publish/deploy the changes.
```
