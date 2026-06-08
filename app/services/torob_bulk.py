from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

import httpx

from app.settings import settings

MAX_ITEMS_PER_REQUEST = 100
MAX_TOTAL_ITEMS = 10_000


@dataclass(frozen=True)
class TorobBulkAddItem:
    base_product_rk: str
    price: int


@dataclass(frozen=True)
class TorobBulkAddResult:
    sent_count: int
    responses: list[Any]

    @property
    def response_text(self) -> str:
        return json.dumps(self.responses, ensure_ascii=False)[:8000]


class TorobBulkAddClient:
    def __init__(self) -> None:
        self.url = settings.torob_bulk_add_url
        self.key = settings.torob_bulk_add_key
        self.timeout = settings.torob_bulk_add_timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def bulk_add(self, shop_id: int, items: list[TorobBulkAddItem]) -> TorobBulkAddResult:
        if not self.key:
            raise TorobBulkAddError("missing_key", "کلید bulk add ترب در تنظیمات سرور قرار نگرفته است.")
        if not items:
            raise TorobBulkAddError("empty_items", "هیچ کالای قابل ارسال مستقیم به ترب در این ثبت نیست.")
        if len(items) > MAX_TOTAL_ITEMS:
            raise TorobBulkAddError("too_many_items", "تعداد کالاها بیشتر از سقف ۱۰۰۰۰ محصول ترب است.")

        responses: list[Any] = []
        sent_count = 0
        client = await self._get_client()
        for chunk in _chunks(items, MAX_ITEMS_PER_REQUEST):
            payload = {
                "bulk_product_adding_key": self.key,
                "shop_id": shop_id,
                "items": [
                    {"base_product_rk": item.base_product_rk, "price": item.price}
                    for item in chunk
                ],
            }
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
            except httpx.TimeoutException as exc:
                raise TorobBulkAddError("timeout", "ارسال به ترب timeout شد. کمی بعد دوباره تلاش کن.") from exc
            except httpx.HTTPError as exc:
                raise TorobBulkAddError("network_error", "ارتباط با endpoint bulk ترب برقرار نشد.") from exc

            if response.status_code in {401, 403}:
                raise TorobBulkAddError("forbidden", "کلید bulk add یا دسترسی فروشگاه توسط ترب تایید نشد.", response)
            if response.status_code >= 400:
                raise TorobBulkAddError("http_error", "ترب برای bulk add پاسخ خطا برگرداند.", response)

            responses.append(_response_json_or_text(response))
            sent_count += len(chunk)

        return TorobBulkAddResult(sent_count=sent_count, responses=responses)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client


class TorobBulkAddError(RuntimeError):
    def __init__(self, code: str, public_message: str, response: httpx.Response | None = None) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = response.status_code if response is not None else None
        self.response_text = response.text[:4000] if response is not None else None


def _chunks(items: list[TorobBulkAddItem], size: int) -> list[list[TorobBulkAddItem]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _response_json_or_text(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text
