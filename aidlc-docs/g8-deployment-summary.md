# G8 — AWS Deployment / Hackathon Demo Release · summary

**Date:** 2026-10-04 (UTC) · **Status:** G8 — DEPLOYED DEMO REVIEW REQUIRED
(deployed + live-validated; awaiting owner review). **Region:** us-east-1 ·
**Account:** 153485202811 (workshop). Deployed from the already-certified G7 app;
no retraining / no new modeling. **50-image representative subset** only.

> **The deployed hackathon demo contains a deterministic 50-image representative
> subset. The complete locally verified collection contains 1,144 patches.**
> The model/evaluation evidence remains based on the frozen G4 artifacts, not on
> these 50 deployed images.

## Live URL
- **CloudFront (public demo):** https://dgv0wpd8tglrw.cloudfront.net
- API Gateway (origin): https://wx414e64ja.execute-api.us-east-1.amazonaws.com

## AWS architecture
- **Frontend:** static React build in private S3 `osteopatch-web-153485202811`,
  served via **CloudFront** (OAC; bucket private). SPA.
- **Backend:** FastAPI as a **Lambda container image** `osteopatch-api`
  (PackageType=Image, 3008 MB, 90 s timeout; torch + pytorch-grad-cam baked;
  serve path lazy-torch) behind an **API Gateway v2 HTTP API**. CloudFront routes
  `/v1/*` to the API.
- **Review state:** **DynamoDB on-demand** `osteopatch-reviews` (thin adapter over
  the same repo interface; prediction immutable; append-only review_event with
  revision + idempotency). SQLite path preserved locally via env selector.
- **Runtime assets:** recovered model + the 50 TIFFs + 50 thumbnails in private
  S3 `osteopatch-artifacts-153485202811` (read by the Lambda role; never public).
- IaC: CDK under `app/g6/deploy/` (stack `OsteoPatchG8`).

## Deployed resources
- CloudFormation stack: `OsteoPatchG8`
- Lambda: `osteopatch-api` (image, 3008 MB / 90 s)
- API GW HTTP API: `wx414e64ja`
- CloudFront distribution: `EIKXG771OD6Q8` → dgv0wpd8tglrw.cloudfront.net
- DynamoDB: `osteopatch-reviews` (+ `idem-index` GSI)
- S3: `osteopatch-web-153485202811` (frontend, private OAC),
  `osteopatch-artifacts-153485202811` (assets, private)
- ECR: image via CDK `cdk-hnb659fds-container-assets-153485202811-us-east-1`

## 50-image subset
- Deterministic selection: 6 persisted anchors (all 3 classes + high/low priority +
  the VIABLE↔NECROSIS confusion case `Case-3-A18-41817-26873` + a NON_TUMOR
  example) then filled to 50 by the app's review-priority order. Persisted:
  `runtime-artifacts/recovery/g8-subset-image-ids.json`.
- Covers Case-3 / Case-4 / Case-48 / P9 groups; all three predicted classes.

## Upload (actual)
- TIFFs uploaded: **50** → `s3://osteopatch-artifacts-153485202811/images/` (11.7 MiB)
- Thumbnails uploaded: **50** → `.../thumbnails/` (5.4 MiB)
- Total ≈ **17.1 MiB**. 0 failures. Bucket private (OAC); no public read/write.

## Backend health
`GET /v1/health` → `{model_version: baseline-frozen-g4, bundle 01727fb8…,
images_indexed: 50, predictions: 50}`. `GET /v1/images` → total 50, items 50.

## Live validation (all 15 PASS, against the CloudFront URL)
1 Workbench loads ✓ · 2 50 real thumbnails ✓ · 3 review-priority sort ✓ · 4 patch
opens ✓ · 5 three model scores ✓ · 6 attribution panel loads ✓ · 7
suggested-vs-runner-up Grad-CAM (VIABLE vs NECROSIS, live torch Lambda) ✓ · 8
NECROSIS vs VIABLE direction (hint flips, overlay recomputes) ✓ · 9 ACCEPT (control
present) ✓ · 10 CORRECT saved → persisted ✓ · 11 DEFER (control present) ✓ · 12
history persists after reload (patch shows "Reviewed", history #1) ✓ · 13 export
(`/v1/exports/reviews` → 50 rows, the CORRECT present, model baseline-frozen-g4) ✓ ·
14 model-attribution disclaimer visible ✓ · 15 behavioral-recovery disclosure
visible ✓. DynamoDB write path (UI→APIGW→Lambda→DynamoDB) proven; demo review
cleaned afterward (reviews table back to 0 → pristine demo state).

## Screenshots (real, from CloudFront) — runtime-artifacts/evidence/g8/screenshots/
A-deployed-workbench.png · B-deployed-review-screen.png · C-deployed-attribution.png ·
D1-deployed-viable-vs-necrosis.png · D2-deployed-necrosis-vs-viable.png ·
E-deployed-review-history.png

## Cost (demo scale, us-east-1)
Effectively **$0 for the demo window**; **~$0.20–0.30/month** if left running
(S3 ~17 MiB + web ~1 MB ≈ negligible; ECR image ~1.5–2 GB ≈ $0.15–0.20/mo;
Lambda/APIGW/DynamoDB/CloudFront within free tier at demo traffic). No
GPU/SageMaker/RDS/NAT/App Runner.

## Teardown
```
# from app/g6/deploy/cdk (CDK venv active, AWS_PROFILE=workshop):
cdk destroy OsteoPatchG8 --force
# then empty + confirm the asset bucket (web bucket auto-empties via custom resource):
aws s3 rm s3://osteopatch-artifacts-153485202811/images/ --recursive --profile workshop
aws s3 rm s3://osteopatch-artifacts-153485202811/thumbnails/ --recursive --profile workshop
# optional: delete the ECR image to stop storage cost
```
(The workshop reaper also tears the account down at expiry.)

## Redeploy
```
cd app/g6/deploy/cdk && <activate CDK venv>
set AWS_PROFILE=workshop
cdk deploy OsteoPatchG8        # builds the Lambda image + stack
# re-upload the 50 assets:
aws s3 sync <local images subset>     s3://osteopatch-artifacts-153485202811/images/     --profile workshop
aws s3 sync <local thumbnails subset> s3://osteopatch-artifacts-153485202811/thumbnails/ --profile workshop
# build + upload frontend, invalidate CloudFront.
```
Rebuildable from the durable project tree; local runtime preserved (unchanged).

## Security / exposure limitations
- Educational prototype, no patient-identifiable data. Private S3 (OAC); no public
  bucket read/write. The review WRITE endpoint is open on the demo API for the
  interactive workflow (bounded, no auth) — acceptable for a hackathon demo;
  documented here as the exposure limitation. All disclaimers visible in the UI.

## Remaining hackathon limitations
- 50-image subset of the 1,144-image local collection (clearly labeled in-UI).
- Behaviorally-reconstructed classifier (contrastive attribution only; absolute
  single-class CAM not recoverable). Scores uncalibrated. Exploratory/educational
  over 4 slide groups; not diagnosis/prognosis/treatment-response.
- Torch Lambda cold start ~10–30 s on first attribution; cached/warm fast.
