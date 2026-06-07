from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.services.basalam import BasalamClient, BasalamClientError
from app.services.torob import TorobClient, TorobClientError

BASALAM_EXTRA_WAIT_SECONDS = 0.9


@dataclass(frozen=True)
class ProductSearchResult:
    source: str
    rank: int
    base_prk: str
    name: str
    price: int | None
    price_text: str | None
    image_url: str | None
    product_url: str | None
    is_already_added: bool = False


class ProductSearchClient:
    def __init__(self) -> None:
        self.torob = TorobClient()
        self.basalam = BasalamClient()

    async def close(self) -> None:
        await asyncio.gather(self.torob.close(), self.basalam.close(), return_exceptions=True)

    async def search_products(self, query: str, page: int = 0, per_source: int = 2) -> list[ProductSearchResult]:
        fallback_size = per_source * 2
        torob_size = fallback_size * (page + 1)
        torob_task = asyncio.create_task(self.torob.search_base_products(query, size=torob_size, page=0))
        basalam_task = asyncio.create_task(self.basalam.search_products(query, size=per_source, page=page))
        torob_response = await _task_result(torob_task)
        basalam_response = await _task_result_with_timeout(basalam_task, BASALAM_EXTRA_WAIT_SECONDS)

        torob_results: list[ProductSearchResult] = []
        basalam_results: list[ProductSearchResult] = []
        errors: list[Exception] = []

        if isinstance(torob_response, Exception):
            errors.append(torob_response)
        else:
            basalam_count = len(basalam_response) if not isinstance(basalam_response, Exception) else 0
            page_size = fallback_size - min(basalam_count, per_source)
            page_start = page * page_size
            for result in torob_response[page_start : page_start + page_size]:
                torob_results.append(
                    ProductSearchResult(
                        source="torob",
                        rank=result.rank,
                        base_prk=result.base_prk,
                        name=result.name,
                        price=result.price,
                        price_text=result.price_text,
                        image_url=result.image_url,
                        product_url=result.product_url,
                        is_already_added=result.is_already_added,
                    )
                )

        if isinstance(basalam_response, Exception):
            errors.append(basalam_response)
        else:
            for result in basalam_response:
                basalam_results.append(
                    ProductSearchResult(
                        source="basalam",
                        rank=result.rank,
                        base_prk=result.product_id,
                        name=result.name,
                        price=result.price,
                        price_text=result.price_text,
                        image_url=result.image_url,
                        product_url=result.product_url,
                    )
                )

        combined = _interleave(torob_results, basalam_results)
        if combined:
            return [
                ProductSearchResult(
                    source=result.source,
                    rank=index,
                    base_prk=result.base_prk,
                    name=result.name,
                    price=result.price,
                    price_text=result.price_text,
                    image_url=result.image_url,
                    product_url=result.product_url,
                    is_already_added=result.is_already_added,
                )
                for index, result in enumerate(combined)
            ]

        raise _to_product_search_error(errors)


class ProductSearchError(RuntimeError):
    def __init__(self, code: str, public_message: str) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


def _interleave(*groups: list[ProductSearchResult]) -> list[ProductSearchResult]:
    combined: list[ProductSearchResult] = []
    max_length = max((len(group) for group in groups), default=0)
    for index in range(max_length):
        for group in groups:
            if index < len(group):
                combined.append(group[index])
    return combined


async def _task_result(task: asyncio.Task):
    try:
        return await task
    except Exception as exc:
        return exc


async def _task_result_with_timeout(task: asyncio.Task, timeout: float):
    try:
        return await asyncio.wait_for(task, timeout=timeout)
    except asyncio.TimeoutError:
        task.cancel()
        return BasalamClientError("basalam_timeout", "جستجوی باسلام به موقع آماده نشد.")
    except Exception as exc:
        return exc


def _to_product_search_error(errors: list[Exception]) -> ProductSearchError:
    for error in errors:
        if isinstance(error, TorobClientError):
            return ProductSearchError(error.code, error.public_message)
    for error in errors:
        if isinstance(error, BasalamClientError):
            return ProductSearchError(error.code, error.public_message)
    return ProductSearchError("search_unavailable", "جستجو کامل نشد. دوباره تلاش کن.")
