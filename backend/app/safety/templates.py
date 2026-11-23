"""Teks tetap untuk pesan rujukan (PRD bagian 13). Bukan hasil generate LLM.

NEEDS_VERIFICATION: seluruh teks harus diverifikasi track C sebelum demo.
"""

REFERRAL = {
    "RF-SYMPTOM": (
        "Gejala yang Anda sebutkan bisa menandakan kondisi darurat. "
        "Segera hubungi 119 atau datang ke IGD terdekat sekarang. "
        "Jangan menunggu gejala hilang sendiri."
    ),
    # NEEDS_VERIFICATION: tambahkan layanan dukungan krisis kesehatan jiwa yang berlaku di
    # Indonesia (PRD bagian 17). Jangan isi nomor sebelum diverifikasi tim.
    "RF-SELFHARM": (
        "Terima kasih sudah mau bercerita. Anda tidak sendirian, dan perasaan ini layak "
        "mendapat bantuan. Kalau Anda dalam bahaya sekarang, hubungi 119 atau datang ke IGD "
        "terdekat. Cobalah juga menghubungi orang yang Anda percaya."
    ),
    "RF-BP-CRISIS": (
        "Tekanan darah yang tercatat sangat tinggi. Segera periksa ke fasilitas kesehatan atau "
        "IGD terdekat, terutama jika disertai sakit kepala hebat, nyeri dada, atau sesak napas."
    ),
    "RF-HR": (
        "Denyut jantung istirahat yang tercatat di luar rentang yang aman. "
        "Silakan periksakan diri ke fasilitas kesehatan."
    ),
}

DISCLAIMER = (
    "Catatan: hasil ini bukan diagnosis medis dan tidak menggantikan konsultasi dengan "
    "tenaga kesehatan."
)

DIABETES_CAVEAT = (
    "Prediksi diabetes berasal dari data survei self-report di AS (CDC BRFSS 2015) dengan fitur "
    "biner. Ini indikasi untuk skrining dini, bukan diagnosis."
)

FRAMINGHAM_CAVEAT = (
    "Skor Framingham dikembangkan pada kohort AS; kalibrasinya untuk populasi Indonesia belum "
    "divalidasi."
)
