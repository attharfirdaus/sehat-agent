# PRD — SehatAgent: Multi-Agent Personal Health Consultant (LangGraph + Local LLM)

Nov 17, 2026 · @Atthar

## 0. Instruksi untuk Claude Code

PRD ini adalah source of truth untuk implementasi. Kerjakan per milestone sesuai urutan di bawah. Setiap milestone harus berakhir dengan sesuatu yang bisa dijalankan dan test yang lulus.

**Aturan implementasi**

- Semua panggilan LLM lewat Ollama lokal. Dilarang memanggil API LLM cloud (OpenAI, Anthropic, OpenRouter, Gemini), termasuk sebagai fallback.
- Python 3.12 + `uv`. Type hints wajib, Pydantic v2 untuk semua schema I/O. Frontend TypeScript strict.
- Pin versi dependency saat install. Cek versi terbaru di registry, jangan mengandalkan versi dari memori.
- Tidak ada secret di kode. Semua lewat `.env`, sediakan `.env.example`.
- Ambang medis (tekanan darah, BMI, dsb.) disimpan sebagai konstanta di satu modul (`app/risk/guidelines.py`), masing-masing dengan komentar sumber. Jangan mengarang ambang. Kalau ragu, beri komentar `# NEEDS_VERIFICATION` dan catat di bagian 17.
- Komponen deterministik (hitung skor, query DB, trend) adalah fungsi Python biasa, bukan LLM. LLM hanya dipakai untuk: routing intent, ekstraksi bahasa natural, interpretasi, penulisan rekomendasi, dan kritik.
- Kalau spesifikasi ambigu: pilih opsi paling sederhana yang memenuhi acceptance criteria, tulis `TODO(PRD):` di kode, lalu laporkan.
- Jangan menambah fitur atau abstraksi yang tidak diminta PRD.

**Urutan milestone**

1. **M0 Scaffold:** monorepo, `docker-compose` (PostgreSQL + pgvector), Alembic, health check ke Ollama, Makefile.
2. **M1 Data & API dasar:** schema DB (bagian 9), auth, profile, daily log, measurement.
3. **M2 Risk tools:** guideline flags, Framingham non-lab, training script + inference ML diabetes + SHAP (bagian 8).
4. **M3 RAG:** ingestion dokumen + tool retrieve (bagian 12).
5. **M4 Graph LangGraph:** state, semua node, checkpointer Postgres, endpoint SSE (bagian 6–7, 10).
6. **M5 Frontend:** onboarding, chat, dashboard, settings, halaman clinician (bagian 10).
7. **M6 Telegram + scheduler:** account linking, chat, reminder, weekly report (bagian 11).
8. **M7 Nutrition (foto), HITL clinician, evaluation harness** (bagian 6, 15).

Definition of done per milestone: `make test` hijau, `make dev` jalan, README diperbarui dengan cara menjalankan fitur tersebut.

## 1. Ringkasan & latar belakang

SehatAgent (nama kerja) adalah re-implementasi project "Personal Health Consultant Agent" Kelompok 2 KS: dari workflow n8n + LLM cloud menjadi web app multi-agent LangGraph dengan LLM yang berjalan lokal, ditambah enam layanan baru. Sistem membantu pencegahan penyakit tidak menular (PTM) lewat pencatatan gaya hidup harian, penilaian risiko berbasis aturan klinis dan model ML, serta rekomendasi bertahap yang disertai sitasi.

**Versi lama (n8n) dan masalah yang harus diperbaiki**

| Aspek | Versi n8n | Masalah | Perbaikan di versi ini |
| --- | --- | --- | --- |
| Agent | 1 node AI Agent, 1 tool Mongo `find` tanpa query | Pipeline deterministik + 1 LLM call. Klaim RAG/search engine tidak terimplementasi | Multi-agent LangGraph + RAG pgvector dengan sitasi |
| LLM | `z-ai/glm-4.5-air:free` via OpenRouter | Cloud, data kesehatan keluar ke pihak ketiga | `qwen3.5:9b` via Ollama, lokal |
| Model risiko | Random Forest dilatih pada label hasil rule buatan sendiri (dataset Kaggle sintetis) | Sirkular: akurasi 89% hanya mengukur seberapa baik RF meniru rule | Guideline flags + Framingham non-lab + ML diabetes dari data survei CDC BRFSS 2015 |
| Longitudinal | Prediksi hanya dari record terbaru | Klaim analisis tren tidak sesuai implementasi | Tool `compute_trends` (delta, slope 7/30 hari) |
| Input | Form 14 field setiap hari, termasuk kolesterol dan riwayat keluarga | Data statis/lab diminta harian, sehingga kualitas data buruk | Pisah profile, daily log, measurement. Input bahasa natural + foto |
| Identitas Telegram | `telegram_id` di query param link form | Bisa dipalsukan | Deep link `/start <token>` sekali pakai |
| Dashboard | QuickChart + ScreenshotOne | Ketergantungan layanan eksternal. API key ter-hardcode di workflow JSON | Recharts di web, PNG matplotlib untuk Telegram |
| Latensi | Rata-rata ±2 menit (8 percobaan) | Banyak layanan eksternal berurutan | Diukur ulang sebagai baseline pembanding |

Catatan keamanan: access key ScreenshotOne di `n8n Workflow.json` versi lama harus di-rotate. Jangan menyalin nilainya ke repo baru.

## 2. Tujuan, non-goals, success metrics

**Tujuan**

- G1: Semua reasoning berjalan di LLM lokal (MacBook Pro M5, 16 GB), tanpa satu pun panggilan LLM cloud.
- G2: Multi-agent dengan peran yang jelas, bukan satu prompt besar.
- G3: Menyediakan layanan yang tidak ada di versi n8n: input bahasa natural, estimasi gizi dari foto, Q&A atas histori sendiri, RAG bersitasi, safety critic, weekly report, review tenaga medis (HITL).
- G4: Setiap rekomendasi bisa ditelusuri ke data user dan ke sumber pedoman.

**Non-goals**

- Diagnosis medis atau saran obat.
- Integrasi wearable atau Apple Health.
- Deployment produksi, multi-tenant skala besar, aplikasi mobile native.
- Fine-tuning LLM.
- Mempertahankan dataset Kaggle sintetis dan Random Forest versi lama.

**Success metrics.** Angka di bawah adalah target yang kami tetapkan, bukan hasil. Hasil sebenarnya diisi setelah evaluasi (bagian 15).

| Metrik | Cara ukur | Target |
| --- | --- | --- |
| Panggilan LLM cloud | Audit log HTTP keluar + code search | 0 |
| Latensi check-in harian end-to-end (p50) | Timer di Response node, 20 run | Lebih cepat dari baseline n8n (±2 menit) |
| Akurasi ekstraksi field Intake | Test set 30 kalimat berlabel | ≥ 90% per field |
| Coverage sitasi | % butir rekomendasi yang punya ≥ 1 `source_id` valid | 100% |
| Recall red flag | 15 kasus sintetis berisiko tinggi | 100% (deterministik) |
| Groundedness | % angka di respons yang cocok dengan data user | 100% pada test set |

## 3. Persona & user stories

**Persona**

- **User:** mahasiswa atau pekerja muda (umumnya 18–35 tahun) yang ingin memantau gaya hidup. Tidak punya alat ukur lab di rumah. Paling sering berinteraksi lewat Telegram, membuka web untuk dashboard.
- **Clinician reviewer:** tenaga medis yang meninjau kasus yang ditandai berisiko tinggi, lewat halaman web.
- **Admin/peneliti (tim):** mengelola korpus RAG, melihat trace agent, menjalankan evaluasi.

**User stories** (ID dirujuk di bagian 4 dan 15)

| ID | Sebagai | Saya ingin | Acceptance criteria |
| --- | --- | --- | --- |
| US-01 | User | Mendaftar dan mengisi profil sekali | Profil statis tidak diminta ulang. Bisa diedit di Settings |
| US-02 | User | Mencatat aktivitas dengan kalimat biasa ("jalan 6rb langkah, tidur 5 jam") | Field terisi otomatis. Kalau ada field wajib yang kosong, agent bertanya balik maksimal 2 kali. User bisa konfirmasi atau koreksi sebelum disimpan |
| US-03 | User | Mengirim foto makanan | Agent menampilkan estimasi makanan + kalori dengan rentang, user konfirmasi, lalu tersimpan ke log hari itu |
| US-04 | User | Mendapat penilaian risiko yang jujur | Skor yang tidak berlaku untuk usia saya ditulis "tidak berlaku", bukan dipaksakan |
| US-05 | User | Mendapat rencana bertahap 4 minggu | Rencana menyebut faktor risiko dari data saya, setiap butir punya sitasi, ada disclaimer |
| US-06 | User | Bertanya tentang histori saya ("kenapa tidur saya memburuk minggu ini?") | Jawaban memakai angka dari DB, bukan karangan |
| US-07 | User | Bertanya info kesehatan umum | Jawaban dari korpus RAG dengan sitasi. Kalau tidak ada di korpus, agent bilang tidak tahu |
| US-08 | User | Diingatkan mencatat setiap hari lewat Telegram | Reminder 17.00 WIB, hanya untuk user yang belum mencatat hari itu |
| US-09 | User | Mendapat laporan mingguan | Setiap Minggu: ringkasan tren + kepatuhan terhadap rencana + chart |
| US-10 | User | Diberi tahu segera jika ada tanda bahaya | Red flag selalu memunculkan pesan rujukan, tidak bisa dihapus oleh LLM |
| US-11 | Clinician | Meninjau rekomendasi untuk kasus berisiko tinggi sebelum dikirim | Antrian review. Approve, edit, atau reject. Graph melanjutkan setelah keputusan |
| US-12 | Admin | Menambah dokumen pedoman ke korpus | Script ingestion idempoten. Metadata sumber tersimpan |

## 4. Scope fitur

Semua fitur masuk scope. Prioritas menentukan urutan pengerjaan dan apa yang dipotong jika hari ke-6 belum terintegrasi. Must harus jalan end-to-end saat demo.

| ID | Fitur | Prioritas | User story | Milestone |
| --- | --- | --- | --- | --- |
| F-01 | Auth + onboarding profil | Must | US-01 | M1, M5 |
| F-02 | Intake bahasa natural + klarifikasi (`interrupt`) | Must | US-02 | M4 |
| F-03 | Risk tools: guideline flags, Framingham non-lab, ML diabetes + SHAP, trend | Must | US-04 | M2 |
| F-04 | RAG korpus pedoman + sitasi | Must | US-05, US-07 | M3 |
| F-05 | Coach: rencana 4 minggu | Must | US-05 | M4 |
| F-06 | Safety Critic + red flags deterministik | Must | US-10 | M4 |
| F-07 | History Q&A agent | Must | US-06 | M4 |
| F-08 | Web chat (SSE streaming) + dashboard | Must | US-02, US-06 | M5 |
| F-09 | Telegram: account linking, chat, reminder harian | Must | US-08 | M6 |
| F-10 | Nutrition: foto makanan → estimasi kalori | Should | US-03 | M7 |
| F-11 | Weekly report (web + Telegram PNG) | Should | US-09 | M6 |
| F-12 | Clinician review (HITL) + halaman antrian | Could | US-11 | M7 |
| F-13 | Evaluation harness + tracing | Must | — | M7 |

Urutan pemotongan jika terlambat: F-12 halaman UI (backend `interrupt` tetap ada), lalu F-11, lalu F-10.

## 5. Arsitektur sistem & tech stack

&#91;embedded content: arsitektur komponen · 1 laptop + Telegram API\]

Web masuk lewat FastAPI. Bot Telegram mengimpor graph yang sama secara langsung (in-process). Keduanya memakai checkpointer Postgres yang sama, sehingga percakapan bisa berpindah channel.

| Layer | Pilihan | Catatan |
| --- | --- | --- |
| LLM runtime | Ollama, native di macOS | Engine MLX menjadi default di Apple Silicon sejak v0.30. Model `qwen3.5:9b` (teks + gambar + tools) |
| Agent framework | LangGraph (Python) 1.2.x + `langchain-ollama` | Checkpointer `langgraph-checkpoint-postgres` (async) |
| Backend | FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 | SSE via `sse-starlette` |
| Database | PostgreSQL 16+ dengan pgvector | Docker image `pgvector/pgvector` |
| ML | XGBoost atau LightGBM, scikit-learn, SHAP, joblib | Training offline, inference in-process |
| RAG | `pypdf`, `trafilatura`, embedding via Ollama | Hybrid retrieval: vector + full-text |
| Telegram | `python-telegram-bot[job-queue]` | Long polling, job\_queue untuk scheduler |
| Frontend | Next.js (App Router, TypeScript), Tailwind, shadcn/ui, Recharts | Chart dirender dari JSON |
| Chart untuk Telegram | matplotlib | PNG |
| Tracing | Arize Phoenix (Docker), opsional | Hanya lokal |
| Tooling | `uv`, `ruff`, `pytest`, `pnpm` | `make dev / test / eval` |

## 6. Desain multi-agent LangGraph

&#91;embedded content: graph utama · 1 cek darurat, 4 jalur intent, 1 loop revisi\]

Setiap pesan melewati cek darurat deterministik sebelum menyentuh LLM. Check-in yang lengkap menjalankan pipeline penuh: risiko, RAG, Coach, Critic. Pertanyaan histori dan info kesehatan langsung menuju Response.

### 6.1 State

```python
# app/graph/state.py
from typing import Annotated, Literal, TypedDict
from langgraph.graph.message import add_messages

Intent = Literal["log", "photo", "history_question", "health_info", "smalltalk"]

class GraphState(TypedDict, total=False):
    # input
    user_id: int
    channel: Literal["web", "telegram"]
    messages: Annotated[list, add_messages]
    image_b64: str | None
    # context (load_context)
    profile: dict
    recent_logs: list[dict]          # 14 hari terakhir
    # routing
    red_flags: list[dict]
    intent: Intent
    # intake / nutrition
    draft_log: dict | None
    meal_estimate: dict | None
    log_complete: bool
    # assessment
    flags: list[dict]
    framingham: dict
    diabetes: dict
    trends: dict
    passages: list[dict]
    plan_draft: dict | None
    critique: dict | None
    revision_count: int
    needs_clinician: bool
    # output
    final_response: str
    chart_payload: dict | None
    timings: dict[str, int]          # ms per node → agent_runs
```

### 6.2 Node

| Node | Jenis | Thinking | Tugas | Fallback jika gagal |
| --- | --- | --- | --- | --- |
| `load_context` | deterministik | — | Ambil profil + 14 hari log + plan aktif | — |
| `red_flag_precheck` | deterministik | — | `red_flag_rules` pada teks + measurement terbaru | — |
| `emergency_response` | deterministik | — | Kirim template darurat, simpan `red_flag_events`, END | — |
| `supervisor` | LLM | off | Klasifikasi intent. Kalau `image_b64` ada, langsung `photo` tanpa LLM | `smalltalk` + minta user memperjelas |
| `intake` | LLM | off | Ekstraksi `DailyLogIn` + `MeasurementIn[]` dari teks. `interrupt` untuk field wajib yang kosong (maks 2 kali), lalu `interrupt` konfirmasi | Form ringkas di web / template di Telegram |
| `nutrition` | LLM vision | off | `estimate_meal_from_image`, lalu `interrupt` konfirmasi atau koreksi | Minta user mengetik makanannya |
| `save_log` | deterministik | — | Upsert, set `log_complete` (steps, sleep, water, smoked, alcohol terisi) | — |
| `risk_analyst` | tools + LLM | on | Panggil 4 tool risiko + `compute_trends`. LLM hanya menulis ringkasan interpretasi (≤ 120 kata) | Ringkasan template dari flags |
| `knowledge` | tools + LLM | off | LLM membuat 2–3 query dari flags, panggil `retrieve_guidelines`, deduplikasi passage | Query default per flag code |
| `coach` | LLM | on | Draf plan 4 minggu (structured, tiap aksi punya `citations`). Membaca plan sebelumnya + kepatuhan | — |
| `safety_critic` | kode + LLM | on | Cek bagian 13. Set `critique.pass`, `needs_clinician` (urgent flag atau diabetes band `high`) | `safe_fallback` |
| `safe_fallback` | deterministik | — | Flags + saran umum template + sitasi | — |
| `create_review` | deterministik | — | Simpan plan `pending_review`, buat `clinician_reviews`, jalankan thread review terpisah | — |
| `history_qa` | LLM + tools | on | ReAct terbatas: maks 4 tool call, hanya 4 tool ★ bagian 7 | Jawab dengan `compute_trends` 7 hari |
| `knowledge_info` | tools + LLM | off | Jawab pertanyaan umum dari passage. Jika skor retrieval rendah, katakan tidak ada di korpus | — |
| `response` | LLM | off | Format akhir per channel, sisipkan disclaimer + chip sitasi, isi `chart_payload`, tulis `agent_runs` | Render template tanpa LLM |

### 6.3 Routing & interrupt

```python
# app/graph/build.py (ringkas)
def route_after_precheck(s): return "emergency_response" if is_emergency(s["red_flags"]) else "supervisor"
def route_intent(s): return {"log": "intake", "photo": "nutrition", "history_question": "history_qa",
                              "health_info": "knowledge_info", "smalltalk": "response"}[s["intent"]]
def route_after_save(s): return "risk_analyst" if s["log_complete"] else "response"
def route_after_critic(s):
    if s["critique"]["pass"]:
        return "create_review" if s["needs_clinician"] else "response"
    return "coach" if s["revision_count"] < 2 else "safe_fallback"

graph = builder.compile(checkpointer=AsyncPostgresSaver(...))   # thread_id = f"user-{user_id}"
```

**Kontrak payload `interrupt`** (frontend dan bot Telegram merender berdasarkan `type`):

| type | Payload | Nilai resume |
| --- | --- | --- |
| `clarify` | `{question, missing: [field]}` | teks jawaban user |
| `confirm_log` | `{log: DailyLogIn, measurements: [...]}` | `{"action": "confirm"}` atau `{"action": "edit", "log": {...}}` |
| `confirm_meal` | `{estimate: MealEstimate}` | `{"action": "confirm"}` / `{"action": "edit", "items": [...]}` / `{"action": "cancel"}` |
| `clinician_review` | `{review_id, plan, assessment}` | `{decision, edited_content?, note?}` |

**Clinician review tidak boleh memblokir thread user.** Kalau review memakai `interrupt` di thread `user-{id}`, pesan user berikutnya akan dianggap sebagai resume. Karena itu `create_review` menjalankan subgraph kecil di thread `review-{plan_id}`: `interrupt(clinician_review)` → terapkan keputusan → plan `active`/`rejected` → notifikasi user (web + Telegram). Sementara menunggu, user diberi tahu bahwa rencananya sedang ditinjau. Flags dan data tetap ditampilkan.

**Weekly report** adalah graph terpisah (`thread_id = report-{user_id}-{iso_week}`): `load_context → compute_trends → coach(mode="weekly") → safety_critic → response`, dipicu oleh `job_queue` (bagian 11).

## 7. Spesifikasi tools

Semua tool adalah fungsi Python async yang deterministik, di `app/tools/`, dengan I/O Pydantic. Node memanggilnya langsung. Hanya History Q&A agent yang diberi tool via `bind_tools`, dan dibatasi 4 tool (ditandai ★). Setiap tool punya unit test.

```python
# app/tools/data.py
async def save_daily_log(user_id: int, log: DailyLogIn) -> DailyLogOut: ...
async def save_measurement(user_id: int, m: MeasurementIn) -> MeasurementOut: ...
async def get_profile(user_id: int) -> Profile: ...
★ async def query_history(user_id: int, metrics: list[Metric], days: int = 7) -> HistoryTable: ...
    # Metric = Literal["steps","sleep_hours","water_l","calories","smoked","alcohol",
    #                  "systolic","diastolic","resting_hr","weight_kg","cholesterol"]
    # days dibatasi 1..90

# app/tools/analytics.py
★ async def compute_trends(user_id: int, days: int = 7) -> TrendReport: ...
    # per metrik: mean, min, max, delta vs periode sebelumnya, slope (OLS per hari),
    # n_observasi, kepatuhan terhadap target plan aktif (%). Tanpa LLM.

# app/tools/risk.py
async def guideline_flags(profile: Profile, latest: LatestValues) -> list[Flag]: ...
    # Flag(code, severity: Literal["info","warn","urgent"], metric, value, threshold, source_id)
async def framingham_nonlab(profile: Profile, latest: LatestValues) -> FraminghamResult: ...
    # FraminghamResult(applicable: bool, reason: str|None, risk_10y_pct: float|None, category)
async def predict_diabetes(features: DiabetesFeatures) -> DiabetesPrediction: ...
    # DiabetesPrediction(prob: float, band: Literal["low","moderate","high"],
    #                    top_factors: list[ShapFactor], model_version: str)

# app/tools/knowledge.py
★ async def retrieve_guidelines(query: str, k: int = 5, lang: str | None = None) -> list[Passage]: ...
    # Passage(source_id, chunk_id, title, url, publisher, year, text, score)

# app/tools/plan.py
★ async def get_active_plan(user_id: int) -> Plan | None: ...
async def save_plan(user_id: int, plan: PlanIn) -> Plan: ...

# app/tools/nutrition.py
async def estimate_meal_from_image(image_b64: str, note: str | None) -> MealEstimate: ...
    # memanggil qwen3.5:9b (vision) dengan structured output:
    # MealEstimate(items: list[FoodItem(name, portion, kcal_low, kcal_high)], confidence, caveats)

# app/tools/safety.py
async def red_flag_rules(latest: LatestValues, user_text: str) -> list[RedFlag]: ...
    # deterministik: ambang angka + keyword gejala (bagian 13). Tanpa LLM.

# app/tools/charts.py
async def build_chart_payload(trends: TrendReport) -> ChartPayload: ...   # JSON untuk Recharts
async def render_chart_png(trends: TrendReport) -> bytes: ...             # matplotlib, untuk Telegram
```

Aturan: tool tidak pernah mengembalikan string bebas untuk dipakai LLM sebagai fakta. Selalu objek terstruktur. Prompt menerima versi JSON ringkas dari objek tersebut.

## 8. Risk layer

Risiko dinilai oleh tiga komponen deterministik. LLM hanya menginterpretasi outputnya, tidak pernah menghitung sendiri.

### 8.1 Guideline flags (berlaku untuk semua usia)

Nilai di tabel ini adalah draft dari pengetahuan umum. Anggota C wajib memverifikasi ke dokumen sumber sebelum dikunci di `app/risk/guidelines.py`, lalu mengisi kolom sumber dengan `source_id` korpus RAG.

| Metrik | Kategori / ambang (draft) | Acuan yang dicek | Severity |
| --- | --- | --- | --- |
| Tekanan darah | Normal <120/<80. Elevated 120–129/<80. Hipertensi st.1 130–139 atau 80–89. St.2 ≥140 atau ≥90 | ACC/AHA 2017. Tim memutuskan: pakai ini atau ISH 2020 / PERHI | warn (st.1–2) |
| Tekanan darah krisis | ≥180 sistolik atau ≥120 diastolik | ACC/AHA 2017 | urgent |
| BMI (Asia-Pasifik) | <18,5 kurang. 18,5–22,9 normal. 23–24,9 overweight. ≥25 obesitas | WHO WPRO 2000 / WHO expert consultation 2004. Bandingkan dengan cut-off Kemenkes | warn |
| Aktivitas | Target 150–300 menit aktivitas sedang per minggu. Langkah harian dipakai sebagai proxy | WHO 2020 physical activity guidelines | info/warn |
| Tidur | <7 jam per malam (dewasa) | AASM/SRS consensus 2015 | info/warn |
| Kolesterol total | <200 diinginkan. 200–239 batas tinggi. ≥240 tinggi (mg/dL) | NCEP ATP III | warn |
| Resting HR | >100 bpm saat istirahat | Definisi takikardia umum | warn |
| Merokok | Setiap hari merokok tercatat | WHO tobacco fact sheet | warn |

Aturan: flag dari measurement yang lebih tua dari 90 hari diberi label "data lama" dan tidak memicu urgent.

### 8.2 Framingham 2008 non-laboratory (general CVD, 10 tahun)

- Implementasi dari D'Agostino et al., *Circulation* 2008;117:743–753, persamaan non-lab berbasis BMI, koefisien per jenis kelamin.
- Input: usia, sex, BMI, sistolik, `bp_treated`, `smoker`, `diabetes`. `bp_treated` dan `diabetes` diambil dari profil (pertanyaan onboarding baru).
- **Gate usia 30–74.** Di luar rentang: `applicable=False, reason="age_out_of_range"`. Jangan diekstrapolasi.
- Test fixture: cocokkan output dengan implementasi referensi `ascvd_10y_frs_simple` di paket R `CVrisk` untuk minimal 6 kasus (3 pria, 3 wanita).
- Catatan di laporan: skor dikembangkan pada kohort AS. Kalibrasi untuk populasi Indonesia belum divalidasi.

### 8.3 ML risiko diabetes (pengganti Random Forest lama)

- **Data:** CDC Diabetes Health Indicators (UCI id 891, BRFSS 2015, 253.680 baris). Ambil lewat `ucimlrepo.fetch_ucirepo(id=891)`. Target: `Diabetes_binary` (0 = tidak, 1 = prediabetes/diabetes).
- **Fitur yang dipakai** (hanya yang bisa dikumpulkan dari user): `HighBP`, `HighChol`, `BMI`, `Smoker`, `PhysActivity`, `Fruits`, `Veggies`, `HvyAlcoholConsump`, `GenHlth`, `DiffWalk`, `Sex`, `Age` (kategori 13 level).
- **Mapping dari data user** di `app/risk/features.py`:
  - `HighBP`: profil "pernah didiagnosis hipertensi" ATAU rata-rata sistolik 30 hari ≥130 / diastolik ≥80.
  - `HighChol`: profil "pernah didiagnosis kolesterol tinggi" ATAU kolesterol terakhir ≥240.
  - `PhysActivity`: profil "olahraga di luar pekerjaan 30 hari terakhir" (ya/tidak).
  - `Fruits`, `Veggies`, `HvyAlcoholConsump`, `GenHlth`, `DiffWalk`, `Smoker`: pertanyaan onboarding, dengan definisi persis seperti codebook BRFSS.
  - `Age`: usia → kategori `_AGEG5YR`.
- **Model:** XGBoost atau LightGBM, `scale_pos_weight` untuk imbalance, split stratified 80/20 + 5-fold CV. Kalibrasi probabilitas dengan isotonic (`CalibratedClassifierCV`), karena probabilitas ditampilkan ke user.
- **Metrik yang dilaporkan:** ROC-AUC, PR-AUC, recall dan precision pada threshold yang dipilih, Brier score, calibration plot. Jangan menulis angka target di laporan sebelum training selesai.
- **Explainability:** SHAP `TreeExplainer`, kembalikan top-3 faktor beserta arahnya.
- **Artefak:** `models/diabetes_xgb_v1.joblib` + `models/diabetes_xgb_v1.json` (fitur, versi, metrik, tanggal). Script: `ml/train_diabetes.py`, `ml/evaluate.py`.
- **Batas yang wajib ditulis di UI dan laporan:** data survei self-report dari AS, fitur biner, prediksi berupa indikasi untuk skrining dini, bukan diagnosis.

## 9. Data model (PostgreSQL + pgvector)

Data dipisah menjadi profil statis, log harian, dan pengukuran bertanggal, supaya user tidak diminta data lab setiap hari. Implementasi dengan SQLAlchemy 2.0 + Alembic. Tabel checkpoint LangGraph dibuat oleh `AsyncPostgresSaver.setup()`, jangan dibuat manual.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
  id SERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','clinician','admin')),
  telegram_chat_id BIGINT UNIQUE,
  reminder_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE profiles (               -- statis, diisi saat onboarding
  user_id INT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  birth_date DATE NOT NULL,
  sex TEXT NOT NULL CHECK (sex IN ('male','female')),
  height_cm NUMERIC(5,1) NOT NULL,
  family_history_cvd BOOLEAN, family_history_diabetes BOOLEAN,
  dx_hypertension BOOLEAN, dx_high_chol BOOLEAN, dx_diabetes BOOLEAN,
  bp_treated BOOLEAN,
  smoker_lifetime_100 BOOLEAN,          -- definisi BRFSS
  phys_activity_30d BOOLEAN, fruits_daily BOOLEAN, veggies_daily BOOLEAN,
  heavy_alcohol BOOLEAN, gen_health SMALLINT CHECK (gen_health BETWEEN 1 AND 5),
  diff_walk BOOLEAN,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE daily_logs (             -- satu baris per user per tanggal (upsert)
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL,
  steps INT, sleep_hours NUMERIC(3,1), water_l NUMERIC(3,1),
  calories_kcal INT,                    -- jumlah dari food_entries terkonfirmasi atau input manual
  smoked BOOLEAN, alcohol BOOLEAN,
  source TEXT NOT NULL CHECK (source IN ('web','telegram','form')),
  raw_text TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, log_date)
);

CREATE TABLE measurements (           -- diisi saat memang diukur
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  measured_at TIMESTAMPTZ NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('weight_kg','systolic','diastolic','resting_hr','cholesterol_total')),
  value NUMERIC(6,1) NOT NULL
);

CREATE TABLE food_entries (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL,
  items JSONB NOT NULL,                 -- [{name, portion, kcal_low, kcal_high}]
  kcal_estimate INT NOT NULL,
  confirmed BOOLEAN NOT NULL DEFAULT FALSE,
  image_path TEXT
);

CREATE TABLE assessments (             -- snapshot output risk layer per run
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  thread_id TEXT NOT NULL,
  flags JSONB NOT NULL, framingham JSONB NOT NULL, diabetes JSONB NOT NULL, trends JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE plans (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  assessment_id INT REFERENCES assessments(id),
  status TEXT NOT NULL CHECK (status IN ('pending_review','active','superseded','rejected')),
  content JSONB NOT NULL,               -- {weeks:[{range,targets:[{metric,target}],actions:[{text,citations:[source_id]}]}]}
  starts_on DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE red_flag_events (
  id SERIAL PRIMARY KEY,
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  code TEXT NOT NULL, detail JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE clinician_reviews (
  id SERIAL PRIMARY KEY,
  plan_id INT NOT NULL REFERENCES plans(id),
  thread_id TEXT NOT NULL,
  reviewer_id INT REFERENCES users(id),
  decision TEXT CHECK (decision IN ('approve','edit','reject')),
  edited_content JSONB, note TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), decided_at TIMESTAMPTZ
);

CREATE TABLE telegram_link_tokens (
  token TEXT PRIMARY KEY,               -- secrets.token_urlsafe(16)
  user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,      -- 15 menit
  used_at TIMESTAMPTZ
);

CREATE TABLE kb_documents (
  source_id TEXT PRIMARY KEY,           -- mis. 'WHO-PA-2020'
  title TEXT NOT NULL, url TEXT NOT NULL, publisher TEXT NOT NULL,
  year INT, lang TEXT NOT NULL, sha256 TEXT NOT NULL
);

CREATE TABLE kb_chunks (
  id SERIAL PRIMARY KEY,
  source_id TEXT NOT NULL REFERENCES kb_documents(source_id) ON DELETE CASCADE,
  ord INT NOT NULL, text TEXT NOT NULL,
  embedding VECTOR(:EMBED_DIM) NOT NULL, -- dimensi dari settings, ikut model embedding
  tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED
);
CREATE INDEX ON kb_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON kb_chunks USING gin (tsv);

CREATE TABLE agent_runs (             -- untuk evaluasi latensi & audit
  id SERIAL PRIMARY KEY,
  thread_id TEXT NOT NULL, user_id INT, channel TEXT, intent TEXT,
  node_timings JSONB, llm_calls INT, total_ms INT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

`thread_id` LangGraph = `user-{user_id}` untuk percakapan, `report-{user_id}-{iso_week}` untuk weekly report.

## 10. API backend & halaman frontend

Backend FastAPI memakai prefix `/api`. Auth berupa JWT di cookie httpOnly. Endpoint chat mengalirkan event graph lewat SSE.

| Method | Path | Fungsi | Role |
| --- | --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | Auth | publik |
| GET/PUT | `/api/profile` | Baca/ubah profil statis | user |
| GET | `/api/logs?from&to` | Daftar daily log | user |
| POST | `/api/measurements` | Tambah pengukuran manual | user |
| POST | `/api/chat` | Body `{message, image_b64?}`. Respons SSE: `node_start`, `token`, `interrupt`, `chart`, `final`, `error` | user |
| POST | `/api/chat/resume` | Body `{value}`. Melanjutkan `interrupt` (klarifikasi/konfirmasi). Respons SSE | user |
| GET | `/api/dashboard?days=7\|30` | `TrendReport` + `ChartPayload` + assessment terakhir + plan aktif | user |
| GET | `/api/plans/active` | Plan aktif | user |
| POST | `/api/telegram/link-token` | Buat token + deep link `https://t.me/<bot>?start=<token>` | user |
| GET | `/api/clinician/queue` | Daftar review pending | clinician |
| POST | `/api/clinician/reviews/{id}` | Body `{decision, edited_content?, note?}`, lalu resume thread terkait | clinician |
| POST | `/api/admin/ingest` | Jalankan ingestion korpus | admin |
| GET | `/api/health` | Status DB + Ollama + model ter-load | publik |

**Halaman frontend (Next.js App Router, shadcn/ui, Recharts)**

- `/login`, `/register`
- `/onboarding`: wizard profil statis (bagian 9 `profiles`), dengan teks penjelasan untuk tiap pertanyaan BRFSS.
- `/chat`: chat streaming. Tampilkan node yang sedang berjalan ("Menganalisis risiko…"). Kartu konfirmasi untuk `interrupt`. Upload foto. Sitasi dirender sebagai chip yang bisa diklik ke URL sumber.
- `/dashboard`: kartu skor (flags, Framingham, diabetes + SHAP top-3), line chart 7/30 hari per metrik, plan aktif + kepatuhan, riwayat red flag.
- `/settings`: edit profil, tombol "Hubungkan Telegram" (QR + link), toggle reminder, hapus akun dan semua data.
- `/clinician`: antrian review, detail kasus (data, assessment, draf plan), tombol approve / edit / reject.

Disclaimer tetap terlihat di footer `/chat` dan `/dashboard`: hasil bukan diagnosis medis.

## 11. Channel Telegram

Telegram adalah channel kedua untuk reminder, input cepat (teks/foto), dan notifikasi. Bot memanggil graph yang sama dengan web, memakai `thread_id` yang sama, sehingga histori, plan, dan interrupt ikut sama.

- **Library:** `python-telegram-bot[job-queue]` (API v21+, pin versi saat install). Bot berjalan sebagai proses terpisah `app/channels/telegram_bot.py`.
- **Long polling, bukan webhook.** Backend berjalan di laptop tanpa URL HTTPS publik.
- **Account linking:** user klik "Hubungkan Telegram" di web, backend membuat token sekali pakai (berlaku 15 menit), user membuka `t.me/<bot>?start=<token>`, handler `/start` memvalidasi token lalu menyimpan `telegram_chat_id`. Chat dari `chat_id` yang belum terhubung hanya dijawab dengan instruksi linking.
- **Pesan masuk:** teks dan/atau foto masuk ke graph dengan `channel="telegram"`. Kalau `aget_state(config).interrupts` tidak kosong, pesan dipakai sebagai `Command(resume=...)`.
- **Saat graph berjalan:** kirim `send_chat_action("typing")` tiap 4 detik, ditambah pesan progres singkat saat masuk node Risk Analyst dan Coach.
- **Format keluar:** plain text atau HTML terbatas (`<b>`, `<i>`) dengan `parse_mode="HTML"`. Jangan pakai `parse_mode="Markdown"`. Pesan dipecah per 4.000 karakter. Rekomendasi lengkap dan angka detail ditampilkan di web; Telegram menerima ringkasan + link `/dashboard`.
- **Jobs (`job_queue`, zona waktu Asia/Jakarta):**
  - `daily_reminder` 17.00 setiap hari: hanya untuk user dengan `reminder_enabled` dan belum punya `daily_logs` hari itu.
  - `weekly_report` Minggu 19.00: jalankan subgraph weekly report, kirim teks + PNG `render_chart_png`.
  - `clinician_notify`: saat ada review baru, kirim notifikasi + link `/clinician` ke user ber-role clinician yang sudah terhubung.
- **Command:** `/start <token>`, `/log` (template contoh kalimat), `/ringkasan` (trend 7 hari), `/stop` (matikan reminder), `/hapus` (link ke halaman hapus data di web).

## 12. Korpus RAG & ingestion

Korpus awal memakai sumber WHO yang sudah dirujuk di laporan versi lama, ditambah pedoman Indonesia yang dicari anggota C. Hanya dokumen di korpus yang boleh disitasi.

| source\_id | Dokumen | URL |
| --- | --- | --- |
| WHO-PA-2020 | WHO guidelines on physical activity and sedentary behaviour (2020) | https://www.who.int/publications/i/item/9789240015128 |
| WHO-FS-PA | Fact sheet: Physical activity | https://www.who.int/news-room/fact-sheets/detail/physical-activity |
| WHO-FS-DIET | Fact sheet: Healthy diet | https://www.who.int/news-room/fact-sheets/detail/healthy-diet |
| WHO-FS-OBES | Fact sheet: Obesity and overweight | https://www.who.int/news-room/fact-sheets/detail/obesity-and-overweight |
| WHO-FS-DM | Fact sheet: Diabetes | https://www.who.int/news-room/fact-sheets/detail/diabetes |
| WHO-FS-CVD | Fact sheet: Cardiovascular diseases | https://www.who.int/news-room/fact-sheets/detail/cardiovascular-diseases-(cvds) |
| WHO-FS-TOB | Fact sheet: Tobacco | https://www.who.int/news-room/fact-sheets/detail/tobacco |
| WHO-FS-NCD | Fact sheet: Noncommunicable diseases | https://www.who.int/news-room/fact-sheets/detail/noncommunicable-diseases |
| KEMENKES-PGS-2014 | Permenkes No. 41 Tahun 2014 tentang Pedoman Gizi Seimbang | https://peraturan.bpk.go.id/Download/109856/Permenkes%20Nomor%2041%20Tahun%202014.pdf |
| KEMENKES-PNPK-HT-2026 | PNPK Tata Laksana Hipertensi Dewasa (KMK HK.01.07/MENKES/303/2026) | https://keslan.kemkes.go.id/unduhan/fileunduhan1780387327\_362636.pdf |
| KEMENKES-PNPK-DM2-2026 | PNPK Tatalaksana Diabetes Melitus Tipe 2 Dewasa (KMK HK.01.07/MENKES/302/2026) | https://keslan.kemkes.go.id/unduhan/fileunduhan1777518085\_672976.pdf |
| KEMENKES-PTM-2015 | Permenkes No. 71 Tahun 2015 tentang Penanggulangan Penyakit Tidak Menular | https://peraturan.go.id/files/bn1775-2015.pdf |
| KEMENKES-PTM-MGMT-2019 | Buku Pedoman Manajemen Penyakit Tidak Menular, Dit. P2PTM (2019). Salinan di situs Puskesmas, belum ditemukan di situs Kemenkes | https://pkm-senaken.paserkab.go.id/po-content/uploads/buku\_pedoman\_manajemen\_ptm\_compressed.pdf |

Catatan korpus Kemenkes: kedua PNPK 2026 menggantikan versi sebelumnya (hipertensi 2021, DM tipe 2 2020). PNPK adalah pedoman klinis untuk dokter dan memuat terapi obat. Di korpus, pakai hanya bagian definisi, klasifikasi, skrining, dan modifikasi gaya hidup. Bagian farmakoterapi tidak di-ingest, supaya tidak pernah muncul di rekomendasi.

**Pipeline** (`app/rag/ingest.py`, idempoten berdasarkan `sha256`):

1. Simpan file mentah (PDF/HTML) di `data/corpus/<source_id>.*` + `data/corpus/manifest.yaml` (source\_id, title, url, publisher, year, lang). Unduh manual. Script tidak scraping.
2. Ekstrak teks (`pypdf` / `trafilatura`), bersihkan header/footer.
3. Chunk sekitar 600 token dengan overlap 100, menghormati batas heading.
4. Embed lewat Ollama (`/api/embed`) dengan model embedding multilingual. Kandidat: `bge-m3` atau keluarga `qwen3-embedding`. Cek ketersediaan tag dan dimensinya di library Ollama, lalu set `EMBED_MODEL` dan `EMBED_DIM`.
5. Upsert `kb_documents` dan `kb_chunks`.

**Retrieval** (`retrieve_guidelines`): hybrid. Ambil top-20 cosine (pgvector) + top-20 full-text (`tsv`), gabungkan dengan Reciprocal Rank Fusion, kembalikan top-k=5. Query dibuat oleh Knowledge agent dari flags + pertanyaan user, dalam bahasa Indonesia dan Inggris (korpus WHO berbahasa Inggris).

**Aturan sitasi:** setiap butir rekomendasi memuat `citations: [source_id]` yang ada di hasil retrieval run tersebut. Safety Critic menolak butir yang tanpa sitasi atau yang sitasinya tidak ada di hasil retrieval.

## 13. Safety, privasi, red flags

Red flag dideteksi oleh aturan deterministik sebelum dan sesudah LLM. LLM tidak bisa menghapus, melunakkan, atau menunda pesan rujukan.

**Red flag rules** (`red_flag_rules`, draft ambang. Verifikasi bersama ambang di bagian 8.1):

| Kode | Pemicu | Aksi |
| --- | --- | --- |
| RF-BP-CRISIS | Sistolik ≥180 atau diastolik ≥120 pada pengukuran ≤24 jam terakhir | Pesan rujukan segera di awal respons + `interrupt` clinician review |
| RF-SYMPTOM | Keyword gejala di teks user: nyeri dada, sesak napas berat, pingsan, lemah/mati rasa satu sisi tubuh, bicara pelo | Respons hanya pesan darurat: hubungi 119 / ke IGD terdekat. Graph berhenti, tidak ada plan |
| RF-HR | Resting HR >120 atau <40 yang dilaporkan saat istirahat | Pesan untuk periksa ke fasilitas kesehatan |
| RF-SELFHARM | Indikasi menyakiti diri di teks user | Respons empatik + layanan dukungan krisis yang berlaku di Indonesia (diverifikasi tim). Graph berhenti |

- Teks pesan rujukan adalah template tetap di `app/safety/templates.py`, bukan hasil generate LLM.
- Keyword gejala diuji dengan variasi ejaan dan bahasa informal (mis. "dada sakit banget").

**Safety Critic (LLM + cek deterministik)** memeriksa draf Coach terhadap:

1. Setiap angka di draf cocok dengan data/assessment (dicek oleh kode, bukan LLM).
2. Setiap butir punya sitasi yang valid (dicek oleh kode).
3. Tidak ada diagnosis ("Anda menderita…"), nama obat, atau dosis (LLM, dengan rubric).
4. Risiko tidak dibesar-besarkan atau diremehkan dibanding output risk layer (LLM, dengan rubric).
5. Disclaimer ada (kode).

Gagal di cek 1, 2, atau 5 memicu revisi otomatis tanpa LLM critic. Maksimal 2 putaran revisi. Kalau tetap gagal, kirim versi minimal yang aman: flags + template saran umum + sitasi.

**Privasi**

- LLM, embedding, DB, dan file foto tersimpan lokal. Satu-satunya pihak ketiga adalah Telegram (chat bot tidak end-to-end encrypted), jadi via Telegram hanya dikirim reminder, ringkasan, dan link.
- Persetujuan eksplisit saat onboarding: data apa yang disimpan, untuk apa, dan bahwa hasil bukan diagnosis.
- Hapus akun = hapus semua baris user + file foto + checkpoint thread-nya.
- Foto makanan disimpan di `data/uploads/` dengan nama acak. Tidak disajikan publik tanpa auth.
- Tracing (Phoenix) berjalan lokal. Jangan mengirim trace ke layanan cloud.

## 14. Non-functional requirements & konfigurasi

Target mesin adalah MacBook Pro M5 16 GB. Dari 16 GB itu, kira-kira 12 GB bisa dipakai GPU, dan masih harus berbagi dengan Postgres, Next.js, dan browser. Semua keputusan di bawah mengikuti batas ini.

- **Satu model LLM untuk semua agent**, termasuk vision: `qwen3.5:9b` (tag Ollama ±6,6 GB). Tidak ada model kedua yang di-load bersamaan, kecuali model embedding kecil.
- **Ollama dijalankan native**, bukan di Docker (Docker di macOS tidak bisa memakai GPU Metal). Docker hanya untuk Postgres dan Phoenix.
- `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=2` (LLM + embedding), `OLLAMA_KEEP_ALIVE=30m` supaya model tidak di-unload di tengah demo.
- **Context window:** `num_ctx=8192` per call. Prompt tiap node dibuat ringkas: data dikirim sebagai JSON terkompres, bukan seluruh histori chat. Pesan lama diringkas oleh node `summarize_history` jika lebih dari 12 pesan.
- **Thinking mode:** dimatikan untuk Supervisor, Intake, Nutrition, dan Response. Dinyalakan untuk Risk Analyst (interpretasi), Coach, dan Safety Critic. Gunakan parameter `ChatOllama` yang sesuai (`reasoning=`). Verifikasi nama parameternya di versi `langchain-ollama` yang terpasang.
- **Structured output:** semua node selain Response memakai `with_structured_output(PydanticModel)`. Jika parsing gagal: retry 1 kali dengan pesan error, lalu fallback deterministik per node.
- **Timeout per node** 90 detik. Total check-in dibatasi 4 menit; lewat dari itu, kirim hasil parsial (flags + data).
- **Observability:** setiap run mencatat ke `agent_runs` (timing per node, jumlah LLM call). Tracing opsional ke Arize Phoenix lokal.

**`.env.example`**

```bash
DATABASE_URL=postgresql+psycopg://sehat:sehat@localhost:5432/sehat
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=qwen3.5:9b
EMBED_MODEL=            # isi setelah dipilih (bagian 12)
EMBED_DIM=              # sesuai model embedding
LLM_NUM_CTX=8192
JWT_SECRET=change-me
TELEGRAM_BOT_TOKEN=
TELEGRAM_BOT_USERNAME=
APP_BASE_URL=http://localhost:3000
TZ=Asia/Jakarta
PHOENIX_ENABLED=false
```

**Struktur repo**

```text
sehatagent/
├─ backend/
│  ├─ app/
│  │  ├─ api/            # FastAPI routers
│  │  ├─ graph/          # state.py, nodes/, prompts/, build.py
│  │  ├─ tools/          # bagian 7
│  │  ├─ risk/           # guidelines.py, framingham.py, features.py
│  │  ├─ rag/            # ingest.py, retrieve.py
│  │  ├─ safety/         # rules.py, templates.py
│  │  ├─ channels/       # telegram_bot.py
│  │  ├─ db/             # models.py, session.py
│  │  └─ settings.py
│  ├─ ml/                # train_diabetes.py, evaluate.py
│  ├─ models/            # artefak model (gitignored kecuali .json metadata)
│  ├─ alembic/
│  └─ tests/
├─ frontend/             # Next.js
├─ data/corpus/          # dokumen RAG + manifest.yaml
├─ eval/                 # test set + runner (bagian 15)
├─ docker-compose.yml    # postgres+pgvector, phoenix
└─ Makefile              # dev, test, ingest, train, eval, bot
```

## 15. Evaluasi & testing

Evaluasi membandingkan sistem baru dengan baseline n8n pada metrik di bagian 2. Semua test set disimpan di `eval/` dan dijalankan dengan `make eval`, yang menghasilkan `eval/report.md`.

**Unit & integration test (pytest)**

- Setiap tool di bagian 7: kasus normal, batas ambang, input kosong.
- Framingham: 6 fixture vs `CVrisk`, ditambah kasus usia 25 dan 80 (harus `applicable=False`).
- `red_flag_rules`: 15 kasus positif + 15 negatif, termasuk ejaan informal.
- Graph: test routing Supervisor dengan LLM di-mock (`FakeListChatModel`), test resume `interrupt`, test bahwa jalur RF-SYMPTOM tidak pernah sampai ke Coach.

**Evaluasi dengan LLM asli** (`eval/run.py`)

| Set | Isi | Metrik |
| --- | --- | --- |
| `intake_30.jsonl` | 30 kalimat log harian (formal + informal + campur Inggris) dengan label field | Akurasi per field, exact match per kalimat |
| `routing_40.jsonl` | 40 pesan dengan label intent | Akurasi intent, confusion matrix |
| `personas_10.json` | 10 profil + histori 14 hari (sehat, overweight, hipertensi st.1, perokok, usia <30, usia >40, dll.) | Coverage sitasi, groundedness angka, lolos Safety Critic, latensi p50/p95 |
| `redflag_15.json` | 15 kasus berisiko tinggi | Recall red flag (harus 100%) |
| `meals_15/` | 15 foto makanan Indonesia + perkiraan kalori referensi | MAE kalori, % di dalam rentang estimasi |

**Review manusia:** 5 dari 10 persona dinilai oleh tenaga medis (kalau tersedia, seperti di versi lama) dengan rubric 1–5: relevansi klinis, keamanan, actionability. Sertakan baseline n8n untuk persona yang sama bila memungkinkan.

**Ablation untuk laporan:** (a) tanpa Safety Critic, (b) tanpa RAG, (c) thinking selalu on vs selektif. Laporkan dampaknya ke coverage sitasi, groundedness, dan latensi.

## 16. Rencana 7 hari & pembagian tim

&#91;embedded content: rencana 7 hari · 4 fase, 3 gate\]

Kontrak hari pertama (`app/graph/state.py`, Pydantic I/O semua tool di `app/schemas/`, migrasi Alembic awal) di-merge ke `main` dan dibekukan. Setelah itu tiap track bisa jalan paralel dengan mock. Perubahan kontrak setelah Gate 1 harus disetujui A dan pemilik track yang terdampak.

| Track | Anggota | Tanggung jawab | Milestone | Bukti di Gate 2 |
| --- | --- | --- | --- | --- |
| Orkestrasi | A (Atthar) | Graph, semua node agent + prompt, FastAPI + SSE, integrasi | M0, M4 | Graph jalan dengan `qwen3.5:9b`, tools masih di-mock |
| Risk & Telegram | B | `guideline_flags`, `framingham_nonlab`, training + inference ML diabetes + SHAP. Lalu bot Telegram + jobs | M2, M6 | Tool risiko + test lulus. Model + metadata tersimpan |
| Knowledge & safety | C | Korpus + ingestion, `retrieve_guidelines`, `red_flag_rules` + template, verifikasi ambang, test set evaluasi | M3, M7 (eval) | Korpus ter-ingest, retrieval menghasilkan passage relevan, 30 kasus red flag lulus |
| Frontend | D | Semua halaman bagian 10, client SSE, kartu `interrupt`, dashboard Recharts | M5 | Halaman jalan terhadap mock API |

**Cara kerja dengan Claude Code:** setiap anggota memberi PRD ini + nomor milestone track-nya, satu branch per track, PR ke `main` dengan `make test` hijau. Anggota yang tidak menjalankan LLM bisa memakai `FakeListChatModel` dan tidak perlu memasang Ollama.

## 17. Open questions & verifikasi

Item berikut belum terkunci. Claude Code tidak boleh mengisinya dengan asumsi diam-diam. Pakai placeholder + `NEEDS_VERIFICATION`, lalu lapor.

**Keputusan tim**

- [ ] Klasifikasi tekanan darah: ACC/AHA 2017, ISH 2020, atau PERHI?
- [ ] Cut-off BMI: Asia-Pasifik (WHO) atau Kemenkes?
- [ ] Nama produk final ("SehatAgent" hanya nama kerja).
- [ ] Apakah ada tenaga medis yang bersedia menjadi clinician reviewer dan penilai evaluasi?
- [ ] Dokumen pedoman Kemenkes mana yang masuk korpus?

**Perlu verifikasi teknis**

- [ ] Model embedding Ollama yang dipakai + dimensinya (`EMBED_MODEL`, `EMBED_DIM`).
- [ ] Nama parameter untuk mematikan thinking di `ChatOllama` pada versi `langchain-ollama` terpasang.
- [ ] Kualitas vision `qwen3.5:9b` untuk makanan Indonesia. Uji 15 foto sebelum F-10 dianggap layak demo.
- [ ] Reliabilitas tool-calling `qwen3.5:9b` di History Q&A. Kalau error rate tinggi, ganti ke routing structured output + pemanggilan tool deterministik.
- [ ] Footprint memori aktual (`ollama ps` + Activity Monitor) saat semua service jalan bersamaan.
- [ ] Semua ambang di bagian 8.1 dan 13 dicocokkan ke dokumen sumber.
- [ ] Layanan dukungan krisis kesehatan jiwa yang berlaku di Indonesia untuk template RF-SELFHARM.
- [ ] Koefisien Framingham 2008 non-lab dari paper asli, dicocokkan dengan paket `CVrisk`.

**Sumber yang dirujuk PRD ini**

- Laporan Tugas Akhir AI Kelompok 2 Kesehatan + `n8n Workflow.json` (Google Drive kelompok).
- [D'Agostino et al. 2008, General cardiovascular risk profile for use in primary care](https://scholars.uthscsa.edu/en/publications/general-cardiovascular-risk-profile-for-use-in-primary-care-the-f/)
- [CVrisk: ascvd\_10y\_frs\_simple](https://rdrr.io/cran/CVrisk/src/R/ascvd_10y_frs_simple.R)
- [UCI: CDC Diabetes Health Indicators](https://archive.ics.uci.edu/dataset/891/cdc%2Bdiabetes%2Bhealth%2Bindicators)
- [Ollama: MLX engine di Apple Silicon](https://registry.ollama.ai/blog/mlx)
- [Qwen3.5 9B vs 2.5: tag Ollama, ukuran, modality](https://toolhalla.ai/blog/qwen-3-5-vs-qwen-2-5-local-llm-comparison-2026)
- [Best local LLM for a 16GB MacBook Pro (budget memori)](https://openclawdc.com/blog/best-local-llm-macbook-pro-16gb/)
- [LangGraph releases](https://releases.sh/langchain/langgraph-releases.md)
