"""Auth — token issue + verify.

E1 ships a LOCAL stand-in IdP (HS256, deterministic) so the whole stack runs
offline with no secret in code beyond a dev key. The verify path has the same
shape as external OIDC verification (decode, check iss/aud/exp, read claims),
so swapping in Cognito/an IdP is a config change, not a rewrite.
"""
from __future__ import annotations

import time

import jwt  # PyJWT

from . import config


class AuthError(Exception):
    def __init__(self, message: str, http_status: int = 401):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


def issue_token(*, user_id: str, email: str, memberships: list[dict]) -> dict:
    """Issue a local bearer token. memberships: [{project_id, role, name}]."""
    if config.USE_EXTERNAL_OIDC:
        raise AuthError(
            "local token issuer disabled: external OIDC is configured", 400
        )
    now = int(time.time())
    claims = {
        "iss": config.JWT_ISSUER,
        "aud": config.JWT_AUDIENCE,
        "sub": user_id,
        "email": email,
        "iat": now,
        "exp": now + config.TOKEN_TTL_SECONDS,
        # project_id -> role, compact for the authorizer
        "roles": {m["project_id"]: m["role"] for m in memberships},
    }
    token = jwt.encode(claims, config.JWT_SECRET, algorithm=config.JWT_ALG)
    return {"access_token": token, "token_type": "bearer", "expires_in": config.TOKEN_TTL_SECONDS}


def verify_token(token: str) -> dict:
    """Decode + validate a bearer token, returning its claims.

    In external-OIDC mode this is where JWKS/RS256 verification would run; the
    returned claim shape (sub, email, roles) is kept identical.
    """
    try:
        claims = jwt.decode(
            token,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALG],
            audience=config.JWT_AUDIENCE,
            issuer=config.JWT_ISSUER,
        )
    except jwt.ExpiredSignatureError:
        raise AuthError("token expired", 401)
    except jwt.InvalidTokenError as exc:
        raise AuthError(f"invalid token: {exc}", 401)
    if "sub" not in claims:
        raise AuthError("token missing subject", 401)
    return claims
