"""Enterprise E1 configuration and the RBAC role model.

Nothing here is a clinical claim. This module adds the *systems* concerns the
G6 prototype lacked (identity, roles, tenancy) and never alters the frozen
3-class model contract.
"""
from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Roles (RBAC) — ordered loosely by privilege, but access is per-capability,
# not a strict hierarchy (an auditor is NOT a superset of a reviewer).
# ---------------------------------------------------------------------------
class Role(str, Enum):
    STUDENT = "student"
    REVIEWER = "reviewer"
    PATHOLOGIST = "pathologist"
    ML_ENGINEER = "ml_engineer"
    ADMIN = "admin"
    AUDITOR = "auditor"


ALL_ROLES = tuple(r.value for r in Role)

# Capability → roles allowed. Routes depend on capabilities, not raw roles, so
# the policy is auditable in one place.
CAPABILITIES: dict[str, tuple[str, ...]] = {
    # read the gallery / a patch / its prediction + attribution
    "review:read": (Role.STUDENT, Role.REVIEWER, Role.PATHOLOGIST, Role.ADMIN, Role.AUDITOR),
    # submit ACCEPT / CORRECT / DEFER
    "review:write": (Role.STUDENT, Role.REVIEWER, Role.PATHOLOGIST, Role.ADMIN),
    # adjudicate / batch sign-off (E4 contract; enforced now so routes exist)
    "review:adjudicate": (Role.PATHOLOGIST, Role.ADMIN),
    # export reviews
    "export:read": (Role.REVIEWER, Role.PATHOLOGIST, Role.ADMIN, Role.AUDITOR),
    # manage projects / memberships / datasets
    "project:admin": (Role.ADMIN,),
    # model registry (E5 contract)
    "model:manage": (Role.ML_ENGINEER, Role.ADMIN),
    # read the audit log
    "audit:read": (Role.AUDITOR, Role.ADMIN),
    # LIVE INFERENCE — two capabilities, deliberately split.
    #
    # `live:analyze` is the WRITER: it accepts an uploaded file, spends CPU on a
    # forward pass, and writes rows plus on-disk artefacts. Excluded: STUDENT
    # (running inference is not a learning action, and it is the expensive one)
    # and AUDITOR (read-only by role across this whole capability map).
    "live:analyze": (Role.REVIEWER, Role.PATHOLOGIST, Role.ML_ENGINEER, Role.ADMIN),
    # `live:read` is the READER: view a stored run, its tiles and its mosaic.
    # Everyone who can read the review surface can read a live result — there is
    # nothing in an uploaded-file result that a learner may not see.
    "live:read": (
        Role.STUDENT, Role.REVIEWER, Role.PATHOLOGIST,
        Role.ML_ENGINEER, Role.ADMIN, Role.AUDITOR,
    ),
    # CASE REPORTS — two capabilities, same writer/reader shape as live inference.
    #
    # `report:write` is the WRITER: it produces a signed clinical-style document
    # and appends a row that can never be edited. Deliberately excludes AUDITOR
    # (an audit trail must not be writable by whoever audits it) and STUDENT
    # (a learner drafts practice notes, not the case record). ML_ENGINEER is
    # excluded too: this is a clinical document, and the roles that may author
    # one are the ones that review cases.
    "report:write": (Role.REVIEWER, Role.PATHOLOGIST, Role.ADMIN),
    # `report:read`: a report is derived from data every role may read, so
    # nothing in it is withheld from a learner or an auditor.
    "report:read": (
        Role.STUDENT, Role.REVIEWER, Role.PATHOLOGIST,
        Role.ML_ENGINEER, Role.ADMIN, Role.AUDITOR,
    ),
}
# normalize enum members to their string values
CAPABILITIES = {
    cap: tuple(r.value if isinstance(r, Role) else r for r in roles)
    for cap, roles in CAPABILITIES.items()
}


def roles_for(capability: str) -> tuple[str, ...]:
    if capability not in CAPABILITIES:
        raise KeyError(f"unknown capability: {capability}")
    return CAPABILITIES[capability]


# ---------------------------------------------------------------------------
# Token / IdP config
# ---------------------------------------------------------------------------
# E1 uses a LOCAL symmetric signing key for a stand-in IdP. In a real
# deployment OSTEOPATCH_OIDC_JWKS_URL points at Cognito/your IdP and the issuer
# verifies RS256 against the JWKS — the verify path is identical in shape.
JWT_SECRET = os.environ.get("OSTEOPATCH_JWT_SECRET", "e1-local-dev-not-a-real-secret")
JWT_ALG = "HS256"
JWT_ISSUER = "osteopatch-e1-local"
JWT_AUDIENCE = "osteopatch-api"
TOKEN_TTL_SECONDS = int(os.environ.get("OSTEOPATCH_TOKEN_TTL", "3600"))

# External OIDC (unset locally -> local issuer used). When set, E1 is wired to
# verify third-party tokens instead; the stub issuer is disabled.
OIDC_JWKS_URL = os.environ.get("OSTEOPATCH_OIDC_JWKS_URL", "").strip()
USE_EXTERNAL_OIDC = bool(OIDC_JWKS_URL)

# ---------------------------------------------------------------------------
# Enterprise data store (users / projects / memberships / audit).
# Separate DB from the G6 review store — different lifecycle + ownership.
# ---------------------------------------------------------------------------
def _env_path(var: str, default: str) -> Path:
    return Path(os.environ.get(var, default)).resolve()


SCRATCH_ROOT = _env_path(
    "OSTEOPATCH_ENT_SCRATCH",
    str(Path(os.environ.get("KIROCREW_SCRATCH", str(Path.home() / ".kiro" / "crew" / "scratch"))) / "osteopatch_e1"),
)
ENT_DB_PATH = _env_path("OSTEOPATCH_ENT_DB", str(SCRATCH_ROOT / "enterprise.sqlite3"))
AUDIT_LOG_PATH = _env_path("OSTEOPATCH_AUDIT_LOG", str(SCRATCH_ROOT / "audit_chain.jsonl"))

# Per-project image allowlists live here; each project's scope is written as a
# JSON file the G6 app already understands (OSTEOPATCH_IMAGE_ALLOWLIST).
PROJECT_SCOPE_DIR = _env_path("OSTEOPATCH_PROJECT_SCOPES", str(SCRATCH_ROOT / "project_scopes"))

HOST = "127.0.0.1"
PORT = int(os.environ.get("OSTEOPATCH_ENT_PORT", "8140"))

DISCLAIMER = (
    "Educational / research prototype. NOT for diagnosis, treatment decisions, "
    "treatment-response prediction, or prognosis."
)
