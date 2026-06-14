import pytest
import httpx

from app.services.torob_bulk import TorobBulkAddClient, TorobBulkAddError, TorobBulkAddItem
from app.services.torob_headers import build_torob_request_headers, is_torob_bot_challenge


def test_build_torob_request_headers_includes_iw1(monkeypatch) -> None:
    monkeypatch.setattr("app.services.torob_headers.settings.torob_iw1_header", "secret-iw1")
    headers = build_torob_request_headers(content_type="application/json")
    assert headers["x-iw1"] == "secret-iw1"
    assert headers["Content-Type"] == "application/json"


def test_bot_challenge_detection_for_bulk_490() -> None:
    response = httpx.Response(
        490,
        headers={"content-type": "text/html; charset=utf-8"},
        text="<title>آیا شما یک ربات هستید؟‌ | ترب</title>",
    )
    assert is_torob_bot_challenge(response) is True


class FakeResponse:
    def __init__(self, status_code: int, text: str = "", json_data: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = {"content-type": "application/json"}
        self._json_data = json_data

    def json(self):
        if self._json_data is None:
            raise ValueError("no json")
        return self._json_data


class FakeAsyncClient:
    instances = []

    def __init__(self, *args, **kwargs) -> None:
        self.posts = []
        self.instances.append(self)

    async def post(self, url, json, headers):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return FakeResponse(200, '{"ok": true}', {"ok": True})

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_bulk_add_chunks_items_and_sends_required_payload(monkeypatch) -> None:
    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_key", "secret")
    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_url", "https://api.example/bulk")
    monkeypatch.setattr("app.services.torob_bulk.settings.torob_iw1_header", "test-iw1")
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
    assert fake.posts[0]["headers"]["x-iw1"] == "test-iw1"


@pytest.mark.asyncio
async def test_bulk_add_requires_secret_key(monkeypatch) -> None:
    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_key", "")
    client = TorobBulkAddClient()

    with pytest.raises(TorobBulkAddError) as exc:
        await client.bulk_add(shop_id=94925, items=[TorobBulkAddItem(base_product_rk="rk", price=1000)])

    assert exc.value.code == "missing_key"


@pytest.mark.asyncio
async def test_bulk_add_maps_490_to_bot_challenge(monkeypatch) -> None:
    class BotChallengeClient:
        instances = []

        def __init__(self, *args, **kwargs) -> None:
            self.instances.append(self)

        async def post(self, url, json, headers):
            return httpx.Response(490, text="robot", headers={"content-type": "text/html"})

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_key", "secret")
    monkeypatch.setattr("app.services.torob_bulk.httpx.AsyncClient", BotChallengeClient)
    client = TorobBulkAddClient()

    with pytest.raises(TorobBulkAddError) as exc:
        await client.bulk_add(shop_id=94925, items=[TorobBulkAddItem(base_product_rk="rk", price=1000)])

    assert exc.value.code == "bot_challenge"


@pytest.mark.asyncio
async def test_bulk_health_check_uses_empty_items(monkeypatch) -> None:
    captured_payloads: list[dict] = []

    class HealthClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def post(self, url, json, headers):
            captured_payloads.append(json)
            return FakeResponse(400, '{"items":["required"]}')

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("app.services.torob_bulk.settings.torob_bulk_add_key", "real-key")
    monkeypatch.setattr("app.services.torob_bulk.httpx.AsyncClient", HealthClient)
    client = TorobBulkAddClient()

    result = await client.health_check()

    assert captured_payloads == [{"bulk_product_adding_key": "real-key", "shop_id": 0, "items": []}]
    assert result.outcome == "reachable"


@pytest.mark.asyncio
async def test_bulk_health_check_detects_bot_challenge(monkeypatch) -> None:
    class HealthClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def post(self, url, json, headers):
            return httpx.Response(490, text="robot", headers={"content-type": "text/html"})

        async def aclose(self) -> None:
            return None

    monkeypatch.setattr("app.services.torob_bulk.httpx.AsyncClient", HealthClient)
    client = TorobBulkAddClient()

    result = await client.health_check()

    assert result.outcome == "bot_challenge"
