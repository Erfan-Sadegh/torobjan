from __future__ import annotations

import asyncio
from dataclasses import dataclass
import re

import httpx

from app.settings import settings


@dataclass(frozen=True)
class TorobSearchResult:
    rank: int
    base_prk: str
    name: str
    price: int | None
    price_text: str | None
    image_url: str | None
    product_url: str | None
    is_already_added: bool


class TorobClient:
    def __init__(self) -> None:
        self.base_url = settings.torob_base_url.rstrip("/")
        self.timeout = settings.torob_timeout_seconds
        self.max_retries = settings.torob_max_retries
        self.rate_limit_seconds = settings.torob_rate_limit_seconds
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search_base_products(self, query: str, size: int = 5, page: int = 0) -> list[TorobSearchResult]:
        fetch_size = min(max(size * 3, 12), 24)
        params = {
            "sort": "popularity",
            "query": query,
            "q": query,
            "page": page,
            "size": fetch_size,
            "_search_landing": "search",
            "_landing_page": "home",
            "source": "next_mobile",
        }
        headers = self._request_headers()

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                client = await self._get_client(headers)
                response = await client.get(
                    f"{self.base_url}/v4/base-product/search/",
                    params=params,
                    headers=headers,
                )
                if _is_bot_challenge(response):
                    raise TorobClientError(
                        "torob_bot_challenge",
                        "ترب فعلا درخواست‌های جستجوی خودکار را تایید نمی‌کند. کمی بعد دوباره تلاش کن یا دسترسی ترب را تنظیم کن.",
                    )
                if response.status_code in {401, 403}:
                    raise TorobClientError(
                        "torob_forbidden",
                        "دسترسی gateway ترب تایید نشد. توکن یا مجوز gateway را بررسی کن.",
                    )
                if response.status_code == 404:
                    raise TorobClientError(
                        "torob_gateway_not_found",
                        "مسیر gateway ترب پیدا نشد. تنظیمات یا deploy سرویس gateway را بررسی کن.",
                    )
                if response.status_code == 429:
                    raise TorobClientError(
                        "torob_rate_limited",
                        "gateway ترب فعلا درخواست زیادی دریافت کرده. کمی بعد دوباره تلاش کن.",
                    )
                if response.status_code >= 500:
                    raise TorobClientError(
                        "torob_gateway_error",
                        "gateway ترب فعلا پاسخ پایدار نمی‌دهد. کمی بعد دوباره تلاش کن.",
                    )
                response.raise_for_status()
                data = response.json()
                await asyncio.sleep(self.rate_limit_seconds)
                return parse_search_results(data, size=size, query=query)
            except TorobClientError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 403:
                    raise TorobClientError(
                        "torob_forbidden",
                        "اتصال به ترب مجاز نیست. دسترسی جستجوی پنل ترب برای این درخواست تایید نشد.",
                    ) from exc
                if isinstance(exc, httpx.TimeoutException):
                    last_error = TorobClientError(
                        "torob_timeout",
                        "ارتباط با ترب timeout شد. اگر VPN روشن است خاموشش کن و دوباره تلاش کن.",
                    )
                else:
                    last_error = TorobClientError(
                        "torob_unavailable",
                        "جستجو کامل نشد. دوباره تلاش کن.",
                    )
                if attempt < self.max_retries:
                    await asyncio.sleep(0.4 * (attempt + 1))
        if isinstance(last_error, TorobClientError):
            raise last_error
        raise TorobClientError("torob_unavailable", "جستجو کامل نشد. دوباره تلاش کن.")

    async def search_by_image_bytes(self, image_bytes: bytes, size: int = 5) -> list[TorobSearchResult]:
        headers = self._request_headers(referer="https://torob.com/search-by-image/")
        client = await self._get_client(headers)
        try:
            upload = await client.post(
                f"{self.base_url}/v4/base-product/search-image-upload/",
                files={"img": ("eitaa.jpg", image_bytes, "image/jpeg")},
                headers=headers,
            )
            if _is_bot_challenge(upload):
                raise TorobClientError("torob_bot_challenge", "سرچ تصویری ترب تایید نشد.")
            upload.raise_for_status()
            payload = upload.json()
            image_url = payload.get("image_url")
            if not image_url:
                raise TorobClientError("torob_bad_response", "ترب برای سرچ تصویری image_url برنگرداند.")
            params = {
                "image_url": image_url,
                "discover_method": "search_image_upload",
                "source": "next_mobile",
                "_landing_page": "search-by-image",
                "crop_behavior": "with_initial_unchanged",
            }
            box = payload.get("detected_objects", {}).get("initial", {}).get("box", {})
            if isinstance(box, dict):
                for key in ("x", "y", "w", "h"):
                    if key in box:
                        params[key] = box[key]
            search = await client.get(
                f"{self.base_url}/v4/base-product/search-by-image/",
                params=params,
                headers=headers,
            )
            if _is_bot_challenge(search):
                raise TorobClientError("torob_bot_challenge", "سرچ تصویری ترب تایید نشد.")
            search.raise_for_status()
            await asyncio.sleep(self.rate_limit_seconds)
            return parse_search_results(search.json(), size=size)
        except TorobClientError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            if isinstance(exc, httpx.TimeoutException):
                raise TorobClientError("torob_timeout", "سرچ تصویری ترب timeout شد.") from exc
            raise TorobClientError("torob_unavailable", "سرچ تصویری ترب کامل نشد.") from exc

    def _request_headers(self, referer: str = "https://torob.com/") -> dict[str, str]:
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9,fa;q=0.8",
            "origin": "https://torob.com",
            "referer": referer,
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Linux; Android 13; SM-G981B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Mobile Safari/537.36",
        }
        if settings.torob_proxy_token:
            headers["x-proxy-token"] = settings.torob_proxy_token
        if settings.torob_iw1_header:
            headers["x-iw1"] = settings.torob_iw1_header
        if settings.torob_cookie:
            headers["cookie"] = settings.torob_cookie
        if settings.torob_csrf_token:
            headers["x-csrftoken"] = settings.torob_csrf_token
        return headers

    async def _get_client(self, headers: dict[str, str]) -> httpx.AsyncClient:
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = httpx.AsyncClient(timeout=self.timeout, trust_env=False)
        return self._client


class TorobClientError(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def parse_search_results(data: dict, size: int = 5, query: str = "") -> list[TorobSearchResult]:
    candidates: list[tuple[int, int, TorobSearchResult]] = []
    for original_rank, item in enumerate(data.get("results", [])):
        if item.get("is_adv"):
            continue
        base_prk = str(item.get("random_key") or "").strip()
        name = str(item.get("name1") or "").strip()
        if not base_prk or not name:
            continue
        result = TorobSearchResult(
            rank=original_rank,
            base_prk=base_prk,
            name=name,
            price=_to_int(item.get("price")),
            price_text=item.get("price_text"),
            image_url=item.get("image_url"),
            product_url=_absolute_product_url(item.get("web_client_absolute_url")),
            is_already_added=bool(item.get("is_already_added")),
        )
        candidates.append((_match_score(query, name), original_rank, result))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    results: list[TorobSearchResult] = []
    for display_rank, (_score, _original_rank, result) in enumerate(candidates[:size]):
        results.append(
            TorobSearchResult(
                rank=display_rank,
                base_prk=result.base_prk,
                name=result.name,
                price=result.price,
                price_text=result.price_text,
                image_url=result.image_url,
                product_url=result.product_url,
                is_already_added=result.is_already_added,
            )
        )
    return results


def _is_bot_challenge(response: httpx.Response) -> bool:
    if response.status_code == 490:
        return True
    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return False
    text = response.text[:500]
    return "آیا شما یک ربات هستید" in text or "robot" in text.lower()


def _match_score(query: str, name: str) -> int:
    query_tokens = _tokens(query)
    name_tokens = _tokens(name)
    if not query_tokens or not name_tokens:
        return 0
    name_joined = " ".join(name_tokens)
    score = 0
    for token in query_tokens:
        if token in name_tokens:
            score += 4
        elif token in name_joined:
            score += 2
    if " ".join(query_tokens) in name_joined:
        score += 6
    return score


def _tokens(value: str) -> list[str]:
    text = value.strip().lower()
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return [token for token in re.split(r"[\s,،؛:()/\\|+\-_.]+", text) if len(token) > 1]


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _absolute_product_url(value: object) -> str | None:
    if not value:
        return None
    text = str(value)
    if text.startswith("http"):
        return text
    return f"https://torob.com{text}"
