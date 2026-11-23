from app.rag.retrieve import retrieve
from app.schemas import Passage


async def retrieve_guidelines(query: str, k: int = 5, lang: str | None = None) -> list[Passage]:
    """Hybrid retrieval korpus pedoman (vector + full-text, RRF), kembalikan top-k passage.

    Tool ★ untuk History Q&A agent.
    """
    return await retrieve(query, k, lang)
