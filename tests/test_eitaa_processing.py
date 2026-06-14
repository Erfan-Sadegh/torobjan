import asyncio
from unittest.mock import AsyncMock

import pytest

from app.routes import seller as seller_routes
from app.services.eitaa import EitaaPhoto, EitaaProductDraft
from app.services.torob import TorobSearchResult


@pytest.mark.asyncio
async def test_match_eitaa_draft_runs_text_and_image_in_parallel(monkeypatch) -> None:
    events: list[str] = []

    async def fake_text_search(torob, product_name, cache, cache_lock=None):
        events.append("text_start")
        await asyncio.sleep(0.05)
        events.append("text_end")
        return [
            TorobSearchResult(
                rank=0,
                base_prk="rk-1",
                name=product_name,
                price=1000,
                price_text=None,
                image_url=None,
                product_url=None,
                is_already_added=False,
            )
        ]

    async def fake_image_search(uniom, torob, row, draft, prefetched_image_bytes=None):
        events.append("image_start")
        await asyncio.sleep(0.05)
        events.append("image_end")
        return seller_routes.EitaaImageSearchOutcome(results=[], attempted=True)

    monkeypatch.setattr(seller_routes, "_search_eitaa_text_results", fake_text_search)
    monkeypatch.setattr(seller_routes, "_search_eitaa_image_results", fake_image_search)
    monkeypatch.setattr(seller_routes.settings, "eitaa_image_match_enabled", True)
    monkeypatch.setattr(seller_routes.settings, "eitaa_image_match_limit", 10)

    draft = EitaaProductDraft(
        message_id="1",
        product_name="رب گوجه",
        price_toman="1000",
        description=None,
        message_date=None,
        photos=[EitaaPhoto(file_id="photo-1", width=800, height=800)],
    )
    row = seller_routes.SubmissionRow(submission_id=1, input_row=1, input_product_name="رب گوجه")

    outcome = await seller_routes._match_eitaa_draft(
        index=1,
        draft=draft,
        row=row,
        uniom=AsyncMock(),
        torob=AsyncMock(),
        prefetched_images={1: b"image-bytes"},
        text_search_cache={},
        cache_lock=asyncio.Lock(),
        image_match_attempts=0,
        image_matching_blocked=False,
    )

    assert outcome.torob_error is None
    assert events.index("image_start") < events.index("text_end")
    assert events.index("text_start") < events.index("image_end")
