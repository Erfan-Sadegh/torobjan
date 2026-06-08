import pytest
import httpx

from app.services.uniom import UniomClient, UniomClientError


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


@pytest.mark.asyncio
async def test_uniom_history_pagination_reduces_page_size_on_errors(monkeypatch) -> None:
    client = UniomClient()
    calls = []

    async def fake_get_chat_history(chat_id: str, limit: int, offset_id: int | None = None):
        calls.append((chat_id, limit, offset_id))
        if limit > 20:
            raise UniomClientError("uniom_unavailable", "temporary")
        start = offset_id if offset_id is not None else 120
        return [{"message_id": start - index} for index in range(limit)]

    monkeypatch.setattr(client, "get_chat_history", fake_get_chat_history)

    messages = await client.get_chat_history_paginated("@kosarmarket", total_limit=40, page_size=50)

    assert len(messages) == 40
    assert calls[0] == ("@kosarmarket", 40, None)
    assert calls[1] == ("@kosarmarket", 20, None)


@pytest.mark.asyncio
async def test_uniom_download_file_maps_503_to_public_error(monkeypatch) -> None:
    client = UniomClient()
    client.token = "test-token"

    class FakeClient:
        async def get(self, *args, **kwargs):
            return httpx.Response(503, request=httpx.Request("GET", "https://uniom.test/file"))

    async def fake_get_client():
        return FakeClient()

    monkeypatch.setattr(client, "_get_client", fake_get_client)

    with pytest.raises(UniomClientError) as exc:
        await client.download_file("files/photo.jpg")

    assert exc.value.code == "uniom_file_unavailable"
    assert "https://uniom" not in exc.value.public_message
