# Shared contract: teaching

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

TeachingReference is distinct from a model suggestion: item_id, image_id, approved_label, explanation_text, hint_steps, source_refs, approved_by, approved_at_utc, content_version, status(draft|approved|retired). Without approval, display only a draft to faculty; do not score a learner against an AI-generated label. Reuse actual images with known redistribution rights.

TeachingAttempt fields: attempt_id, learner_alias, project_id, exercise_version, item_id, answer, submitted_at_utc, reveal_at_utc nullable, feedback_version. Model answer, original dataset label, correctness, hidden hints, and answer-bearing metadata must not appear in learner API responses before their release stage. Hiding CSS is insufficient. Student attempts are not reviewer/adjudication events.

Demo educational sessions use aliases and isolated session IDs, not real patient identifiers. An answer submission is explicit and idempotent; drafts are not scores. Deterministic assignments are versioned. Difficulty labels based on model ambiguity say model-ambiguity tier, not proven learner difficulty. Quiz performance does not establish clinical competence or educational superiority.

The assistant is a deterministic approved-content navigator first: answer only supported FAQs and application actions using allowlisted structured intents. No model-generated morphology explanations, diagnosis, treatment advice, shell commands, external network requests, or autonomous write actions. Unknown questions return a bounded unsupported response.
