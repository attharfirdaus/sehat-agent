"""Giliran graph berjalan sebagai task backend: tetap selesai walau koneksi SSE putus."""

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.graph import build
from app.graph.build import RUNS, TurnBusy, follow, start_turn
from tests.test_api_data import register


def test_turn_survives_disconnect_and_can_be_replayed(
    monkeypatch: pytest.MonkeyPatch, run: Any
) -> None:
    gate = asyncio.Event()

    async def slow_turn(
        graph: Any, graph_input: Any, uid: int, channel: str
    ) -> AsyncIterator[dict]:
        yield {"event": "node_start", "data": {"node": "coach"}}
        await gate.wait()  # LLM masih bekerja
        yield {"event": "final", "data": {"text": "selesai"}}

    monkeypatch.setattr(build, "stream_turn", slow_turn)

    async def scenario() -> tuple[list[dict], list[dict]]:
        turn = start_turn(None, None, 999_001, "web")  # type: ignore[arg-type]
        events = follow(turn)
        first = [await anext(events)]
        await events.aclose()  # user pindah halaman: koneksi putus
        with pytest.raises(TurnBusy):
            start_turn(None, None, 999_001, "web")  # type: ignore[arg-type]
        assert 999_001 in RUNS and not turn.done
        gate.set()
        await turn.task  # task tetap jalan sampai selesai
        assert 999_001 not in RUNS
        return first, [e async for e in follow(turn)]  # sambung ulang: diputar dari awal

    first, replay = run(scenario)
    assert first == [{"event": "node_start", "data": {"node": "coach"}}]
    assert [e["event"] for e in replay] == ["node_start", "final"]


def test_reattach_endpoint_and_busy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    uid = register(client)
    assert client.get("/api/chat/stream").status_code == 409  # tidak ada giliran berjalan
    RUNS[uid] = build.TurnRun()  # giliran lain masih berjalan untuk user ini
    try:
        assert client.get("/api/chat/history").json()["running"] is True
        assert client.post("/api/chat", json={"message": "halo"}).status_code == 409
    finally:
        RUNS.pop(uid, None)
