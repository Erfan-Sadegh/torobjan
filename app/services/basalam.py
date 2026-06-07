from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class BasalamSearchResult:
    rank: int
    product_id: str
    name: str
    price: int | None
    price_text: str | None
    image_url: str | None
    product_url: str | None


class BasalamClient:
    def __init__(self) -> None:
        self.base_url = "https://search.basalam.com"
        self.timeout = 3.0
        self._client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search_products(self, query: str, size: int = 2, page: int = 0) -> list[BasalamSearchResult]:
        client = await self._get_client()
        response = await client.get(
            f"{self.base_url}/ai-engine/api/v2.0/product/search",
            params={
                "q": query,
                "from": max(page, 0) * size,
                "size": size,
            },
            headers={
                "accept": "application/json",
                "user-agent": "Mozilla/5.0 (compatible; Torobjan/1.0)",
            },
        )
        if response.status_code >= 500:
            raise BasalamClientError("basalam_unavailable", "باسلام فعلا پاسخ پایدار نمی‌دهد.")
        response.raise_for_status()
        return parse_basalam_results(response.json(), size=size)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client


class BasalamClientError(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def parse_basalam_results(data: dict, size: int = 2) -> list[BasalamSearchResult]:
    results: list[BasalamSearchResult] = []
    for original_rank, item in enumerate(data.get("products", [])):
        product_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if not product_id or not name:
            continue
        price = _price_rial_to_toman(item.get("price") or item.get("primaryPrice"))
        results.append(
            BasalamSearchResult(
                rank=original_rank,
                product_id=product_id,
                name=name,
                price=price,
                price_text=f"{price:,} تومان" if price else None,
                image_url=_image_url(item.get("photo")),
                product_url=f"https://basalam.com/p/{product_id}",
            )
        )
        if len(results) >= size:
            break
    return results


def _price_rial_to_toman(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value) // 10)
    except (TypeError, ValueError):
        return None


def _image_url(photo: object) -> str | None:
    if not isinstance(photo, dict):
        return None
    return photo.get("MEDIUM") or photo.get("SMALL")
