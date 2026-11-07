"""Per-tenant roles: user tokens and the role-checking dependency.

Identity is the per-user secret token sent in ``X-User-Token``, looked up by
its SHA-256 hash. It is never a client-supplied user id: no id header is read,
so a caller cannot act as another user without holding that user's token.
Only the hash is stored. The shared bearer token is still required first.
Part of Ledgerly.
"""

import hashlib
import secrets
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header
from ledgerly_shared.orm import AppUser, TenantMembership
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerly_api.auth import AuthError, require_token
from ledgerly_api.db import get_session
from ledgerly_api.problems import ForbiddenError
from ledgerly_api.tenants import Problem

FORBIDDEN_RESPONSE = {
    403: {
        "model": Problem,
        "content": {"application/problem+json": {}},
    }
}


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest under which a user token is stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_token() -> str:
    """Return a new random user token; show it once and store only its hash."""
    return secrets.token_urlsafe(32)


def require_user(
    _: Annotated[None, Depends(require_token)],
    session: Annotated[Session, Depends(get_session)],
    x_user_token: Annotated[str | None, Header()] = None,
) -> AppUser:
    """Return the user owning ``X-User-Token``; 401 when absent or unknown."""
    if not x_user_token:
        raise AuthError("Missing X-User-Token header.")
    user = session.scalar(
        select(AppUser).where(AppUser.token_hash == hash_token(x_user_token))
    )
    if user is None:
        raise AuthError("Invalid user token.")
    return user


def require_role(*allowed: str) -> Callable[..., str]:
    """Build a dependency that allows only these roles in the path tenant.

    The dependency reads the ``tenant_id`` path parameter and returns the
    caller's role. It raises ForbiddenError (403) when the caller is not a
    member of that tenant or holds a role outside ``allowed``.
    """

    def dependency(
        tenant_id: int,
        user: Annotated[AppUser, Depends(require_user)],
        session: Annotated[Session, Depends(get_session)],
    ) -> str:
        role = session.scalar(
            select(TenantMembership.role).where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user.id,
            )
        )
        if role is None or role not in allowed:
            raise ForbiddenError()
        return role

    return dependency
