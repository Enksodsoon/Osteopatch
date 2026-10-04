Using AI-DLC, continue only U3 after confirming G3 and the unit code-generation plan are approved. Read docs/08_data_and_api_contracts.md and the U3 task.

Build the local React/FastAPI/SQLite workflow using the actual approved model: curated gallery, asynchronous job status, all three scores, and accept/correct/defer with persistent history. Source labels and immutable predictions must remain separate. Do not expose benchmark labels in normal reviewer responses.

Test failures first, including unknown image IDs, failed/stale jobs, duplicate requests, stale revisions and persistence after restart. Test fixtures must never silently become demo predictions. Label local demo identity clearly and bind development to loopback.

Run backend/frontend/end-to-end tests and demonstrate a saved review after restart. Commit, record actual evidence and present G4. No cloud resources, arbitrary uploads or automatic training. Stop at the gate.
