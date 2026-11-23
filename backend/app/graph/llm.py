"""Akses LLM lokal (Ollama). Semua node memanggil LLM lewat modul ini."""

import asyncio
import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from app.settings import settings

NODE_TIMEOUT_S = 90  # PRD bagian 14
# Menyimpang dari bagian 14 (thinking on untuk Risk Analyst, Coach, Safety Critic), diputuskan A
# 2026-11-21: di M5 16 GB dengan qwen3.5:9b Coach 12 s (off) vs 277 s (on, juga "low"),
# Interpretasi 4 s vs 130 s, melampaui timeout node 90 s. Set True hanya untuk ablation (15).
THINKING = False


def chat(reasoning: bool) -> ChatOllama:
    """`reasoning` = thinking mode (langchain-ollama 1.1.0, terverifikasi)."""
    return ChatOllama(
        model=settings.LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        num_ctx=settings.LLM_NUM_CTX,
        reasoning=reasoning,
    )


def compact(data: Any) -> str:
    """JSON ringkas untuk prompt (PRD: data dikirim sebagai JSON terkompres)."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)


async def structured[T: BaseModel](
    schema: type[T], system: str, user: str, reasoning: bool = False
) -> T | None:
    """Structured output; retry 1x dengan pesan error, None kalau tetap gagal (node fallback)."""
    llm = chat(reasoning).with_structured_output(schema)
    messages: list[Any] = [SystemMessage(system), HumanMessage(user)]
    try:
        async with asyncio.timeout(NODE_TIMEOUT_S):
            for attempt in range(2):
                try:
                    out = await llm.ainvoke(messages)
                    return schema.model_validate(out)
                except Exception as e:  # parse/validasi/koneksi: retry sekali lalu fallback
                    if attempt == 1:
                        return None
                    messages.append(
                        HumanMessage(f"Output sebelumnya tidak valid: {e}. Ulangi sesuai schema.")
                    )
    except TimeoutError:
        return None
    return None
