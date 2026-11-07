"""Product routes: create, list, export and look up one tenant's products."""

import base64
import binascii
import csv
import io
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from ledgerly_shared.orm import Product, Tenant
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, Engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ledgerly_api.auth import require_token
from ledgerly_api.problems import problem_response
from ledgerly_api.tenants import Problem, SessionDep

router = APIRouter(dependencies=[Depends(require_token)])

MAX_ID = 2**63 - 1
# Rows read per query when streaming the CSV export.
BATCH_SIZE = 500
# Cells starting with these are read as formulas by spreadsheets.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

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


def _problem(request: Request, status: int, title: str, detail: str) -> JSONResponse:
    return problem_response(request, status, detail, title=title)


def _tenant_not_found(request: Request, tenant_id: int) -> JSONResponse:
    return _problem(request, 404, "Not Found", f"Tenant {tenant_id} was not found.")


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
            f"Product with sku {body.sku} already exists in tenant {tenant_id}.",
        )
    return _read(product)


@router.get(
    "/tenants/{tenant_id}/products",
    response_model=ProductPage,
    responses={
        400: _PROBLEM_RESPONSE,
        401: _PROBLEM_RESPONSE,
        404: _PROBLEM_RESPONSE,
        422: _PROBLEM_RESPONSE,
    },
)
def list_products(
    request: Request,
    tenant_id: int,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    q: Annotated[str | None, Query(max_length=255)] = None,
):
    if session.get(Tenant, tenant_id) is None:
        return _tenant_not_found(request, tenant_id)
    query = select(Product).where(Product.tenant_id == tenant_id)
    term = (q or "").strip()
    if term:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(Product.name.ilike(f"%{escaped}%", escape="\\"))
    if cursor is not None:
        after = _decode_cursor(cursor, tenant_id)
        if after is None:
            return _problem(request, 400, "Bad Request", "The cursor is not valid.")
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


def _csv_text(value: str) -> str:
    """Neutralize spreadsheet formulas in free text."""
    if value.startswith(_FORMULA_PREFIXES):
        return "'" + value
    return value


def _csv_chunk(rows: list[list[object]]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue()


def _stream_products_csv(bind: Engine | Connection, tenant_id: int) -> Iterator[str]:
    """Yield the tenant's products as CSV, one chunk per batch.

    The generator owns its Session: the request-scoped one may already be
    closed by the time the body is consumed.
    """
    yield _csv_chunk([["id", "sku", "name", "price", "currency"]])
    session = Session(bind)
    try:
        last = 0
        while True:
            batch = list(
                session.scalars(
                    select(Product)
                    .where(Product.tenant_id == tenant_id, Product.id > last)
                    .order_by(Product.id)
                    .limit(BATCH_SIZE)
                )
            )
            if not batch:
                break
            yield _csv_chunk(
                [
                    [
                        product.id,
                        _csv_text(product.sku),
                        _csv_text(product.name),
                        "" if product.price_minor is None else product.price_minor,
                        product.currency or "",
                    ]
                    for product in batch
                ]
            )
            last = batch[-1].id
            if len(batch) < BATCH_SIZE:
                break
    finally:
        session.close()


@router.get(
    "/tenants/{tenant_id}/products.csv",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/csv": {}}},
        401: _PROBLEM_RESPONSE,
        404: _PROBLEM_RESPONSE,
        422: _PROBLEM_RESPONSE,
    },
)
def export_products_csv(
    request: Request,
    tenant_id: int,
    session: SessionDep,
):
    # Check the tenant before streaming: a problem response cannot replace
    # a 200 that has already started.
    if session.get(Tenant, tenant_id) is None:
        return _tenant_not_found(request, tenant_id)
    bind = session.get_bind()
    return StreamingResponse(
        _stream_products_csv(bind, tenant_id),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="tenant-{tenant_id}-products.csv"'
            )
        },
    )


@router.get(
    "/tenants/{tenant_id}/products/{product_id}",
    response_model=ProductRead,
    responses={
        401: _PROBLEM_RESPONSE,
        404: _PROBLEM_RESPONSE,
        422: _PROBLEM_RESPONSE,
    },
)
def get_product(
    request: Request,
    tenant_id: int,
    product_id: Annotated[int, Path(ge=1, le=MAX_ID)],
    session: SessionDep,
):
    if session.get(Tenant, tenant_id) is None:
        return _tenant_not_found(request, tenant_id)
    # Filter on both columns: another tenant's id must look missing.
    product = session.scalar(
        select(Product).where(Product.tenant_id == tenant_id, Product.id == product_id)
    )
    if product is None:
        return _problem(
            request,
            404,
            "Not Found",
            f"Product {product_id} was not found.",
        )
    return _read(product)
