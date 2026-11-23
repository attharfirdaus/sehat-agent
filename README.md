# SehatAgent

Spesifikasi: [PRD.md](PRD.md). Status: M0–M5 dan M7 selesai; M6 (Telegram) dilewati
(keputusan 2026-11-21). Semua LLM dan embedding berjalan lokal lewat Ollama.

## Prasyarat

- `uv`, Docker, Node 20+ (pnpm dipanggil lewat `npx`).
- Ollama native: `ollama pull qwen3.5:9b` dan `ollama pull bge-m3`.
- macOS: `brew install libomp` (runtime OpenMP untuk XGBoost).

## Setup sekali

```bash
cp .env.example .env   # EMBED_MODEL=bge-m3, EMBED_DIM=1024, JWT_SECRET acak
make db migrate        # Postgres + skema
make train             # unduh UCI 891 (±11 MB) + latih model diabetes (±1 menit)
make ingest            # ingest korpus data/corpus/ (idempoten per sha256)
```

Kalau port 5432 sudah terpakai, ubah `POSTGRES_PORT` dan port di `DATABASE_URL`.

## Menjalankan

```bash
make dev   # backend :8000
make web   # frontend :3000 (terminal kedua)
```

Buka http://localhost:3000: daftar, isi profil, lalu catat harian di `/chat`: ketik kalimat biasa,
kirim foto makanan, atau buka form check-in lewat tombol formulir di kotak pesan (5 isian wajib +
pengukuran opsional, tanpa LLM untuk ekstraksi; `/chat?form=1` langsung membukanya). Halaman lain:
`/dashboard`, `/settings` (edit profil, hapus akun), `/clinician` (role clinician/admin).

Jadikan user clinician atau admin (belum ada UI untuk ini):

```bash
docker compose exec db psql -U sehat -d sehat -c "UPDATE users SET role='clinician' WHERE email='saya@contoh.id'"
```

## Komponen

| Bagian PRD | Lokasi | Catatan |
| --- | --- | --- |
| Ambang medis (8.1, 13) | `backend/app/risk/guidelines.py` | ACC/AHA 2017 + BMI Asia-Pasifik; semua `NEEDS_VERIFICATION` |
| Framingham non-lab (8.2) | `backend/app/risk/framingham.py` | Pria cocok dengan contoh CVrisk; koefisien wanita belum diverifikasi |
| Model diabetes (8.3) | `backend/ml/`, `backend/models/diabetes_xgb_v1.json` | XGBoost + isotonic + SHAP; metrik di file `.json` |
| RAG (12) | `backend/app/rag/`, `data/corpus/manifest.yaml` | bge-m3 + full-text, RRF; PNPK tanpa bagian farmakoterapi |
| Red flag (13) | `backend/app/safety/` | Deterministik, dicek sebelum dan sesudah LLM |
| Graph (6) | `backend/app/graph/` | Thinking off (lihat `llm.py`) |
| Evaluasi (15) | `eval/` | `make eval` menulis `eval/report.md` |

## API

`/api/chat`, `/api/chat/resume`, dan `/api/checkin` (form check-in) mengalirkan SSE: `node_start`, `token`, `interrupt`,
`chart`, `final`, `error`. Endpoint lain ada di http://localhost:8000/docs.

## Test & lint

```bash
make lint test
```

Test butuh Postgres docker (dijalankan otomatis oleh `make test`) dan memakai database
`sehat_test`. Test tidak butuh Ollama, model terlatih, atau korpus: tool berat di-mock.
