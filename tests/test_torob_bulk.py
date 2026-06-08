import pytest

from app.services.torob_bulk import TorobBulkAddClient, TorobBulkAddError, TorobBulkAddItem


class FakeResponse:
    status_code = 200
    text = '{"ok": true}'

    def json(self):
        return {"ok": True}


class FakeAsyncClient:
    instances = []

    def __init__(self, *args, **kwargs) -> None:
        self.posts = []
        self.instances.append(self)

    async def post(self, url, json, headers):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return FakeResponse()

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_bulk_add_chunks_items_and_sends_required_payload(monkeypatch) -> None:
    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_key", "secret")
    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_url", "https://api.example/bulk")
    monkeypatch.setattr("app.services.torob_bulk.httpx.AsyncClient", FakeAsyncClient)
    FakeAsyncClient.instances = []
    client = TorobBulkAddClient()
    items = [TorobBulkAddItem(base_product_rk=f"rk-{index}", price=1000 + index) for index in range(105)]

    result = await client.bulk_add(shop_id=94925, items=items)

    fake = FakeAsyncClient.instances[0]
    assert result.sent_count == 105
    assert len(fake.posts) == 2
    assert len(fake.posts[0]["json"]["items"]) == 100
    assert len(fake.posts[1]["json"]["items"]) == 5
    assert fake.posts[0]["json"]["bulk_product_adding_key"] == "secret"
    assert fake.posts[0]["json"]["shop_id"] == 94925
    assert fake.posts[0]["json"]["items"][0] == {"base_product_rk": "rk-0", "price": 1000}


@pytest.mark.asyncio
async def test_bulk_add_requires_secret_key(monkeypatch) -> None:
    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_key", "")
    client = TorobBulkAddClient()

    with pytest.raises(TorobBulkAddError) as exc:
        await client.bulk_add(shop_id=94925, items=[TorobBulkAddItem(base_product_rk="rk", price=1000)])

    assert exc.value.code == "missing_key"
