"""Read-only Locust load test for a tenant's product endpoints.

Part of Ledgerly. Configuration comes from the environment:

    LEDGERLY_API_TOKEN (or API_TOKEN)  bearer token for the API
    LEDGERLY_TENANT_ID                 id of an existing tenant

The host is Locust's --host option. No request here writes data.
"""

import os
import random

from locust import HttpUser, between, task

PAGE_SIZE = 20
MAX_FOLLOWED_PAGES = 2
MAX_KNOWN_IDS = 500


def _require_env() -> tuple[str, str]:
    token = os.environ.get("LEDGERLY_API_TOKEN") or os.environ.get("API_TOKEN")
    tenant_id = os.environ.get("LEDGERLY_TENANT_ID")
    missing = []
    if not token:
        missing.append("LEDGERLY_API_TOKEN (or API_TOKEN)")
    if not tenant_id:
        missing.append("LEDGERLY_TENANT_ID")
    if missing:
        raise SystemExit("locustfile: set " + " and ".join(missing) + ".")
    return token, tenant_id


TOKEN, TENANT_ID = _require_env()


class ProductsUser(HttpUser):
    """Lists, pages through and fetches products for one tenant."""

    wait_time = between(0.5, 2)

    def on_start(self):
        self.client.headers["Authorization"] = f"Bearer {TOKEN}"
        self.product_ids: list[int] = []

    def _remember(self, items):
        for item in items:
            if len(self.product_ids) >= MAX_KNOWN_IDS:
                self.product_ids.pop(random.randrange(len(self.product_ids)))
            self.product_ids.append(item["id"])

    def _get_page(self, name, params):
        """GET one page; return its parsed body, or None on failure."""
        with self.client.get(
            f"/tenants/{TENANT_ID}/products",
            params=params,
            name=name,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")
                return None
            try:
                body = response.json()
                items = body["items"]
                next_cursor = body["next_cursor"]
            except (ValueError, KeyError, TypeError):
                response.failure("malformed page body")
                return None
            self._remember(items)
            return {"items": items, "next_cursor": next_cursor}

    @task(5)
    def list_products(self):
        self._get_page("/tenants/[id]/products", {"limit": PAGE_SIZE})

    @task(2)
    def follow_cursor(self):
        page = self._get_page(
            "/tenants/[id]/products", {"limit": PAGE_SIZE}
        )
        for _ in range(MAX_FOLLOWED_PAGES):
            if page is None or page["next_cursor"] is None:
                return
            page = self._get_page(
                "/tenants/[id]/products?cursor",
                {"limit": PAGE_SIZE, "cursor": page["next_cursor"]},
            )

    @task(3)
    def get_product(self):
        if not self.product_ids:
            return
        product_id = random.choice(self.product_ids)
        with self.client.get(
            f"/tenants/{TENANT_ID}/products/{product_id}",
            name="/tenants/[id]/products/[id]",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")
