#!/usr/bin/env python3
"""OsteoPatch G8 — CDK app (us-east-1, workshop account 153485202811).

Cost-minimal, serverless, no always-on compute:

  * Lambda (container image, torch baked for the lazy /attribution path) behind
    an API Gateway v2 HTTP API.
  * DynamoDB on-demand table for the append-only review_event stream.
  * Private S3 web bucket (OAC) + CloudFront, with /v1/* routed to the API and
    everything else to the SPA. Single origin for the browser => no CORS, and
    the certified frontend's relative /v1 calls work unchanged.
  * Read-only IAM to the EXISTING private artifacts bucket
    (osteopatch-artifacts-153485202811) for the TIFF/thumbnail pixel assets.

Nothing public-writable beyond the demo review POST; the artifacts + web buckets
stay private (OAC only). All educational disclaimers are served by the app.
"""
import os

from aws_cdk import (
    App,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_apigatewayv2 as apigw,
    aws_apigatewayv2_integrations as integrations,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origins,
    aws_dynamodb as ddb,
    aws_ecr_assets as ecr_assets,
    aws_iam as iam,
    aws_lambda as _lambda,
    aws_s3 as s3,
)
from constructs import Construct

ACCOUNT = os.environ.get("CDK_DEFAULT_ACCOUNT", "153485202811")
REGION = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
ARTIFACTS_BUCKET = "osteopatch-artifacts-153485202811"
HERE = os.path.dirname(os.path.abspath(__file__))  # app/g6/deploy/cdk
APP_G6 = os.path.abspath(os.path.join(HERE, "..", ".."))  # docker build context = app/g6


class OsteoPatchStack(Stack):
    def __init__(self, scope: Construct, cid: str, **kw) -> None:
        super().__init__(scope, cid, **kw)

        artifacts = s3.Bucket.from_bucket_name(self, "Artifacts", ARTIFACTS_BUCKET)

        # ---- DynamoDB: append-only review events ---------------------------
        reviews = ddb.Table(
            self, "Reviews",
            table_name="osteopatch-reviews",
            partition_key=ddb.Attribute(name="image_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="sk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # demo — teardown deletes it
        )
        reviews.add_global_secondary_index(
            index_name="idem-index",
            partition_key=ddb.Attribute(name="image_id", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="idempotency_key", type=ddb.AttributeType.STRING),
        )

        # ---- Lambda: the FastAPI API as a container image ------------------
        image = ecr_assets.DockerImageAsset(
            self, "ApiImage",
            directory=APP_G6,
            file="deploy/Dockerfile",
            platform=ecr_assets.Platform.LINUX_AMD64,
        )
        fn = _lambda.DockerImageFunction(
            self, "ApiFn",
            function_name="osteopatch-api",
            code=_lambda.DockerImageCode.from_ecr(
                image.repository, tag_or_digest=image.image_tag
            ),
            memory_size=3008,                 # torch attribution needs headroom
            timeout=Duration.seconds(90),     # cold start w/ torch 10-30s
            ephemeral_storage_size=None,      # default 512MB /tmp is enough per-image
            environment={
                "OSTEOPATCH_REVIEW_STORE": "dynamodb",
                "OSTEOPATCH_REVIEW_TABLE": reviews.table_name,
                "OSTEOPATCH_ASSET_BUCKET": ARTIFACTS_BUCKET,
                "OSTEOPATCH_ASSET_TIFF_PREFIX": "images/",
                "OSTEOPATCH_ASSET_THUMB_PREFIX": "thumbnails/",
                "OSTEOPATCH_PROJECT_ROOT": "/var/task/runtime",
            },
        )
        reviews.grant_read_write_data(fn)
        artifacts.grant_read(fn)  # read-only TIFFs/thumbnails + model mirror

        # ---- API Gateway v2 HTTP API (Lambda proxy) ------------------------
        http = apigw.HttpApi(
            self, "HttpApi",
            api_name="osteopatch-api",
            default_integration=integrations.HttpLambdaIntegration("ApiInteg", fn),
        )

        # ---- Web bucket (private) + CloudFront -----------------------------
        web = s3.Bucket(
            self, "Web",
            bucket_name=f"osteopatch-web-{ACCOUNT}",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        api_domain = f"{http.api_id}.execute-api.{REGION}.amazonaws.com"
        api_origin = origins.HttpOrigin(api_domain)

        dist = cf.Distribution(
            self, "Cdn",
            default_behavior=cf.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(web),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cf.CachePolicy.CACHING_OPTIMIZED,
            ),
            additional_behaviors={
                "/v1/*": cf.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
            default_root_object="index.html",
            error_responses=[
                # SPA fallback: 403/404 from S3 -> index.html (client-side routing)
                cf.ErrorResponse(http_status=403, response_http_status=200,
                                 response_page_path="/index.html", ttl=Duration.seconds(0)),
                cf.ErrorResponse(http_status=404, response_http_status=200,
                                 response_page_path="/index.html", ttl=Duration.seconds(0)),
            ],
            comment="OsteoPatch educational review demo (G8)",
        )

        CfnOutput(self, "WebBucketName", value=web.bucket_name)
        CfnOutput(self, "DistributionId", value=dist.distribution_id)
        CfnOutput(self, "PublicUrl", value=f"https://{dist.distribution_domain_name}")
        CfnOutput(self, "ApiUrl", value=http.url or f"https://{api_domain}")
        CfnOutput(self, "ApiFunctionName", value=fn.function_name)
        CfnOutput(self, "ReviewsTableName", value=reviews.table_name)


app = App()
OsteoPatchStack(
    app, "OsteoPatchG8",
    env={"account": ACCOUNT, "region": REGION},
    description="OsteoPatch educational osteosarcoma review prototype — G8 demo deploy",
)
app.synth()
