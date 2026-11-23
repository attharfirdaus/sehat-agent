"""Hybrid retrieval (PRD bagian 12): top-20 cosine (pgvector) + top-20 full-text, digabung
Reciprocal Rank Fusion, kembalikan top-k."""

import re

from sqlalchemy import func, select

from app.db.models import KbChunk, KbDocument
from app.db.session import SessionLocal
from app.rag.ingest import embed
from app.schemas import Passage

CANDIDATES = 20
RRF_K = 60
# Kandidat vektor di bawah kemiripan ini dibuang, supaya pertanyaan di luar korpus tidak
# mendapat passage. Bukan ambang medis. Kalibrasi 2026-11-21, bge-m3, korpus 12 dokumen:
# 7 pertanyaan relevan >= 0,569; 5 pertanyaan di luar topik <= 0,442.
MIN_SIMILARITY = 0.50


def _or_query(text: str) -> str:
    words = re.findall(r"\w{3,}", text.lower())
    return " | ".join(dict.fromkeys(words))


async def retrieve(query: str, k: int = 5, lang: str | None = None) -> list[Passage]:
    [qvec] = await embed([query])
    distance = KbChunk.embedding.cosine_distance(qvec)
    base = select(KbChunk.id).join(KbDocument)
    if lang:
        base = base.where(KbDocument.lang == lang)
    tsquery = func.to_tsquery("simple", _or_query(query) or "''")
    async with SessionLocal() as session:
        vec_ids = list(
            await session.scalars(
                base.where(1 - distance >= MIN_SIMILARITY).order_by(distance).limit(CANDIDATES)
            )
        )
        if not vec_ids:  # tidak ada yang cukup mirip: anggap di luar korpus
            return []
        fts_ids = list(
            await session.scalars(
                base.where(KbChunk.tsv.op("@@")(tsquery))
                .order_by(func.ts_rank(KbChunk.tsv, tsquery).desc())
                .limit(CANDIDATES)
            )
        )
        scores: dict[int, float] = {}
        for ids in (vec_ids, fts_ids):
            for rank, cid in enumerate(ids, start=1):
                scores[cid] = scores.get(cid, 0.0) + 1 / (RRF_K + rank)
        top = sorted(scores, key=lambda c: -scores[c])[:k]
        rows = {
            c.id: (c, d)
            for c, d in await session.execute(
                select(KbChunk, KbDocument).join(KbDocument).where(KbChunk.id.in_(top))
            )
        }
    return [
        Passage(
            source_id=d.source_id,
            chunk_id=c.id,
            title=d.title,
            url=d.url,
            publisher=d.publisher,
            year=d.year,
            text=c.text,
            score=round(scores[c.id], 5),
        )
        for c, d in (rows[i] for i in top)
    ]
