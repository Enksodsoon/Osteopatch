# Shared contract: enterprise

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

Reuse the existing enterprise modules rather than creating a second role system. Existing seeded-email login is a demo identity provider, not production authentication. Shared/public use requires a trusted identity provider, secure session handling, and live server-side project membership checks. Never make a shared deployment public-write merely to simplify a demo.

Define permissions by capability, not UI visibility: student learning only; reviewer review read/write; pathologist adjudicate and research batch sign-off; researcher permitted analytics/exports; model engineer registry work under approval; auditor permitted audit reads; administrator project membership/configuration. The exact installed role enum is authoritative; unsupported proposed roles require additive migrations and tests, not silent string aliases. A role in project A grants no privileges in project B.

Every protected read, count, file, annotation, search, download, task, report, or mutation resolves its parent project and intersects membership with the permitted dataset/allowlist/session. Unauthorized object IDs produce the same response as absent objects where existence would leak. Recheck membership on the server, not just stale JWT claims. Bind audit actor to authenticated identity, not a caller-supplied reviewer field.

Registry transitions and rollback affect a versioned serving pointer only after artifact/evaluation/approval checks. Registry metadata called serving is not proof the actual inference worker loads those bytes; verify pointer-to-loaded-hash correspondence. Record promotion/rollback as append-only events. Audit hash chains provide tamper evidence only within their anchoring/trust model, not magical tamper-proof storage.

Backups are tested by restoration into an isolated location. Retention/deletion requires an explicit approved policy, a dry run, and preservation of frozen research/legal retention needs. No automatic deletion, changing repository visibility, cloud/IAM mutation, messages to users, or external notification delivery without task-specific authorization.
