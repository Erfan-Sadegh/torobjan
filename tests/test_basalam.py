import httpx
import pytest

from app.services.basalam import BasalamClient, parse_basalam_results


def test_parse_basalam_results_converts_rial_price_to_toman() -> None:
    data = {
        "products": [
            {
                "id": 14764302,
                "name": "رب گوجه باسلام",
                "price": 2480000.0,
                "photo": {"MEDIUM": "https://image.example/b.jpg"},
            }
        ]
    }

    results = parse_basalam_results(data, size=2)

    assert len(results) == 1
    assert results[0].product_id == "14764302"
    assert results[0].price == 248000
    assert results[0].product_url == "https://basalam.com/p/14764302"


@pytest.mark.asyncio
async def test_basalam_client_posts_to_openapi_search(monkeypatch) -> None:
    captured = {}

    class FakeAsyncClient:
        async def post(self, url, **kwargs):
            captured["url"] = url
            captured["json"] = kwargs["json"]
            return httpx.Response(
                200,
                json={
                    "products": [
                        {
                            "id": 14764302,
                            "name": "رب گوجه باسلام",
                            "price": 2480000,
                            "photo": {},
                        }
                    ]
                },
                request=httpx.Request("POST", url),
            )

        async def aclose(self):
            return None

    monkeypatch.setattr("httpx.AsyncClient", lambda timeout: FakeAsyncClient())
    client = BasalamClient()

    results = await client.search_products("رب گوجه", size=2, page=3)

    assert captured["url"] == "https://openapi.basalam.com/v1/products/search"
    assert captured["json"] == {"q": "رب گوجه", "rows": 2, "start": 6}
    assert results[0].price == 248000
