"""Product routes: create and list the products of one tenant."""

import base64
import binascii
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from ledgerly_shared.orm import Product, Tenant
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ledgerly_api.auth import require_token
from ledgerly_api.problems import problem_response
from ledgerly_api.tenants import Problem, SessionDep

router = APIRouter(dependencies=[Depends(require_token)])

MAX_ID = 2**63 - 1

_PROBLEM_RESPONSE = {
    "model": Problem,
    "content": {"application/problem+json": {}},
}


class ProductCreate(BaseModel):
    """Request body for creating a product."""

    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    # Integer minor units, e.g. cents; stored in Product.price_minor.
    price: int = Field(ge=0, le=MAX_ID)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class ProductRead(BaseModel):
    """A product as returned by the API.

    price (integer minor units) and currency are null only for
    products that predate migration 0002.
    """

    id: int
    sku: str
    name: str
    price: int | None
    currency: str | None


class ProductPage(BaseModel):
    """One page of products and the cursor for the next page."""

    items: list[ProductRead]
    next_cursor: str | None


def _problem(
    request: Request, status: int, title: str, detail: str
) -> JSONResponse:
    return problem_response(request, status, detail, title=title)


def _tenant_not_found(request: Request, tenant_id: int) -> JSONResponse:
    return _problem(
        request, 404, "Not Found", f"Tenant {tenant_id} was not found."
    )


def _read(product: Product) -> ProductRead:
    return ProductRead(
        id=product.id,
        sku=product.sku,
        name=product.name,
        price=product.price_minor,
        currency=product.currency,
    )


def _encode_cursor(tenant_id: int, product_id: int) -> str:
    raw = f"{tenant_id}:{product_id}".encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str, tenant_id: int) -> int | None:
    """Return the product id inside a cursor issued for this tenant.

    Returns None if the cursor is malformed or was issued for another
    tenant, so a cursor never changes the traversal of a different
    tenant's products.
    """
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        text = base64.urlsafe_b64decode(padded.encode("ascii")).decode("ascii")
    except (binascii.Error, UnicodeError):
        return None
    tenant_part, _, id_part = text.partition(":")
    if not (tenant_part.isascii() and tenant_part.isdigit()):
        return None
    if not (id_part.isascii() and id_part.isdigit()):
        return None
    if int(tenant_part) != tenant_id:
        return None
    value = int(id_part)
    if value > MAX_ID or _encode_cursor(tenant_id, value) != cursor:
        return None
    return value


@router.post(
    "/tenants/{tenant_id}/products",
    status_code=201,
    response_model=ProductRead,
    responses={
        401: _PROBLEM_RESPONSE,
        404: _PROBLEM_RESPONSE,
        409: _PROBLEM_RESPONSE,
    },
)
def create_product(
    request: Request,
    tenant_id: int,
    body: ProductCreate,
    session: SessionDep,
):
    if session.get(Tenant, tenant_id) is None:
        return _tenant_not_found(request, tenant_id)
    product = Product(
        tenant_id=tenant_id,
        sku=body.sku,
        name=body.name,
        price_minor=body.price,
        currency=body.currency,
    )
    session.add(product)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(Product.id).where(
                Product.tenant_id == tenant_id,
                Product.sku == body.sku,
            )
        )
        if existing is None:
            # Not a sku conflict, so do not report it as one.
            raise
        return _problem(
            request,
            409,
            "Conflict",
            f"Product with sku {body.sku} already exists in "
            f"tenant {tenant_id}.",
        )
    return _read(product)


@router.get(
    "/tenants/{tenant_id}/products",
    response_model=ProductPage,
    responses={
        400: _PROBLEM_RESPONSE,
        401: _PROBLEM_RESPONSE,
        404: _PROBLEM_RESPONSE,
    },
)
def list_products(
    request: Request,
    tenant_id: int,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
):
    if session.get(Tenant, tenant_id) is None:
        return _tenant_not_found(request, tenant_id)
    query = select(Product).where(Product.tenant_id == tenant_id)
    if cursor is not None:
        after = _decode_cursor(cursor, tenant_id)
        if after is None:
            return _problem(
                request, 400, "Bad Request", "The cursor is not valid."
            )
        query = query.where(Product.id > after)
    rows = list(session.scalars(query.order_by(Product.id).limit(limit + 1)))
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        next_cursor = _encode_cursor(tenant_id, page[-1].id)
    return ProductPage(
        items=[_read(product) for product in page],
        next_cursor=next_cursor,
    )
