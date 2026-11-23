"""Prompt sistem per node. Data dikirim terpisah sebagai JSON ringkas."""

from app.risk import guidelines as g

SUPERVISOR = """Klasifikasikan pesan user ke satu intent:
- log: user melaporkan aktivitas/gaya hidup hari ini (langkah, tidur, air, rokok, alkohol, makan,
  tekanan darah, berat badan, dll.)
- history_question: user bertanya tentang data/histori/tren miliknya sendiri
- health_info: user bertanya info kesehatan umum
- smalltalk: sapaan, terima kasih, atau hal lain
Jawab hanya dengan field intent."""

INTAKE = """Ekstrak data harian dari teks user (bahasa Indonesia, informal, atau campur Inggris).
- steps: jumlah langkah (contoh "6rb" = 6000)
- sleep_hours: jam tidur semalam
- water_l: liter air minum (1 gelas kira-kira 0.25 liter)
- calories_kcal: kalori jika disebut eksplisit
- smoked / alcohol: true/false hanya jika user menyebutnya
- measurements: hanya pengukuran yang angkanya tertulis di `teks` (systolic, diastolic,
  resting_hr, weight_kg, cholesterol_total). Tekanan darah "sistolik/diastolik" = dua item.
  Kosongkan list jika tidak ada.
Isi null untuk yang tidak disebut. Jangan menebak. `sudah_terisi` adalah data sebelumnya,
jangan diulang ke measurements."""

RISK_ANALYST = """Tulis ringkasan hasil penilaian kesehatan 2-4 kalimat (maksimal 80 kata)
dari JSON. Jelaskan apa artinya bagi user dan satu hal terpenting yang bisa dilakukan. Pakai
`label` dan `keterangan` apa adanya. Jangan menghitung ulang, jangan menambah angka di luar JSON,
jangan mendiagnosis. Kalau perkiraan risiko jantung belum bisa dihitung, cukup sebut belum bisa
dihitung dan alasannya. Setiap `label` sudah final menurut pedoman yang dipakai aplikasi (BMI
memakai batas orang Asia): jangan menilai ulang dengan pengetahuan umum. Hal yang ada di
`hal_yang_perlu_diperhatikan` tidak boleh disebut ideal, normal, sehat, atau aman."""

KNOWLEDGE = """Buat 2-3 query pencarian pedoman kesehatan dari flags risiko dan pesan user.
Campur bahasa Indonesia dan Inggris (korpus WHO berbahasa Inggris). Query singkat dan spesifik."""

COACH = """Anda coach gaya hidup. Buat rencana bertahap 4 minggu (4 elemen `weeks`).
Aturan:
- Setiap aksi wajib punya `citations`: list nilai dari `source_id_valid` (mis. "WHO-PA-2020"),
  bukan teks "source_id". Jangan memakai sumber lain.
- Rencana menyebut faktor risiko dari data user (flags, tren).
- Angka di teks aksi hanya boleh berasal dari data user, assessment, target, atau passages.
- `targets.metric` salah satu: steps, sleep_hours, water_l, calories, smoked, alcohol, systolic,
  diastolic, resting_hr, weight_kg, cholesterol.
- Tanpa diagnosis, tanpa nama obat, tanpa dosis.
- Kalau ada `previous_plan`, lanjutkan dan sesuaikan dengan kepatuhan (adherence_pct).
- Kalau ada `critique`, perbaiki semua issue yang disebut.
- Teks aksi: satu kalimat konkret yang mudah dilakukan, bahasa awam tanpa istilah teknis atau
  nama metrik (tulis "tidur", bukan "sleep_hours")."""

CRITIC = """Periksa rencana gaya hidup terhadap dua aturan. Nilai hanya pelanggaran yang jelas.
1. no_diagnosis_or_medication: false HANYA jika teks menyatakan diagnosis ("Anda menderita
   hipertensi", "Anda terkena diabetes"), menyebut nama obat, atau dosis obat. Menyebut faktor
   risiko dari assessment (mis. "tekanan darah tahap 1", "BMI tinggi") BUKAN diagnosis.
2. risk_calibrated: false HANYA jika teks menyebut risiko jauh lebih tinggi/rendah dari
   assessment (mis. "risiko Anda sangat tinggi" padahal band moderate) atau menjanjikan hasil
   pasti ("pasti sembuh", "menghilangkan risiko"). Kalimat umum seperti "membantu menurunkan
   risiko" BUKAN pelanggaran.
Jika tidak ada pelanggaran: kedua field true dan issues kosong. Jika ada, issues berisi kutipan
teks yang melanggar dan aturan mana."""

HISTORY_QA = """Jawab pertanyaan user tentang histori kesehatannya dalam bahasa Indonesia.
Gunakan tool untuk mengambil data; maksimal 4 panggilan tool. Semua angka di jawaban harus
berasal dari hasil tool. Kalau data tidak cukup, katakan terus terang. Jangan mendiagnosis."""

KNOWLEDGE_INFO = """Jawab pertanyaan kesehatan umum hanya dari `passages`, bahasa Indonesia,
ringkas. `citations` berisi source_id passage yang dipakai. Jika passages tidak menjawab
pertanyaan, set found=false. Jangan mendiagnosis atau menyebut obat/dosis."""

SMALLTALK = """Anda SehatAgent, asisten gaya hidup sehat. Balas singkat dan ramah dalam bahasa
Indonesia. Kalau relevan, ajak user mencatat aktivitas hari ini (langkah, tidur, air minum,
rokok, alkohol) atau bertanya tentang tren kesehatannya. Jangan memberi diagnosis."""

CLARIFY_FALLBACK = (
    "Maaf, saya belum menangkap maksudnya. Anda bisa mencatat aktivitas "
    '(contoh: "jalan 6rb langkah, tidur 6 jam, minum 2 liter, tidak merokok, tidak minum '
    'alkohol") atau bertanya tentang tren kesehatan Anda.'
)

INTAKE_FALLBACK = (
    "Maaf, saya belum bisa membaca catatannya. Coba tulis dengan format: "
    '"langkah 6000, tidur 6 jam, air 2 liter, merokok tidak, alkohol tidak".'
)

MEAL_FALLBACK = "Maaf, foto belum bisa dianalisis. Silakan ketik makanan dan porsinya."

PROFILE_MISSING = "Data harian tersimpan. Lengkapi profil di /onboarding agar risiko bisa dinilai."

WEIGHT_MISSING = (
    'Data harian tersimpan. Catat berat badan Anda (contoh: "berat 65 kg") agar risiko bisa '
    "dinilai, karena BMI dibutuhkan skor jantung dan model diabetes."
)

NOT_IN_CORPUS = (
    "Maaf, informasi itu tidak ada di korpus pedoman yang saya miliki, jadi saya tidak bisa "
    "menjawabnya dengan sumber yang jelas."
)

FIELD_LABELS = {
    "steps": "jumlah langkah",
    "sleep_hours": "jam tidur",
    "water_l": "air minum (liter)",
    "smoked": "merokok atau tidak",
    "alcohol": "minum alkohol atau tidak",
}


def clarify_question(missing: list[str]) -> str:
    return "Boleh dilengkapi: " + ", ".join(FIELD_LABELS[f] for f in missing) + "?"


# --- Teks awam untuk hasil penilaian (tanpa kode, istilah model, atau bahasa Inggris) -----


def num(v: float | int | str | None) -> str:
    """Format angka Indonesia: 8500 -> "8.500", 6.5 -> "6,5"."""
    if v is None or isinstance(v, str):
        return str(v)
    if float(v).is_integer():
        return f"{int(v):,}".replace(",", ".")
    return f"{v:.1f}".replace(".", ",")


def _smoked_days(value: object) -> str:
    days = str(value).split()[0]
    return f"merokok {days} dari 7 hari terakhir"


def _bmi(v: object, rule: str) -> str:
    return f"BMI {num(v)} (perbandingan berat dan tinggi badan); {rule}"  # type: ignore[arg-type]


def _bp(v: object) -> str:
    return f"tensi {v} mmHg; normal di bawah {g.BP_ELEVATED_SYS}/{g.BP_STAGE1_DIA}"


# Teks flag menyertakan batas dari app/risk/guidelines.py supaya user (dan LLM) tahu alasannya.
FLAG_TEXT = {
    "BP_CRISIS": (
        "Tekanan darah sangat tinggi",
        lambda v: (
            f"tensi {v} mmHg; {g.BP_CRISIS_SYS}/{g.BP_CRISIS_DIA} ke atas perlu segera diperiksa"
        ),
    ),
    "BP_STAGE2": ("Tekanan darah tinggi", _bp),
    "BP_STAGE1": ("Tekanan darah sedikit tinggi", _bp),
    "BP_ELEVATED": ("Tekanan darah di atas normal", _bp),
    "BMI_OBESE": (
        "Berat badan masuk kategori obesitas",
        lambda v: _bmi(v, f"untuk orang Asia, {num(g.BMI_OBESE)} ke atas termasuk obesitas"),
    ),
    "BMI_OVERWEIGHT": (
        "Berat badan berlebih",
        lambda v: _bmi(v, f"untuk orang Asia, normal sampai {num(g.BMI_OVERWEIGHT - 0.1)}"),
    ),
    "BMI_UNDERWEIGHT": (
        "Berat badan kurang",
        lambda v: _bmi(v, f"normal mulai {num(g.BMI_UNDERWEIGHT)}"),
    ),
    "PA_NONE": ("Belum rutin berolahraga", lambda v: "tidak ada olahraga dalam 30 hari terakhir"),
    "STEPS_LOW": ("Langkah harian masih sedikit", lambda v: f"rata-rata {num(v)} langkah per hari"),
    "SLEEP_SHORT": (
        "Tidur kurang dari 7 jam",
        lambda v: (
            f"rata-rata {num(v)} jam per malam, disarankan minimal {num(g.SLEEP_MIN_HOURS)} jam"
        ),
    ),
    "CHOL_HIGH": (
        "Kolesterol tinggi",
        lambda v: f"{num(v)} mg/dL; normal di bawah {g.CHOL_BORDERLINE}",
    ),
    "CHOL_BORDERLINE": (
        "Kolesterol sedikit tinggi",
        lambda v: f"{num(v)} mg/dL; normal di bawah {g.CHOL_BORDERLINE}",
    ),
    "RHR_HIGH": (
        "Denyut jantung saat istirahat tinggi",
        lambda v: f"{num(v)} kali per menit; normal sampai {g.RESTING_HR_HIGH}",
    ),
    "SMOKING": ("Merokok", _smoked_days),
}


def flag_label(code: str) -> str:
    return FLAG_TEXT.get(code, (code.replace("_", " ").capitalize(), str))[0]


def flag_line(flag: dict) -> str:
    label, detail = FLAG_TEXT.get(flag["code"], (flag_label(flag["code"]), str))
    old = " (data lebih dari 3 bulan lalu)" if flag.get("stale") else ""
    return f"- **{label}**: {detail(flag['value'])}{old}"


# Fitur model diabetes (BRFSS) dalam bahasa awam, sesuai nilai user: fitur biner punya kalimat
# untuk 1 (ya) dan 0 (tidak), supaya "membantu menurunkan" tidak terbaca "kolesterol tinggi".
FEATURE_TEXT: dict[str, tuple[str, str]] = {
    "HighBP": ("riwayat tekanan darah tinggi", "tidak ada riwayat tekanan darah tinggi"),
    "HighChol": ("riwayat kolesterol tinggi", "tidak ada riwayat kolesterol tinggi"),
    "Smoker": ("pernah merokok", "tidak pernah merokok"),
    "PhysActivity": ("rutin berolahraga", "jarang berolahraga"),
    "Fruits": ("makan buah setiap hari", "jarang makan buah"),
    "Veggies": ("makan sayur setiap hari", "jarang makan sayur"),
    "HvyAlcoholConsump": ("minum alkohol berat", "tidak minum alkohol berat"),
    "DiffWalk": ("kesulitan berjalan", "tidak kesulitan berjalan"),
}
FEATURE_PLAIN = {
    "Age": "usia Anda",
    "BMI": "BMI Anda",
    "GenHlth": "penilaian kesehatan Anda",
    "Sex": "jenis kelamin",
}


def feature_text(factor: dict) -> str:
    name = factor["feature"]
    if name in FEATURE_TEXT:
        yes, no = FEATURE_TEXT[name]
        return yes if factor.get("value", 1) else no
    return FEATURE_PLAIN.get(name, name)


BAND_TEXT = {"low": "rendah", "moderate": "sedang", "high": "tinggi"}
CATEGORY_TEXT = {"low": "rendah", "intermediate": "sedang", "high": "tinggi"}


def heart_text(fr: dict, lead: bool = True) -> str:
    """lead=False: tanpa kalimat pembuka, untuk ditaruh di bawah label "Penyakit jantung"."""
    if fr.get("applicable"):
        pct = f"{num(round(fr['risk_10y_pct'], 1))}% ({CATEGORY_TEXT.get(fr.get('category'), '-')})"
        note = (
            "Rumus ini berasal dari penelitian di Amerika Serikat, "
            "jadi anggap sebagai gambaran kasar."
        )
        if lead:
            lead_text = "Perkiraan risiko penyakit jantung dan pembuluh darah dalam 10 tahun"
            return f"{lead_text}: {pct}. {note}"
        return f"{pct.capitalize()} untuk 10 tahun ke depan. {note}"
    reason = {
        "age_out_of_range": "rumusnya hanya untuk usia 30 sampai 74 tahun",
        "missing_weight": "data berat badan belum ada",
        "missing_systolic": "data tekanan darah belum ada",
    }.get(fr.get("reason") or "", "datanya belum cukup")
    if lead:
        return f"Perkiraan risiko penyakit jantung 10 tahun belum bisa dihitung, karena {reason}."
    return f"Belum bisa dihitung, karena {reason}."


def diabetes_text(dm: dict, lead: bool = True) -> str:
    factors = dm.get("top_factors", [])
    raising = [feature_text(f) for f in factors if f["direction"] == "increase"]
    lowering = [feature_text(f) for f in factors if f["direction"] == "decrease"]
    level = f"{BAND_TEXT.get(dm['band'], dm['band'])} (sekitar {num(round(dm['prob'] * 100))}%)."
    parts = [f"Kemungkinan diabetes atau prediabetes: {level}" if lead else level.capitalize()]
    if raising:
        parts.append("Yang paling menaikkan: " + ", ".join(raising) + ".")
    if lowering:
        parts.append("Yang membantu menurunkan: " + ", ".join(lowering) + ".")
    parts.append("Ini perkiraan untuk deteksi dini dari data survei, bukan diagnosis.")
    return " ".join(parts)


TARGET_TEXT = {
    "steps": ("langkah", "per hari"),
    "sleep_hours": ("tidur", "jam per malam"),
    "water_l": ("air minum", "liter per hari"),
    "calories": ("kalori", "kkal per hari"),
    "smoked": ("hari merokok", ""),
    "alcohol": ("hari minum alkohol", ""),
    "systolic": ("tensi sistolik", "mmHg"),
    "diastolic": ("tensi diastolik", "mmHg"),
    "resting_hr": ("denyut istirahat", "kali per menit"),
    "weight_kg": ("berat badan", "kg"),
    "cholesterol": ("kolesterol", "mg/dL"),
}


def target_text(metric: str, target: float) -> str:
    label, unit = TARGET_TEXT.get(metric, (metric, ""))
    return f"{label} {num(target)} {unit}".strip()


PLAIN_LANGUAGE = """Gaya bahasa: bahasa Indonesia sehari-hari yang sopan untuk orang awam (sapa
"Anda"). Kalimat pendek dan jelas. Jangan memakai kode atau istilah teknis seperti nama variabel,
"flag", "bendera", "model", "Framingham", "BRFSS", "probabilitas", "kategori info", atau istilah
bahasa Inggris; jelaskan artinya dengan kata biasa. Bulatkan angka (contoh 1,29% menjadi sekitar
1%)."""

# Semua teks yang dibaca user memakai gaya bahasa yang sama.
RISK_ANALYST += "\n\n" + PLAIN_LANGUAGE
COACH += "\n\n" + PLAIN_LANGUAGE
HISTORY_QA += "\n\n" + PLAIN_LANGUAGE
KNOWLEDGE_INFO += "\n\n" + PLAIN_LANGUAGE
SMALLTALK += "\n\n" + PLAIN_LANGUAGE
