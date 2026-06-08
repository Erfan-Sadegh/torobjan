import asyncio

import pytest

from app.services.product_search import ProductSearchClient
from app.services.torob import TorobSearchResult


@pytest.mark.asyncio
async def test_product_search_uses_only_torob_by_default() -> None:
    class FakeTorob:
        async def search_base_products(self, query: str, size: int = 5, page: int = 0):
            return [
                TorobSearchResult(
                    rank=index,
                    base_prk=f"torob-{index}",
                    name=f"رب ترب {index}",
                    price=100000 + index,
                    price_text=None,
                    image_url=None,
                    product_url=f"https://torob.com/p/torob-{index}",
                    is_already_added=False,
                )
                for index in range(size)
            ]

        async def close(self):
            return None

    client = ProductSearchClient()
    client.torob = FakeTorob()

    results = await client.search_products("رب")

    assert [item.source for item in results] == ["torob", "torob", "torob", "torob"]
    assert [item.base_prk for item in results] == ["torob-0", "torob-1", "torob-2", "torob-3"]


@pytest.mark.asyncio
async def test_product_search_does_not_wait_long_for_slow_basalam(monkeypatch) -> None:
    class FakeTorob:
        async def search_base_products(self, query: str, size: int = 5, page: int = 0):
            return [
                TorobSearchResult(
                    rank=index,
                    base_prk=f"torob-{index}",
                    name=f"رب ترب {index}",
                    price=100000 + index,
                    price_text=None,
                    image_url=None,
                    product_url=f"https://torob.com/p/torob-{index}",
                    is_already_added=False,
                )
                for index in range(size)
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

    assert [item.base_prk for item in results] == ["torob-0", "torob-1", "torob-2", "torob-3"]


@pytest.mark.asyncio
async def test_product_search_fills_missing_basalam_slots_with_torob(monkeypatch) -> None:
    from app.services.basalam import BasalamSearchResult

    class FakeTorob:
        async def search_base_products(self, query: str, size: int = 5, page: int = 0):
            return [
                TorobSearchResult(
                    rank=index,
                    base_prk=f"torob-{index}",
                    name=f"رب ترب {index}",
                    price=100000 + index,
                    price_text=None,
                    image_url=None,
                    product_url=f"https://torob.com/p/torob-{index}",
                    is_already_added=False,
                )
                for index in range(size)
            ]

        async def close(self):
            return None

    class FakeBasalam:
        async def search_products(self, query: str, size: int = 2, page: int = 0):
            return [
                BasalamSearchResult(
                    rank=0,
                    product_id="basalam-1",
                    name="رب باسلام",
                    price=90000,
                    price_text=None,
                    image_url=None,
                    product_url="https://basalam.com/p/basalam-1",
                )
            ]

        async def close(self):
            return None

    client = ProductSearchClient()
    client.torob = FakeTorob()
    client.basalam = FakeBasalam()

    results = await client.search_products("رب")

    assert [item.base_prk for item in results] == ["torob-0", "basalam-1", "torob-1", "torob-2"]
