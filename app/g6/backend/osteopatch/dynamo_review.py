"""DynamoDB-backed review-event store (G8 cloud deploy ONLY).

Why this exists
---------------
SQLite cannot ride a Lambda (no durable writable local disk across invocations).
For the AWS demo the IMMUTABLE read model (``source_qc`` + ``prediction``) still
ships as the frozen SQLite file inside the image — it is read-only and never
changes — while the APPEND-ONLY ``review_event`` stream moves to DynamoDB so
human review persists across stateless Lambda invocations.

This module is a THIN adapter, not a domain redesign. It implements exactly the
review-state surface the API already calls on ``repo``:

  * ``current_revision(image_id) -> int``
  * ``latest_event(image_id) -> Mapping | None``
  * ``event_history(image_id) -> list[Mapping]``
  * ``submit_review(...) -> (event_mapping, created)``

with the SAME invariants as the SQLite path: prediction immutable; review_event
append-only with a monotonic 1-based ``revision_number`` per image; optimistic
concurrency on ``expected_revision``; idempotent replay on ``idempotency_key``;
the same typed errors (NotFoundError / ValidationError / ConflictError).

Selection is by env var (``OSTEOPATCH_REVIEW_STORE=dynamodb``) in app.py, so the
local SQLite behaviour is completely unchanged when the var is unset.

Rows returned are plain dicts that support ``row["col"]`` access exactly like
``sqlite3.Row`` — the query layer's ``_event_dict`` reads them unchanged.

Table shape (single table, on-demand)
-------------------------------------
  PK  image_id (S)
  SK  sk (S):   "REV#<zero-padded revision>"  -> one item per review event
                "META"  (optional) not used; MAX(revision) is derived by a
                        reverse query Limit=1 on the REV# range.
  attributes: review_event_id, prediction_id, action, selected_class, reason,
              note, reviewer, created_at, revision_number (N), idempotency_key
  GSI "idem-index": PK image_id, SK idempotency_key  -> idempotent replay lookup

Concurrency: the insert uses a ConditionExpression (attribute_not_exists(sk)) so
two writers racing for the same revision cannot both win — the loser retries the
idempotency lookup, mirroring the SQLite IntegrityError path.
"""
from __future__ import annotations

import os
import uuid

from . import config
from .db import utc_now
# Reuse the SAME typed errors the API already maps to HTTP status codes.
from .repo import NotFoundError, ValidationError, ConflictError

CANON = set(config.CANONICAL_CLASSES)

_TABLE_ENV = "OSTEOPATCH_REVIEW_TABLE"
_IDEM_INDEX = "idem-index"
_REV_WIDTH = 9  # zero-pad revision in the sort key so lexical == numeric order


def _table():
    import boto3
    name = os.environ.get(_TABLE_ENV)
    if not name:
        raise RuntimeError(f"{_TABLE_ENV} not set — DynamoDB review store misconfigured")
    region = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.resource("dynamodb", region_name=region).Table(name)


def _rev_sk(rev: int) -> str:
    return f"REV#{int(rev):0{_REV_WIDTH}d}"


def _item_to_row(item: dict) -> dict:
    """Return a dict with the exact keys queries._event_dict / repo expect."""
    return {
        "review_event_id": item["review_event_id"],
        "image_id": item["image_id"],
        "prediction_id": item["prediction_id"],
        "action": item["action"],
        "selected_class": item.get("selected_class"),
        "reason": item.get("reason"),
        "note": item.get("note"),
        "reviewer": item["reviewer"],
        "created_at": item["created_at"],
        "revision_number": int(item["revision_number"]),
        "idempotency_key": item["idempotency_key"],
    }


# ---- read surface (mirrors repo.*) ----------------------------------------
def current_revision(image_id: str) -> int:
    from boto3.dynamodb.conditions import Key
    resp = _table().query(
        KeyConditionExpression=Key("image_id").eq(image_id)
        & Key("sk").begins_with("REV#"),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return int(items[0]["revision_number"]) if items else 0


def latest_event(image_id: str) -> dict | None:
    from boto3.dynamodb.conditions import Key
    resp = _table().query(
        KeyConditionExpression=Key("image_id").eq(image_id)
        & Key("sk").begins_with("REV#"),
        ScanIndexForward=False,
        Limit=1,
    )
    items = resp.get("Items", [])
    return _item_to_row(items[0]) if items else None


def event_history(image_id: str) -> list[dict]:
    from boto3.dynamodb.conditions import Key
    resp = _table().query(
        KeyConditionExpression=Key("image_id").eq(image_id)
        & Key("sk").begins_with("REV#"),
        ScanIndexForward=True,
    )
    return [_item_to_row(it) for it in resp.get("Items", [])]


def _event_by_idem(image_id: str, idem_key: str) -> dict | None:
    from boto3.dynamodb.conditions import Key
    resp = _table().query(
        IndexName=_IDEM_INDEX,
        KeyConditionExpression=Key("image_id").eq(image_id)
        & Key("idempotency_key").eq(idem_key),
        Limit=1,
    )
    items = resp.get("Items", [])
    return _item_to_row(items[0]) if items else None


def load_all_review_state() -> dict:
    """One paginated Scan of the (tiny) review_event table -> latest-per-image.

    Returns {image_id: {"latest": row, "revision": int}}. The table holds only
    REV# items (no other item types), and starts empty, growing only by demo
    review clicks — a Scan is cheap and avoids N per-image queries on the
    gallery. On-demand billing: a handful of RCUs."""
    table = _table()
    out: dict = {}
    kwargs: dict = {}
    while True:
        resp = table.scan(**kwargs)
        for it in resp.get("Items", []):
            iid = it["image_id"]
            rev = int(it["revision_number"])
            cur = out.get(iid)
            if cur is None or rev > cur["revision"]:
                out[iid] = {"latest": _item_to_row(it), "revision": rev}
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return out


# ---- write surface (mirrors repo.submit_review) ---------------------------
def submit_review(
    get_prediction,          # callable(prediction_id) -> prediction mapping | None
    image_exists,            # callable(image_id) -> bool
    image_id: str,
    prediction_id: str,
    action: str,
    expected_revision: int,
    idempotency_key: str,
    selected_label: str | None = None,
    reason: str | None = None,
    note: str | None = None,
    reviewer: str | None = None,
) -> tuple[dict, bool]:
    """Append one review event to DynamoDB. Same validation + invariants as the
    SQLite path. ``get_prediction`` / ``image_exists`` are injected so the
    IMMUTABLE read model stays in the frozen SQLite file."""
    if not image_exists(image_id):
        raise NotFoundError("unknown image_id", {"image_id": image_id})

    pred = get_prediction(prediction_id)
    if pred is None:
        raise NotFoundError("unknown prediction_id", {"prediction_id": prediction_id})
    if pred["image_id"] != image_id:
        raise ValidationError(
            "prediction_id does not belong to image_id",
            {"image_id": image_id, "prediction_id": prediction_id},
        )

    action = (action or "").upper()
    if action not in config.REVIEW_ACTIONS:
        raise ValidationError("invalid action", {"action": action})

    if action == "CORRECT":
        if selected_label not in CANON:
            raise ValidationError(
                "CORRECT requires a valid canonical class",
                {"selected_label": selected_label, "allowed": list(config.CANONICAL_CLASSES)},
            )
    elif action == "ACCEPT":
        if selected_label is not None and selected_label != pred["predicted_class"]:
            raise ValidationError(
                "ACCEPT cannot carry a label contradicting the prediction",
                {"selected_label": selected_label, "predicted_class": pred["predicted_class"]},
            )
        selected_label = None
    elif action == "DEFER":
        if selected_label is not None:
            raise ValidationError(
                "DEFER must not carry a class", {"selected_label": selected_label}
            )
        if reason is not None and reason not in config.DEFER_REASONS:
            raise ValidationError(
                "invalid defer reason",
                {"reason": reason, "allowed": list(config.DEFER_REASONS)},
            )

    # idempotent replay — same key on same image returns the original
    prior = _event_by_idem(image_id, idempotency_key)
    if prior is not None:
        return prior, False

    # optimistic concurrency
    cur_rev = current_revision(image_id)
    if int(expected_revision) != cur_rev:
        raise ConflictError(
            "stale expected_revision",
            {"expected_revision": expected_revision, "current_revision": cur_rev},
        )

    new_rev = cur_rev + 1
    event_id = f"rev-{image_id}-{new_rev}-{uuid.uuid4().hex[:8]}"
    item = {
        "image_id": image_id,
        "sk": _rev_sk(new_rev),
        "review_event_id": event_id,
        "prediction_id": prediction_id,
        "action": action,
        "selected_class": selected_label,
        "reason": reason,
        "note": note,
        "reviewer": reviewer or config.DEFAULT_REVIEWER,
        "created_at": utc_now(),
        "revision_number": new_rev,
        "idempotency_key": idempotency_key,
    }
    # drop None attributes (DynamoDB rejects None values)
    item = {k: v for k, v in item.items() if v is not None}

    from botocore.exceptions import ClientError
    try:
        _table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(image_id) AND attribute_not_exists(sk)",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            # racing writer took this revision first — mirror the SQLite retry
            again = _event_by_idem(image_id, idempotency_key)
            if again is not None:
                return again, False
            raise ConflictError("concurrent revision conflict", {"error": str(exc)})
        raise

    return _item_to_row(item), True
