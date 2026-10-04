Using AI-DLC, prepare U5 using only the approved architecture and exact AWS account/region. Read docs/04_architecture_security_cost.md. First write/review IaC, permission requirements, service/usage limits, current price assumptions, retention and a project-owned resource inventory. No cloud mutation until explicit G6A approval.

Use short HTTP requests and a separate bounded model worker, authenticated authorized review APIs, private storage, transactional/idempotent review events and real versioned model artifacts. Avoid permanent GPU/SageMaker endpoints, NAT, RDS, OpenSearch, paid LLMs and purchased domains unless separately authorized. Budget alerts alone are not a hard cap.

Run local template/container tests and show the exact stack/change set. If G6A is absent or permission/budget unresolved, stop deployment and retain the local app. Do not broaden IAM or switch accounts automatically.

After explicit G6A, deploy only that stack and verify live HTTPS, auth rejection/acceptance, real inference, job retry/timeout behavior, history, cache provenance and timings. Report actual success or failure, remaining resources and cost visibility limits. Present G6B, update state/audit and stop.
