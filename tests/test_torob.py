import pytest
import httpx

from app.services.torob_headers import is_torob_bot_challenge
from app.services.torob import TorobClient, TorobClientError, parse_search_results


def test_parse_search_results_maps_expected_fields() -> None:
    data = {
        "results": [
            {
                "random_key": "90a95ec2",
                "name1": "رب گوجه روژین ۸۰۰ گرم",
                "price": 119000,
                "price_text": "از ۱۱۹٫۰۰۰ تومان",
                "image_url": "https://image.torob.com/a.jpg",
                "web_client_absolute_url": "/p/90a95ec2/test/",
                "is_already_added": True,
            }
        ]
    }

    results = parse_search_results(data, size=5, query="رب گوجه")

    assert len(results) == 1
    assert results[0].base_prk == "90a95ec2"
    assert results[0].name == "رب گوجه روژین ۸۰۰ گرم"
    assert results[0].price == 119000
    assert results[0].product_url == "https://torob.com/p/90a95ec2/test/"
    assert results[0].is_already_added is True


def test_parse_search_results_removes_ads_and_reranks_by_query_tokens() -> None:
    data = {
        "results": [
            {
                "random_key": "ad",
                "name1": "تبلیغ نامرتبط",
                "price": 1,
                "is_adv": True,
            },
            {
                "random_key": "weak",
                "name1": "کنسرو گوجه فرنگی",
                "price": 10,
                "is_adv": False,
            },
            {
                "random_key": "strong",
                "name1": "رب گوجه فرنگی روژین ۸۰۰ گرم",
                "price": 20,
                "is_adv": False,
            },
        ]
    }

    results = parse_search_results(data, size=5, query="رب گوجه روژین")

    assert [item.base_prk for item in results] == ["strong", "weak"]
    assert all(item.base_prk != "ad" for item in results)


def test_bot_challenge_detection_for_torob_490() -> None:
    response = httpx.Response(
        490,
        headers={"content-type": "text/html; charset=utf-8"},
        text="<title>آیا شما یک ربات هستید؟‌ | ترب</title>",
    )

    assert is_torob_bot_challenge(response) is True


@pytest.mark.asyncio
async def test_torob_client_maps_gateway_404(monkeypatch) -> None:
    class FakeAsyncClient:
        async def get(self, *args, **kwargs):
            return httpx.Response(404, text="404 page not found", headers={"content-type": "text/plain"})

        async def aclose(self):
            return None

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: FakeAsyncClient())
    client = TorobClient()

    with pytest.raises(TorobClientError) as exc:
        await client.search_base_products("رب گوجه")

    assert exc.value.code == "torob_gateway_not_found"


@pytest.mark.asyncio
async def test_torob_client_sends_iw1_header(monkeypatch) -> None:
    captured_headers = {}

    class FakeAsyncClient:
        async def get(self, *args, **kwargs):
            captured_headers.update(kwargs["headers"])
            return httpx.Response(200, json={"results": []}, request=httpx.Request("GET", "https://example.test"))

        async def aclose(self):
            return None

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: FakeAsyncClient())
    monkeypatch.setattr("app.services.torob.settings.torob_iw1_header", "test-iw1")
    client = TorobClient()

    await client.search_base_products("رب گوجه")

    assert captured_headers["x-iw1"] == "test-iw1"


@pytest.mark.asyncio
async def test_torob_client_acquires_rate_limit_before_text_request(monkeypatch) -> None:
    events: list[str] = []

    class FakeLimiter:
        async def acquire(self) -> None:
            events.append("limit")

    class FakeAsyncClient:
        async def get(self, *args, **kwargs):
            events.append("get")
            return httpx.Response(200, json={"results": []}, request=httpx.Request("GET", "https://example.test"))

        async def aclose(self):
            return None

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: FakeAsyncClient())
    monkeypatch.setattr("app.services.torob.get_torob_rate_limiter", lambda: FakeLimiter())

    await TorobClient().search_base_products("رب گوجه")

    assert events == ["limit", "get"]


@pytest.mark.asyncio
async def test_torob_client_acquires_rate_limit_for_each_retry(monkeypatch) -> None:
    limit_calls = 0
    request_calls = 0

    class FakeLimiter:
        async def acquire(self) -> None:
            nonlocal limit_calls
            limit_calls += 1

    class FakeAsyncClient:
        async def get(self, *args, **kwargs):
            nonlocal request_calls
            request_calls += 1
            if request_calls == 1:
                raise httpx.ReadTimeout("timeout")
            return httpx.Response(200, json={"results": []}, request=httpx.Request("GET", "https://example.test"))

        async def aclose(self):
            return None

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: FakeAsyncClient())
    monkeypatch.setattr("app.services.torob.get_torob_rate_limiter", lambda: FakeLimiter())
    monkeypatch.setattr("app.services.torob.asyncio.sleep", no_sleep)
    client = TorobClient()
    client.max_retries = 1

    await client.search_base_products("رب گوجه")

    assert request_calls == 2
    assert limit_calls == 2


@pytest.mark.asyncio
async def test_torob_client_rate_limits_image_upload_and_search(monkeypatch) -> None:
    events: list[str] = []

    class FakeLimiter:
        async def acquire(self) -> None:
            events.append("limit")

    class FakeAsyncClient:
        async def post(self, *args, **kwargs):
            events.append("post")
            return httpx.Response(
                200,
                json={"image_url": "https://image.example/upload.jpg"},
                request=httpx.Request("POST", "https://example.test/upload"),
            )

        async def get(self, *args, **kwargs):
            events.append("get")
            return httpx.Response(200, json={"results": []}, request=httpx.Request("GET", "https://example.test/search"))

        async def aclose(self):
            return None

    monkeypatch.setattr("httpx.AsyncClient", lambda **kwargs: FakeAsyncClient())
    monkeypatch.setattr("app.services.torob.get_torob_rate_limiter", lambda: FakeLimiter())

    await TorobClient().search_by_image_bytes(b"image")

    assert events == ["limit", "post", "limit", "get"]
