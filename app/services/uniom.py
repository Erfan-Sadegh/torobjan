from __future__ import annotations

from dataclasses import dataclass
import asyncio
from urllib.parse import quote

import httpx

from app.settings import settings


@dataclass(frozen=True)
class UniomFile:
    file_id: str
    file_path: str


class UniomClient:
    def __init__(self) -> None:
        self.base_url = settings.uniom_base_url.rstrip("/")
        self.token = settings.uniom_bot_token.strip()
        self.timeout = settings.uniom_timeout_seconds
        self._client: httpx.AsyncClient | None = None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_chat(self, chat_id: str) -> dict:
        return await self._get_json("getChat", {"chat_id": chat_id})

    async def get_chat_history(self, chat_id: str, limit: int, offset_id: int | None = None) -> list[dict]:
        params: dict[str, object] = {"chat_id": chat_id, "limit": limit}
        if offset_id is not None:
            params["offset_id"] = offset_id
        data = await self._get_json("getChatHistory", params)
        result = data.get("result")
        if not isinstance(result, list):
            raise UniomClientError("uniom_bad_response", "پاسخ تاریخچه کانال قابل پردازش نبود.")
        return [item for item in result if isinstance(item, dict)]

    async def get_chat_history_paginated(self, chat_id: str, total_limit: int, page_size: int) -> list[dict]:
        page_size = max(1, min(page_size, total_limit))
        messages: list[dict] = []
        seen_message_ids: set[object] = set()
        offset_id: int | None = None
        while len(messages) < total_limit:
            current_limit = min(page_size, total_limit - len(messages))
            page = await self.get_chat_history(chat_id, limit=current_limit, offset_id=offset_id)
            new_page: list[dict] = []
            for item in page:
                message_id = item.get("message_id")
                if message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)
                new_page.append(item)
            if not new_page:
                break
            messages.extend(new_page)
            ids = [_to_int(item.get("message_id")) for item in new_page]
            ids = [item for item in ids if item > 0]
            if not ids:
                break
            offset_id = min(ids) - 1
            if len(page) < current_limit:
                break
            await asyncio.sleep(0.2)
        return messages[:total_limit]

    async def get_file(self, file_id: str) -> UniomFile:
        data = await self._get_json("getFile", {"file_id": file_id})
        result = data.get("result")
        if not isinstance(result, dict):
            raise UniomClientError("uniom_bad_response", "اطلاعات فایل از یونیوم دریافت نشد.")
        file_path = str(result.get("file_path") or "").strip()
        if not file_path:
            raise UniomClientError("uniom_bad_response", "مسیر فایل از یونیوم دریافت نشد.")
        return UniomFile(file_id=file_id, file_path=file_path)

    async def download_file(self, file_path: str) -> bytes:
        if not self.token:
            raise UniomClientError("uniom_not_configured", "توکن یونیوم تنظیم نشده است.")
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/file/bot{self.token}/{quote(file_path, safe='/')}")
        response.raise_for_status()
        return response.content

    async def _get_json(self, method: str, params: dict[str, object]) -> dict:
        if not self.token:
            raise UniomClientError("uniom_not_configured", "توکن یونیوم تنظیم نشده است.")
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/bot{self.token}/{method}", params=params)
        try:
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise UniomClientError("uniom_unavailable", "ارتباط با یونیوم کامل نشد. کمی بعد دوباره تلاش کن.") from exc
        if not isinstance(data, dict) or data.get("ok") is not True:
            raise UniomClientError("uniom_bad_response", "یونیوم پاسخ قابل استفاده برنگرداند.")
        return data

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": "torobjan/0.1"},
            )
        return self._client


class UniomClientError(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def _to_int(value: object) -> int:
    try:
        return int(str(value or ""))
    except ValueError:
        return 0
