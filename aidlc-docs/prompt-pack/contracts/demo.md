# Shared contract: demo

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

DemoRun contains run_id, session_id, dataset_version_id, allowlisted_image_ids, model_bundle_hash, code_sha, scenario_version, run_mode(live_local|live_deployed|verified_replay), asset_manifest_sha256, created_at_utc, and isolated_review_store_id. Every screen/export indicates its actual data scope and whether inference/attribution is live or precomputed replay. Synthetic test data is not displayed as real pathology data.

Create a fresh isolated demo review store from an approved pristine template. Never reset, clear, or overwrite the canonical 1,144-image research review DB or a shared production table. Restart creates a new demo session. Saved reviews must survive refresh within that session. Scope every new analytic view to that same session.

Curated scenarios: clear example; ambiguous score example; genuine prediction-versus-approved-reference disagreement; contrastive attribution. Each scenario points to a real permitted image and evidence. If no approved adjudication exists, say dataset-label disagreement, not confirmed model error. Never change a prediction to make the script compelling. Fixed example choices are disclosed as curated, not random/external validation.

Release gate separately records backend tests, frontend tests/build, fixture integration, real-data integration, actual browser journey, dependency/security review, and live deployment. PASS requires observed results for the stated code SHA. SKIPPED, BLOCKED, STALE, and NOT_RUN are not PASS. Real attribution execution and honest unavailable behavior are separate test outcomes.

Default additional cloud budget is USD 0. Preparing a deployment package is allowed; creating resources, synchronizing public assets, invalidating a CDN, deploying a Lambda/container, changing IAM, or publishing a release requires explicit authorization and valid scoped credentials. Never paste secrets into the chat or repository. UI-only deployment does not deploy new backend endpoints. Stop rather than serving an incompatible frontend/backend pair.
