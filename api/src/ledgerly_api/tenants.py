"""Tenant routes: create a tenant and fetch one by id."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from ledgerly_shared.orm import AppUser, Tenant, TenantMembership
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ledgerly_api.auth import AuthError, require_token
from ledgerly_api.db import get_session
from ledgerly_api.problems import problem_response

router = APIRouter(dependencies=[Depends(require_token)])

SessionDep = Annotated[Session, Depends(get_session)]


class TenantCreate(BaseModel):
    """Request body for creating a tenant."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)


class TenantCreated(BaseModel):
    """Response body returned after a tenant is created."""

    id: int


class TenantRead(BaseModel):
    """A tenant as returned by the API."""

    id: int
    name: str
    created_at: datetime


class Problem(BaseModel):
    """An RFC 9457 problem details body."""

    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None


@router.post(
    "/tenants",
    status_code=201,
    response_model=TenantCreated,
    responses={
        401: {
            "model": Problem,
            "content": {"application/problem+json": {}},
        }
    },
)
def create_tenant(
    body: TenantCreate,
    session: SessionDep,
    x_user_token: Annotated[str | None, Header()] = None,
) -> TenantCreated:
    # Imported here because roles.py imports Problem from this module.
    from ledgerly_api.roles import hash_token

    owner = None
    if x_user_token is not None:
        owner = session.scalar(
            select(AppUser).where(
                AppUser.token_hash == hash_token(x_user_token)
            )
        )
        if owner is None:
            raise AuthError("Invalid user token.")
    tenant = Tenant(name=body.name)
    session.add(tenant)
    if owner is not None:
        session.flush()
        session.add(
            TenantMembership(
                tenant_id=tenant.id, user_id=owner.id, role="admin"
            )
        )
    session.commit()
    return TenantCreated(id=tenant.id)


@router.get(
    "/tenants/{tenant_id}",
    response_model=TenantRead,
    responses={
        401: {
            "model": Problem,
            "content": {"application/problem+json": {}},
        },
        404: {
            "model": Problem,
            "content": {"application/problem+json": {}},
        },
    },
)
def get_tenant(request: Request, tenant_id: int, session: SessionDep):
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        return problem_response(
            request,
            404,
            f"Tenant {tenant_id} was not found.",
            title="Not Found",
        )
    return TenantRead(
        id=tenant.id, name=tenant.name, created_at=tenant.created_at
    )
