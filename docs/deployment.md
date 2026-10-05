# Deployment and release runbook

## Two different public surfaces
**GitHub Pages** serves the project/documentation website. **AWS** serves the historical reviewer application. Pages cannot run FastAPI or replace the review database. A successful Pages deployment says nothing about the AWS source revision, model availability or clinical validity.

## GitHub Pages
The `Pages` workflow builds the fixed `_site/` allowlist, checks local links and safety disclosures, uploads a Pages artifact and deploys it from trusted `main`. Only the deployment job has `pages: write` and `id-token: write`. No AWS keys or paid API are needed. Repository Settings → Pages must use **GitHub Actions** as its build source.

Local equivalent:
```sh
python -m unittest discover -s tests/tooling -v
python scripts/build_site.py
python scripts/check_site.py
```

Only six HTML pages, CSS, the three existing approved screenshots and deterministic build metadata are published. Never set the upload path to `.` or publish `runtime-artifacts/`, `aidlc-docs/` wholesale, databases or models. To roll back, revert the website change through a tested PR or rerun the Pages workflow at an appropriately reviewed revision.

## Existing AWS workshop demo
The checked-in [CDK outputs](../app/g6/deploy/cdk-outputs.json) identify the original demo. The new frontend workflow does not provision, destroy or redeploy that stack. It uploads a tested frontend to the existing web bucket and invalidates only the entry document. It does not update API code, model weights, source images, thumbnails or reviews.

### Required configuration before an AWS frontend deployment
- Environment `aws-demo`, restricted to protected `main`, with maintainer approval.
- Environment/repository variable `AWS_DEPLOY_ENABLED` exactly `true` only after a deployment and cost review.
- Variable `AWS_ROLE_ARN`: an explicitly approved short-lived OIDC role in the **existing demo account**. No role is invented or created by this repository.
- Variables `AWS_ACCOUNT_ID`, `AWS_REGION`, `AWS_WEB_BUCKET`, `AWS_DISTRIBUTION_ID` matching the intended existing resources.

The workflow validates inputs, uses OIDC rather than long-lived keys, confirms the caller account and checks that the target bucket/distribution are the intended pairing. Missing configuration fails before credential exchange or upload. Do not turn the enable flag on simply to make a workflow green.

The role's trust policy must restrict the subject to `repo:Enksodsoon/Osteopatch:environment:aws-demo` and audience `sts.amazonaws.com`. Its permissions should be limited to caller identity, reading the target distribution, listing the selected web bucket, writing only web objects and invalidating that distribution. It must not grant infrastructure creation, model/data access, DynamoDB writes or bucket deletion. Creating/changing the role is a separately authorized AWS task and is not performed here.

### Dispatch and verification
Run **Deploy existing AWS frontend** on trusted `main`, selecting the explicit confirmation value. The workflow rebuilds/tests the frontend, uploads hashed assets first and then entry files, retains previous assets, and records the source SHA. It does not use `aws s3 sync --delete`.

A frontend-only rollout can still be incompatible with an older API. Before approving it, verify the deployed API contract and the intended demo subset. After upload, inspect the public page, health, images, model-card disclosures and a permitted disposable review/export journey. Do not call the full system deployed based only on an upload exit code.

### Rollback and cost
Retained old hashed assets support an entry-document rollback, but they are not a complete backup. Preserve a reviewed prior frontend build or rebuild its exact commit and manually restore it under the same environment gate. Do not rewrite model/review evidence. Verify the deployed result after rollback.

AWS S3 operations, invalidations, Lambda, storage and review traffic can incur charges. Workshop credits are not a guarantee of zero cost. This maintenance pass does not execute AWS deployment or create resources. Expired credentials or an absent OIDC role are reported as operational prerequisites, not worked around with another account.

The historical CDK stack includes destroy-on-removal demo resources. Never run `cdk destroy`, broad S3 deletion or stack replacement as routine cleanup; preserve reviews and explicitly approve any teardown.

## Draft prereleases
The release workflow is manually dispatched on `main` and accepts a version matching the canonical Python project version. It refuses an existing release and creates a **draft prerelease**, with intended-use and runtime limitations. Review it before publication. Source archives do not include the licensed runtime bundle. A release tag is not clinical certification.

## Primary references
[GitHub Pages custom workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages) · [Actions secure use](https://docs.github.com/en/actions/reference/security/secure-use) · [OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
