"""Ingestion + hybrid retrieval (bagian 12) dengan embedding palsu deterministik."""

import hashlib
import math
import re
from typing import Any

import pytest
from sqlalchemy import delete

from app.db.models import KbDocument
from app.db.session import SessionLocal
from app.rag import ingest as ing
from app.rag import retrieve as ret

DOC = """<html><body><article><h1>Physical activity</h1>
<p>Adults should do at least 150 to 300 minutes of moderate-intensity aerobic physical
activity per week for substantial health benefits.</p>
<p>Limiting sedentary time and replacing it with physical activity of any intensity
provides health benefits.</p></article></body></html>"""


async def fake_embed(texts: list[str]) -> list[list[float]]:
    """Bag-of-words hashing 1024 dimensi: teks dengan kata sama punya cosine tinggi."""
    out = []
    for t in texts:
        v = [0.0] * 1024
        for w in re.findall(r"\w{3,}", t.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % 1024] += 1
        n = math.sqrt(sum(x * x for x in v)) or 1
        out.append([x / n for x in v])
    return out


def test_drop_repeated_lines_and_chunk() -> None:
    pages = [f"jdih.kemkes.go.id\nIsi halaman {i} tentang hipertensi\n- {i} -" for i in range(5)]
    cleaned = ing.drop_repeated_lines(pages)
    assert all("jdih" not in p and "- " not in p for p in cleaned) and "halaman 3" in cleaned[3]
    text = "\n".join(["BAB I"] + ["kata " * 50] * 12 + ["BAB II"] + ["isi " * 50] * 3)
    chunks = ing.chunk(text)
    assert all(len(c.split()) <= ing.CHUNK_WORDS + ing.OVERLAP_WORDS for c in chunks)
    assert any(c.startswith("BAB II") for c in chunks)  # heading memulai chunk baru
    assert chunks[1].split()[: ing.OVERLAP_WORDS] == chunks[0].split()[-ing.OVERLAP_WORDS :]


@pytest.fixture
def corpus(tmp_path: Any, monkeypatch: pytest.MonkeyPatch, run: Any) -> Any:
    async def clean() -> None:
        async with SessionLocal() as s:
            await s.execute(delete(KbDocument).where(KbDocument.source_id == "TEST-PA"))
            await s.commit()

    run(clean)
    (tmp_path / "TEST-PA.html").write_text(DOC)
    (tmp_path / "MISSING.pdf").write_text("")  # bukan file korpus valid, dan tidak di manifest
    (tmp_path / "manifest.yaml").write_text(
        "documents:\n"
        "  - {source_id: TEST-PA, title: PA test, url: 'https://example.org/pa', publisher: WHO,"
        " year: 2020, lang: en}\n"
        "  - {source_id: TEST-ABSENT, title: x, url: 'https://example.org', publisher: x,"
        " year: null, lang: id}\n"
    )
    monkeypatch.setattr(ing, "embed", fake_embed)
    monkeypatch.setattr(ret, "embed", fake_embed)
    monkeypatch.setattr(ing.settings, "EMBED_MODEL", "fake")
    return tmp_path


def test_ingest_idempotent_and_retrieve(corpus: Any, run: Any) -> None:
    first = run(ing.ingest, corpus)
    assert first["TEST-PA"].startswith("ingested") and first["TEST-ABSENT"] == "missing"
    assert run(ing.ingest, corpus)["TEST-PA"] == "unchanged"

    hits = run(ret.retrieve, "minutes of moderate physical activity per week adults", 3)
    assert hits and hits[0].source_id == "TEST-PA" and hits[0].url == "https://example.org/pa"
    assert "150" in hits[0].text and hits[0].score > 0
    assert run(ret.retrieve, "resep rendang padang", 3) == []
    assert run(ret.retrieve, "physical activity minutes week", 3, "id") == []  # filter bahasa

    (corpus / "TEST-PA.html").write_text(DOC.replace("150", "160"))
    assert run(ing.ingest, corpus)["TEST-PA"].startswith("ingested")  # file berubah -> ulang
