import asyncio

import pytest

from app.services.product_search import ProductSearchClient
from app.services.torob import TorobSearchResult


@pytest.mark.asyncio
async def test_product_search_does_not_wait_long_for_slow_basalam(monkeypatch) -> None:
    class FakeTorob:
        async def search_base_products(self, query: str, size: int = 5, page: int = 0):
            return [
                TorobSearchResult(
                    rank=0,
                    base_prk="torob-1",
                    name="رب ترب",
                    price=100000,
                    price_text=None,
                    image_url=None,
                    product_url="https://torob.com/p/torob-1",
                    is_already_added=False,
                )
            ]

        async def close(self):
            return None

    class FakeBasalam:
        async def search_products(self, query: str, size: int = 2, page: int = 0):
            await asyncio.sleep(1)
            return []

        async def close(self):
            return None

    monkeypatch.setattr("app.services.product_search.BASALAM_EXTRA_WAIT_SECONDS", 0.01)
    client = ProductSearchClient()
    client.torob = FakeTorob()
    client.basalam = FakeBasalam()

    results = await client.search_products("رب")

    assert [item.base_prk for item in results] == ["torob-1"]
