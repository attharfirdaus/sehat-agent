# Laporan evaluasi SehatAgent

Dijalankan 2026-11-21 13:46 UTC · LLM `qwen3.5:9b` · embedding `bge-m3` · thinking off.

## Ringkasan vs target (PRD bagian 2)

| Metrik | Hasil | Target |
| --- | --- | --- |
| Akurasi ekstraksi intake (min. per field) | 97% | >= 90% per field |
| Akurasi routing intent | 98% | — |
| Recall red flag | 100% | 100% |
| Coverage sitasi | 100% | 100% |
| Groundedness angka (persona) | 100% | 100% |
| Lolos Safety Critic tanpa fallback | 70% | — |
| Latensi check-in p50 / p95 | 67 s / 142 s | < baseline n8n ±120 s |

## Intake (30 kalimat)

| Field | Akurasi |
| --- | --- |
| steps | 100% |
| sleep_hours | 100% |
| water_l | 97% |
| smoked | 100% |
| alcohol | 100% |
| exact match per kalimat | 97% |

## Routing (40 pesan)

Baris = label, kolom = prediksi.

| | log | history_question | health_info | smalltalk |
| --- | --- | --- | --- | --- |
| log | 10 | 0 | 0 | 0 |
| history_question | 0 | 9 | 1 | 0 |
| health_info | 0 | 0 | 10 | 0 |
| smalltalk | 0 | 0 | 0 | 10 |

## Red flag (15 kasus)

Recall 100%.

## Persona (10)

| Persona | Detik | Aksi | Bersitasi | Angka grounded | Lolos critic | Fallback | Review clinician | Flags | Alasan fallback |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| sehat-25 | 92.6 | 12 | 12 | True | True | False | False | – | – |
| overweight-35 | 66.9 | 12 | 12 | True | True | False | False | BP_ELEVATED, BMI_OVERWEIGHT, PA_NONE, SLEEP_SHORT | – |
| hipertensi-st1-45 | 82.8 | 1 | 1 | True | False | True | False | BP_STAGE1, BMI_OBESE, SLEEP_SHORT | sitasi tidak ada di hasil retrieval ['KEMENKES-PNPK-HT-2026']: 'Ukur tekanan darah di ruma |
| perokok-30 | 44.5 | 8 | 8 | True | True | False | False | BP_STAGE1, SLEEP_SHORT, SMOKING | – |
| muda-21 | 35.4 | 5 | 5 | True | True | False | False | SLEEP_SHORT | – |
| usia-52 | 126.7 | 12 | 12 | True | True | False | False | BP_STAGE1, BMI_OVERWEIGHT, CHOL_BORDERLINE | – |
| kurang-tidur-28 | 41.1 | 5 | 5 | True | True | False | False | SLEEP_SHORT | – |
| obesitas-hipertensi-48 | 78.6 | 1 | 1 | True | False | True | False | BP_STAGE2, BMI_OBESE, PA_NONE, SLEEP_SHORT | rencana harus 4 minggu, bukan 5 |
| prediabetes-risk-40 | 68.0 | 9 | 9 | True | True | False | False | BP_STAGE1, BMI_OBESE, PA_NONE, SLEEP_SHORT, CHOL_HIGH | – |
| lansia-63 | 64.1 | 1 | 1 | True | False | True | False | BP_STAGE1, BMI_OBESE | rencana harus 4 minggu, bukan 1 |

## Model diabetes (test split)

| Metrik | Nilai |
| --- | --- |
| roc_auc | 0.8232 |
| pr_auc | 0.4153 |
| threshold | 0.35 |
| recall | 0.3678 |
| precision | 0.4597 |
| brier | 0.0981 |
| prevalence | 0.1393 |
| CV ROC-AUC (5-fold) | 0.8266 ± 0.0021 |

## Foto makanan

Dilewati: belum ada foto di eval/meals_15/ (lihat README di folder itu).

Belum dijalankan: review manusia oleh tenaga medis dan ablation (PRD bagian 15).
