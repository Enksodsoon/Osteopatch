# One-task executor prompt

Copy one complete file from tasks/ into a new agent session. The complete task already contains its guardrails and output contract. Prepend the paragraph below only to make task assignment explicit:

```text
Implement only the task contained below in the existing OsteoPatch Review checkout. Read its prerequisites and inspect current files before changing anything. Preserve uncommitted work and use an isolated task-owned checkout. Reuse and verify existing behavior rather than rebuilding it. Do not start another task, install a dependency, spend money, train a model, publish, merge, deploy, or schedule a worker without separate explicit authorization. Return the exact tests, terminal results, focused diff, and task receipt, then stop. If a prerequisite is missing, name it and report BLOCKED.
```

Do not paste all 129 prompts together. Do not substitute the task title for the full prompt. Do not provide credentials in chat.
