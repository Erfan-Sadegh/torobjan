import pytest

from app.services.uniom import UniomClient


@pytest.mark.asyncio
async def test_uniom_history_pagination_deduplicates_and_offsets(monkeypatch) -> None:
    client = UniomClient()
    calls = []
    pages = [
        [{"message_id": 120}, {"message_id": 119}],
        [{"message_id": 118}, {"message_id": 117}],
        [{"message_id": 117}],
    ]

    async def fake_get_chat_history(chat_id: str, limit: int, offset_id: int | None = None):
        calls.append((chat_id, limit, offset_id))
        return pages.pop(0)

    monkeypatch.setattr(client, "get_chat_history", fake_get_chat_history)

    messages = await client.get_chat_history_paginated("@regaal", total_limit=5, page_size=2)

    assert [item["message_id"] for item in messages] == [120, 119, 118, 117]
    assert calls == [("@regaal", 2, None), ("@regaal", 2, 118), ("@regaal", 1, 116)]
