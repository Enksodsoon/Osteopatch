# Independent review prompt

```text
Review only the assigned OsteoPatch task’s implementation. Do not edit product code during this review. Read the complete task prompt, its prerequisite acceptance receipts, the actual diff, and test evidence. Confirm the candidate SHA/diff identity matches the evidence. Re-run targeted checks in an isolated disposable environment where authorized.

Trace every acceptance-test ID to a real assertion. Inspect negative cases, authorization and scope intersections, model/image/review identity, stale requests, retries, null denominators, preserved frozen artifacts, and data-mode disclosures. Check that the code did not merely hide unsupported behavior behind a UI label. A passing fixture is not a real-data, real-attribution, WSI, or deployment pass.

Reject unrelated rewrites, invented metrics/approvals, unsafe credential handling, automatic new training, live writes to the canonical research store, and tests weakened to pass. For UI work inspect the actual rendered result and at least one error and small-screen state.

Return ACCEPT or REQUEST_CHANGES for this task only. For each defect provide severity, exact file/location, reproduction steps, expected behavior, and the smallest test that would expose it. Distinguish a bug from a separately gated future feature. Do not accept based on the implementer’s summary alone. Do not merge or start another task.
```
