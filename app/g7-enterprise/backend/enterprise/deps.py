"""FastAPI dependencies — authn, authz (capability), and project tenancy.

A route declares the capability it needs and (if project-scoped) reads the
X-Project-Id header. These dependencies turn a bearer token + project into a
verified Principal or a 401/403, and emit the authz decision to the audit log
on denial of a mutation.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass

from fastapi import Header, HTTPException

from . import auth, config


@dataclass
class Principal:
    user_id: str
    email: str
    roles: dict  # project_id -> role

    def role_in(self, project_id: str) -> str | None:
        return self.roles.get(project_id)


def principal_from_header(authorization: str | None) -> Principal:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = auth.verify_token(token)
    except auth.AuthError as exc:
        raise HTTPException(status_code=exc.http_status, detail=exc.message) from exc
    return Principal(
        user_id=claims["sub"],
        email=claims.get("email", ""),
        roles=claims.get("roles", {}) or {},
    )


def require(capability: str, *, project_scoped: bool = True):
    """Build a FastAPI dependency enforcing `capability`.

    When project_scoped, the caller must send X-Project-Id and hold a role in
    that project that grants the capability. When not, any role the user holds
    in ANY project that grants the capability suffices (used for cross-project
    reads like the audit log for an auditor).
    """
    allowed = set(config.roles_for(capability))

    def _dep(
        authorization: str | None = Header(default=None),
        x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
    ) -> Principal:
        p = principal_from_header(authorization)
        if project_scoped:
            if not x_project_id:
                raise HTTPException(status_code=400, detail="missing X-Project-Id header")
            # The token proves identity; the store proves current membership and role.
            role = _live_role(p.user_id, x_project_id)
            if role is not None:
                p.roles[x_project_id] = role
            else:
                p.roles.pop(x_project_id, None)
            if role is None:
                # not a member -> do not reveal the project exists
                raise HTTPException(status_code=404, detail="project not found")
            if role not in allowed:
                raise HTTPException(
                    status_code=403,
                    detail=f"role '{role}' lacks capability '{capability}'",
                )
        else:
            roles = _live_roles(p.user_id)
            if not (roles & allowed):
                raise HTTPException(
                    status_code=403,
                    detail=f"no role grants capability '{capability}'",
                )
        return p

    return _dep


def _live_role(user_id: str, project_id: str) -> str | None:
    from . import store
    with closing(_membership_connection()) as conn:
        return store.role_in_project(conn, user_id, project_id)


def _live_roles(user_id: str) -> set[str]:
    from . import store
    with closing(_membership_connection()) as conn:
        return {m["role"] for m in store.memberships_for_user(conn, user_id)}


def _membership_connection() -> sqlite3.Connection:
    # Request dependencies run in FastAPI's thread pool. Keep each authorization
    # read on its own SQLite connection so parallel gallery media calls cannot
    # race through the app's shared connection.
    uri = f"{config.ENT_DB_PATH.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn
