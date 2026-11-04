"""Tenant routes: create a tenant and fetch one by id."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from ledgerly_shared.orm import Tenant
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ledgerly_api.auth import require_token
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
def create_tenant(body: TenantCreate, session: SessionDep) -> TenantCreated:
    tenant = Tenant(name=body.name)
    session.add(tenant)
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
        }
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
    return TenantRead(id=tenant.id, name=tenant.name)
