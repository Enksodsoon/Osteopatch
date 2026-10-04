# OsteoPatch Review API — AWS Lambda container image (G8).
#
# Base: official AWS Lambda Python 3.12 runtime image.
# Serve path is torch-free; torch + torchvision + pytorch-grad-cam are present
# for the ON-DEMAND /attribution route only (imported lazily at request time).
#
# Build context = app/g6 (so we can COPY both backend/ and deploy/). The large
# TIFF + thumbnail pixel assets are NOT baked in — they are fetched from the
# private S3 artifacts bucket at request time. Only the frozen SQLite read model
# and the 21 KB recovered-model bundle are baked in (immutable, load-bearing).

FROM public.ecr.aws/lambda/python:3.12

# ---- Python deps -----------------------------------------------------------
# Serve path: fastapi + mangum + pydantic + pillow + numpy.
# Attribution path (lazy): torch CPU + torchvision + pytorch-grad-cam.
# boto3/botocore are already in the Lambda runtime, but pin them for parity.
COPY deploy/requirements-lambda.txt /tmp/requirements-lambda.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements-lambda.txt \
        --target "${LAMBDA_TASK_ROOT}" && \
    # grad-cam pulls in opencv-python, which links libGL/libxcb (absent on the
    # minimal Lambda base image -> "libxcb.so.1: cannot open shared object").
    # pip cannot uninstall from a --target dir, so delete the cv2 package files
    # directly, then install the headless build (no X11/GL system deps).
    rm -rf "${LAMBDA_TASK_ROOT}/cv2" "${LAMBDA_TASK_ROOT}"/opencv_python-*.dist-info && \
    python -m pip install opencv-python-headless==4.10.0.84 --target "${LAMBDA_TASK_ROOT}"

# ---- Application package ----------------------------------------------------
# The backend package (osteopatch/) — unchanged certified G7 code + the G8
# DynamoDB adapter + store selector.
COPY backend/osteopatch "${LAMBDA_TASK_ROOT}/osteopatch"

# The Lambda entrypoint (sets env/paths, wraps app with Mangum).
COPY deploy/lambda_handler.py "${LAMBDA_TASK_ROOT}/lambda_handler.py"

# ---- Baked immutable runtime artifacts -------------------------------------
# Frozen read model (source_qc + prediction) and the recovered attribution head.
# Copied under deploy/_bake/ by the deploy script before `cdk deploy`.
COPY deploy/_bake/db/osteopatch_g6.sqlite3 "${LAMBDA_TASK_ROOT}/runtime/db/osteopatch_g6.sqlite3"
COPY deploy/_bake/models/g4-behavioral-recovery-r1.pt "${LAMBDA_TASK_ROOT}/runtime/models/g4-behavioral-recovery-r1.pt"

# G8 deployed-demo scope: the deterministic 50-image allowlist. The gallery /
# detail / export reads restrict to these ids (no prediction/label changed).
COPY deploy/_bake/g8-subset-image-ids.json "${LAMBDA_TASK_ROOT}/runtime/g8-subset-image-ids.json"

# ---- Fail closed on artifact drift ------------------------------------------
# The three artifacts above are identified by HASH, not by filename. A rebuilt
# or substituted database carrying the right name would otherwise produce an
# image that is not the one that was certified. Rebuild the context with
# scripts/prepare_bake.py, which verifies every source before copying.
COPY deploy/runtime-artifacts.expected.json "${LAMBDA_TASK_ROOT}/runtime/expected.json"
COPY deploy/verify_bake.py "${LAMBDA_TASK_ROOT}/verify_bake.py"
RUN python "${LAMBDA_TASK_ROOT}/verify_bake.py" \
        "${LAMBDA_TASK_ROOT}/runtime" "${LAMBDA_TASK_ROOT}/runtime/expected.json" && \
    rm -f "${LAMBDA_TASK_ROOT}/verify_bake.py" "${LAMBDA_TASK_ROOT}/runtime/expected.json"

# ---- Bake the ImageNet backbone weights (offline attribution) --------------
# The attribution model is mobilenet_v3_small(IMAGENET1K_V1) + the recovered
# head. torchvision would otherwise DOWNLOAD the backbone weights at request
# time — impossible in Lambda (no NAT egress, read-only FS). Pre-fetch them at
# BUILD time into a baked TORCH_HOME; the handler points TORCH_HOME here so the
# runtime load is a local cache hit, never a network call.
ENV TORCH_HOME="${LAMBDA_TASK_ROOT}/runtime/torch"
RUN mkdir -p "${LAMBDA_TASK_ROOT}/runtime/torch/hub/checkpoints" && \
    PYTHONPATH="${LAMBDA_TASK_ROOT}" TORCH_HOME="${LAMBDA_TASK_ROOT}/runtime/torch" \
    python -c "from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights; mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)"

# Strip pip caches / tests to keep the image lean.
RUN find "${LAMBDA_TASK_ROOT}" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true && \
    find "${LAMBDA_TASK_ROOT}" -type d -name "tests" -prune -exec rm -rf {} + 2>/dev/null || true

CMD [ "lambda_handler.handler" ]
