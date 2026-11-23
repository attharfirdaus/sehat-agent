# CLAUDE.md

Source of truth: `PRD.md`.

## Aturan implementasi

- Semua panggilan LLM lewat Ollama lokal. Dilarang memanggil API LLM cloud (OpenAI, Anthropic, OpenRouter, Gemini), termasuk sebagai fallback.
- Python 3.12 + `uv`. Type hints wajib, Pydantic v2 untuk semua schema I/O. Frontend TypeScript strict.
- Pin versi dependency saat install. Cek versi terbaru di registry, jangan mengandalkan versi dari memori.
- Tidak ada secret di kode. Semua lewat `.env`, sediakan `.env.example`.
- Ambang medis (tekanan darah, BMI, dsb.) disimpan sebagai konstanta di satu modul (`app/risk/guidelines.py`), masing-masing dengan komentar sumber. Jangan mengarang ambang. Kalau ragu, beri komentar `# NEEDS_VERIFICATION` dan catat di bagian 17.
- Komponen deterministik (hitung skor, query DB, trend) adalah fungsi Python biasa, bukan LLM. LLM hanya dipakai untuk: routing intent, ekstraksi bahasa natural, interpretasi, penulisan rekomendasi, dan kritik.
- Kalau spesifikasi ambigu: pilih opsi paling sederhana yang memenuhi acceptance criteria, tulis `TODO(PRD):` di kode, lalu laporkan.
- Jangan menambah fitur atau abstraksi yang tidak diminta PRD.

## Perintah make

- `make dev` — jalankan Postgres (docker compose) + backend FastAPI (reload)
- `make web` — frontend Next.js di :3000 (proxy `/api` ke backend :8000)
- `make test` — pytest backend
- `make lint` — ruff check + ruff format --check, tsc + eslint frontend
- `make migrate` — `alembic upgrade head`
- `make bot` — bot Telegram (TODO, M6)
- `make ingest` — ingestion korpus RAG dari `data/corpus/manifest.yaml`
- `make train` — training model diabetes (XGBoost) ke `backend/models/`
- `make eval` — evaluation harness dengan LLM asli, menulis `eval/report.md`
