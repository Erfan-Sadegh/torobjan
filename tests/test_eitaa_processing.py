import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Submission
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


@pytest.mark.asyncio
async def test_eitaa_text_cache_allows_different_queries_to_run_concurrently() -> None:
    started_count = 0
    both_started = asyncio.Event()

    class ConcurrentTorobClient:
        async def search_base_products(self, query: str, size: int = 5, page: int = 0):
            nonlocal started_count
            started_count += 1
            if started_count == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), timeout=0.2)
            return []

    client = ConcurrentTorobClient()
    cache = {}
    cache_lock = asyncio.Lock()
    await asyncio.gather(
        seller_routes._search_eitaa_text_results(
            client,
            "رب گوجه",
            cache,
            cache_lock,
        ),
        seller_routes._search_eitaa_text_results(
            client,
            "تخم مرغ",
            cache,
            cache_lock,
        ),
    )

    assert started_count == 2


@pytest.mark.asyncio
async def test_eitaa_text_cache_deduplicates_identical_inflight_queries() -> None:
    call_count = 0
    release = asyncio.Event()
    cache = {}
    cache_lock = asyncio.Lock()

    class CountingTorobClient:
        async def search_base_products(self, query: str, size: int = 5, page: int = 0):
            nonlocal call_count
            call_count += 1
            await release.wait()
            return []

    client = CountingTorobClient()
    first = asyncio.create_task(
        seller_routes._search_eitaa_text_results(client, "رب گوجه", cache, cache_lock)
    )
    second = asyncio.create_task(
        seller_routes._search_eitaa_text_results(client, "رب گوجه", cache, cache_lock)
    )
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(first, second)

    assert call_count == 1


@pytest.mark.asyncio
async def test_eitaa_processing_prefetches_images_per_chunk_before_matching(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        submission = Submission(
            store_name="فروشگاه تست",
            source="eitaa",
            source_ref="@test",
            status="processing",
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        submission_id = submission.id

    drafts = [
        EitaaProductDraft(
            message_id=str(index),
            product_name=f"محصول {index}",
            price_toman="1000",
            description=None,
            message_date=None,
            photos=[],
        )
        for index in range(1, 5)
    ]
    events: list[str] = []

    class FakeUniomClient:
        async def get_chat(self, channel_id: str):
            return {}

        async def get_chat_history_paginated(self, *args, **kwargs):
            return []

        async def close(self):
            return None

    class FakeTorobClient:
        async def close(self):
            return None

    async def fake_prefetch(uniom, chunk_drafts, **kwargs):
        events.append("prefetch:" + ",".join(item.message_id for item in chunk_drafts))
        return {}

    async def fake_match(index, draft, row, **kwargs):
        events.append(f"match:{index}")
        return seller_routes.EitaaMatchOutcome(
            index=index,
            row=row,
            draft=draft,
            text_results=[],
            image_outcome=seller_routes.EitaaImageSearchOutcome(results=[]),
        )

    monkeypatch.setattr(seller_routes, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(seller_routes, "UniomClient", FakeUniomClient)
    monkeypatch.setattr(seller_routes, "TorobClient", FakeTorobClient)
    monkeypatch.setattr(seller_routes, "extract_eitaa_products", lambda messages, max_products: drafts)
    monkeypatch.setattr(seller_routes, "_prefetch_eitaa_images", fake_prefetch)
    monkeypatch.setattr(seller_routes, "_match_eitaa_draft", fake_match)
    monkeypatch.setattr(seller_routes.settings, "eitaa_concurrency", 2)

    await seller_routes.process_eitaa_submission(submission_id)

    assert events == [
        "prefetch:1,2",
        "match:1",
        "match:2",
        "prefetch:3,4",
        "match:3",
        "match:4",
    ]


@pytest.mark.asyncio
async def test_eitaa_processing_respects_exact_image_match_limit(monkeypatch, tmp_path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        submission = Submission(
            store_name="فروشگاه تست",
            source="eitaa",
            source_ref="@test",
            status="processing",
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        submission_id = submission.id

    drafts = [
        EitaaProductDraft(
            message_id=str(index),
            product_name=f"محصول {index}",
            price_toman="1000",
            description=None,
            message_date=None,
            photos=[EitaaPhoto(file_id=f"photo-{index}", width=800, height=800)],
        )
        for index in range(1, 5)
    ]
    image_search_count = 0

    class FakeUniomClient:
        async def get_chat(self, channel_id: str):
            return {}

        async def get_chat_history_paginated(self, *args, **kwargs):
            return []

        async def close(self):
            return None

    class FakeTorobClient:
        async def close(self):
            return None

    async def fake_prefetch(uniom, chunk_drafts, **kwargs):
        return {1: b"image"}

    async def fake_text_search(*args, **kwargs):
        return []

    async def fake_image_search(*args, **kwargs):
        nonlocal image_search_count
        image_search_count += 1
        return seller_routes.EitaaImageSearchOutcome(results=[], attempted=True)

    monkeypatch.setattr(seller_routes, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(seller_routes, "UniomClient", FakeUniomClient)
    monkeypatch.setattr(seller_routes, "TorobClient", FakeTorobClient)
    monkeypatch.setattr(seller_routes, "extract_eitaa_products", lambda messages, max_products: drafts)
    monkeypatch.setattr(seller_routes, "_prefetch_eitaa_images", fake_prefetch)
    monkeypatch.setattr(seller_routes, "_search_eitaa_text_results", fake_text_search)
    monkeypatch.setattr(seller_routes, "_search_eitaa_image_results", fake_image_search)
    monkeypatch.setattr(seller_routes.settings, "eitaa_concurrency", 4)
    monkeypatch.setattr(seller_routes.settings, "eitaa_image_match_limit", 1)

    await seller_routes.process_eitaa_submission(submission_id)

    assert image_search_count == 1
