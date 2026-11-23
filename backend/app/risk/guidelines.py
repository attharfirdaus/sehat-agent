"""Ambang medis (PRD bagian 8.1 dan 13). Satu-satunya tempat angka klinis.

Pilihan tim 2026-11-21: tekanan darah ACC/AHA 2017, BMI WHO Asia-Pasifik.
NEEDS_VERIFICATION: semua nilai di bawah adalah draft PRD 8.1/13 dan wajib dicocokkan track C ke
dokumen sumber sebelum dikunci (PRD bagian 17). `*_SOURCE` = source_id korpus RAG bila ada.
"""

# --- Tekanan darah: ACC/AHA 2017 (mmHg) -------------------------------------------------
BP_ELEVATED_SYS = 120  # 120-129 dan diastolik < 80
BP_STAGE1_SYS = 130  # 130-139 atau diastolik 80-89
BP_STAGE1_DIA = 80
BP_STAGE2_SYS = 140  # >= 140 atau diastolik >= 90
BP_STAGE2_DIA = 90
BP_CRISIS_SYS = 180  # >= 180 atau diastolik >= 120 (ACC/AHA 2017, juga RF-BP-CRISIS bagian 13)
BP_CRISIS_DIA = 120
# NEEDS_VERIFICATION: ACC/AHA tidak ada di korpus; PNPK HT 2026 dipakai sebagai rujukan lokal.
BP_SOURCE = "KEMENKES-PNPK-HT-2026"

# --- BMI: WHO WPRO 2000 / WHO expert consultation 2004, cut-off Asia-Pasifik (kg/m2) -----
BMI_UNDERWEIGHT = 18.5  # < 18,5 kurang
BMI_OVERWEIGHT = 23.0  # 23-24,9 overweight
BMI_OBESE = 25.0  # >= 25 obesitas
BMI_SOURCE = "WHO-FS-OBES"

# --- Aktivitas: WHO 2020 physical activity guidelines ------------------------------------
PA_MIN_MINUTES_WEEK = 150  # 150-300 menit aktivitas sedang per minggu
# NEEDS_VERIFICATION: PRD memakai langkah harian sebagai proxy tetapi tidak memberi ambang.
# None = flag langkah tidak aktif; hanya profil phys_activity_30d=False yang memicu flag.
STEPS_PROXY_MIN: int | None = None
PA_SOURCE = "WHO-PA-2020"

# --- Tidur: AASM/SRS consensus 2015 (dewasa) ---------------------------------------------
SLEEP_MIN_HOURS = 7.0
SLEEP_SOURCE: str | None = None  # tidak ada di korpus

# --- Kolesterol total: NCEP ATP III (mg/dL) ----------------------------------------------
CHOL_BORDERLINE = 200  # 200-239 batas tinggi
CHOL_HIGH = 240  # >= 240 tinggi (juga dipakai fitur HighChol, bagian 8.3)
CHOL_SOURCE: str | None = None  # tidak ada di korpus

# --- Denyut jantung istirahat: definisi takikardia umum (bpm) ----------------------------
RESTING_HR_HIGH = 100
RHR_SOURCE: str | None = None

# --- Merokok: WHO tobacco fact sheet -------------------------------------------------------
SMOKING_SOURCE = "WHO-FS-TOB"

# --- Umur data (PRD 8.1): measurement lebih tua dari ini = "data lama", tidak boleh urgent --
STALE_DAYS = 90

# --- Red flag (bagian 13) --------------------------------------------------------------------
RF_BP_WINDOW_HOURS = 24  # RF-BP-CRISIS hanya untuk pengukuran <= 24 jam terakhir
RF_HR_HIGH = 120  # resting HR > 120
RF_HR_LOW = 40  # resting HR < 40

# --- Framingham 2008 non-lab (D'Agostino et al., Circulation 2008;117:743-753) -------------
FRAMINGHAM_AGE_MIN = 30
FRAMINGHAM_AGE_MAX = 74
# NEEDS_VERIFICATION: batas kategori risiko 10 tahun tidak ada di PRD; konvensi umum FRS.
FRAMINGHAM_INTERMEDIATE_PCT = 10.0  # < 10 rendah
FRAMINGHAM_HIGH_PCT = 20.0  # >= 20 tinggi

# --- Band probabilitas diabetes (bagian 8.3) ----------------------------------------------
# NEEDS_VERIFICATION: PRD tidak memberi batas band. Placeholder sampai tim menetapkan
# (misalnya dari kalibrasi + prevalensi BRFSS ~14%).
DIABETES_MODERATE_PROB = 0.15
DIABETES_HIGH_PROB = 0.35
