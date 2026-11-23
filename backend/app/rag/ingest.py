"""Ingestion korpus RAG (PRD bagian 12), idempoten berdasarkan sha256 file.

`make ingest` atau `uv run python -m app.rag.ingest` dari backend/.
"""

import asyncio
import hashlib
import re
from collections import Counter
from pathlib import Path

import httpx
import trafilatura
import yaml
from pypdf import PdfReader
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db.models import KbChunk, KbDocument
from app.db.session import SessionLocal
from app.settings import settings

CORPUS = Path(__file__).resolve().parents[3] / "data" / "corpus"
# shortcut: jumlah kata sebagai proxy token (~0,75 kata/token); ganti tokenizer kalau perlu presisi.
CHUNK_WORDS = 450  # ~600 token
OVERLAP_WORDS = 75  # ~100 token
_HEADING = re.compile(
    r"^(BAB [IVXLC]+\b|[A-H]\.\s+\S|[0-9]{1,2}\.\s+[A-Z]|#{1,6}\s|[A-Z][A-Z ,/-]{6,}$)"
)


def drop_repeated_lines(pages: list[str]) -> list[str]:
    """Bersihkan header/footer: baris pendek yang muncul di >= 30% halaman, dan nomor halaman."""
    counts = Counter(ln for p in pages for ln in {x.strip() for x in p.splitlines() if x.strip()})
    repeated = {
        ln
        for ln, n in counts.items()
        if len(pages) >= 4 and n >= 0.3 * len(pages) and len(ln) < 100
    }
    return [
        "\n".join(
            ln
            for ln in p.splitlines()
            if ln.strip() not in repeated and not re.fullmatch(r"\s*-?\s*\d+\s*-?\s*", ln)
        )
        for p in pages
    ]


def extract(path: Path, pages: list[int] | None) -> str:
    if path.suffix == ".pdf":
        reader = PdfReader(path)
        first, last = pages or (1, len(reader.pages))
        texts = [reader.pages[i].extract_text() or "" for i in range(first - 1, last)]
        return "\n".join(drop_repeated_lines(texts))
    return trafilatura.extract(path.read_text(encoding="utf-8"), include_tables=True) or ""


def chunk(text: str) -> list[str]:
    """Potong per paragraf/baris; chunk baru dimulai di heading bila chunk sudah cukup panjang."""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    chunks: list[str] = []
    current: list[str] = []

    def words() -> int:
        return sum(len(ln.split()) for ln in current)

    for ln in filter(None, lines):
        if current and (
            words() + len(ln.split()) > CHUNK_WORDS
            or (_HEADING.match(ln) and words() > CHUNK_WORDS // 3)
        ):
            chunks.append("\n".join(current))
            tail = " ".join(" ".join(current).split()[-OVERLAP_WORDS:])
            current = [] if _HEADING.match(ln) else [tail]
        current.append(ln)
    if current:
        chunks.append("\n".join(current))
    return chunks


async def embed(texts: list[str]) -> list[list[float]]:
    """Embedding lewat Ollama /api/embed (lokal)."""
    out: list[list[float]] = []
    async with httpx.AsyncClient(base_url=settings.OLLAMA_BASE_URL, timeout=300) as client:
        for i in range(0, len(texts), 16):
            r = await client.post(
                "/api/embed", json={"model": settings.EMBED_MODEL, "input": texts[i : i + 16]}
            )
            r.raise_for_status()
            out += r.json()["embeddings"]
    return out


def _file(source_id: str, corpus: Path) -> Path | None:
    return next((p for p in corpus.glob(f"{source_id}.*") if p.suffix in (".pdf", ".html")), None)


async def ingest(corpus: Path = CORPUS) -> dict[str, str]:
    """Return status per source_id: ingested / unchanged / missing."""
    if not settings.EMBED_MODEL:
        raise RuntimeError("EMBED_MODEL belum di-set di .env")
    manifest = yaml.safe_load((corpus / "manifest.yaml").read_text())["documents"]
    status: dict[str, str] = {}
    for doc in manifest:
        sid, path = doc["source_id"], _file(doc["source_id"], corpus)
        if path is None:
            status[sid] = "missing"
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        async with SessionLocal() as session:
            if (
                await session.scalar(select(KbDocument.sha256).where(KbDocument.source_id == sid))
                == sha
            ):
                status[sid] = "unchanged"
                continue
        texts = chunk(extract(path, doc.get("pages")))
        vectors = await embed(texts)
        meta = {k: doc[k] for k in ("title", "url", "publisher", "year", "lang")}
        async with SessionLocal() as session:
            stmt = insert(KbDocument).values(source_id=sid, sha256=sha, **meta)
            await session.execute(
                stmt.on_conflict_do_update(
                    index_elements=["source_id"], set_={"sha256": sha, **meta}
                )
            )
            await session.execute(delete(KbChunk).where(KbChunk.source_id == sid))
            session.add_all(
                KbChunk(source_id=sid, ord=i, text=t, embedding=v)
                for i, (t, v) in enumerate(zip(texts, vectors, strict=True))
            )
            await session.commit()
        status[sid] = f"ingested ({len(texts)} chunk)"
    return status


if __name__ == "__main__":
    for sid, s in asyncio.run(ingest()).items():
        print(f"{sid:28} {s}")
