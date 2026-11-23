// Label tampilan untuk kode dari backend.

export const METRIC_LABEL: Record<string, string> = {
  steps: "Langkah",
  sleep_hours: "Tidur (jam)",
  water_l: "Air (liter)",
  calories: "Kalori (kkal)",
  smoked: "Merokok (hari)",
  alcohol: "Alkohol (hari)",
  systolic: "Sistolik",
  diastolic: "Diastolik",
  resting_hr: "Denyut istirahat",
  weight_kg: "Berat (kg)",
  cholesterol: "Kolesterol",
};

export const BAND_LABEL = {
  low: "Rendah",
  moderate: "Sedang",
  high: "Tinggi",
} as const;

export const FRAMINGHAM_REASON: Record<string, string> = {
  age_out_of_range: "rumusnya hanya untuk usia 30 sampai 74 tahun",
  missing_weight: "data berat badan belum ada",
  missing_systolic: "data tekanan darah belum ada",
};

export const SEVERITY_CLASS = {
  info: "border-border bg-muted text-foreground",
  warn: "border-amber-500/40 bg-amber-500/10 text-amber-900 dark:text-amber-200",
  urgent: "border-destructive/40 bg-destructive/10 text-destructive",
} as const;

export const NODE_LABEL: Record<string, string> = {
  load_context: "Memuat data Anda…",
  red_flag_precheck: "Memeriksa tanda bahaya…",
  supervisor: "Memahami pesan…",
  intake: "Membaca catatan…",
  nutrition: "Menganalisis foto makanan…",
  save_log: "Menyimpan catatan…",
  risk_analyst: "Menganalisis risiko…",
  knowledge: "Mencari pedoman…",
  coach: "Menyusun rencana…",
  safety_critic: "Memeriksa keamanan rencana…",
  safe_fallback: "Menyiapkan saran aman…",
  create_review: "Mengirim ke tenaga medis…",
  history_qa: "Membaca histori Anda…",
  knowledge_info: "Mencari di pedoman…",
  response: "Menulis jawaban…",
};

// Sama dengan FLAG_TEXT / FEATURE_TEXT di backend/app/graph/prompts (bahasa awam).
export const FLAG_LABEL: Record<string, string> = {
  BP_CRISIS: "Tekanan darah sangat tinggi",
  BP_STAGE2: "Tekanan darah tinggi",
  BP_STAGE1: "Tekanan darah sedikit tinggi",
  BP_ELEVATED: "Tekanan darah di atas normal",
  BMI_OBESE: "Berat badan masuk kategori obesitas",
  BMI_OVERWEIGHT: "Berat badan berlebih",
  BMI_UNDERWEIGHT: "Berat badan kurang",
  PA_NONE: "Belum rutin berolahraga",
  STEPS_LOW: "Langkah harian masih sedikit",
  SLEEP_SHORT: "Tidur kurang dari 7 jam",
  CHOL_HIGH: "Kolesterol tinggi",
  CHOL_BORDERLINE: "Kolesterol sedikit tinggi",
  RHR_HIGH: "Denyut jantung saat istirahat tinggi",
  SMOKING: "Merokok",
};

// Fitur biner: kalimat untuk nilai 1 (ya) dan 0 (tidak), supaya "menurunkan risiko" tidak
// terbaca "kolesterol tinggi menurunkan risiko" padahal maksudnya kolesterol tidak tinggi.
const FEATURE_BINARY: Record<string, [string, string]> = {
  HighBP: [
    "riwayat tekanan darah tinggi",
    "tidak ada riwayat tekanan darah tinggi",
  ],
  HighChol: [
    "riwayat kolesterol tinggi",
    "tidak ada riwayat kolesterol tinggi",
  ],
  Smoker: ["pernah merokok", "tidak pernah merokok"],
  PhysActivity: ["rutin berolahraga", "jarang berolahraga"],
  Fruits: ["makan buah setiap hari", "jarang makan buah"],
  Veggies: ["makan sayur setiap hari", "jarang makan sayur"],
  HvyAlcoholConsump: ["minum alkohol berat", "tidak minum alkohol berat"],
  DiffWalk: ["kesulitan berjalan", "tidak kesulitan berjalan"],
};
const FEATURE_PLAIN: Record<string, string> = {
  Age: "usia Anda",
  BMI: "BMI Anda",
  GenHlth: "penilaian kesehatan Anda",
  Sex: "jenis kelamin",
};

export function featureText(f: { feature: string; value: number }): string {
  const binary = FEATURE_BINARY[f.feature];
  if (binary) return f.value ? binary[0] : binary[1];
  return FEATURE_PLAIN[f.feature] ?? f.feature;
}

export const RED_FLAG_LABEL: Record<string, string> = {
  "RF-BP-CRISIS": "Tekanan darah sangat tinggi",
  "RF-SYMPTOM": "Gejala darurat dilaporkan",
  "RF-HR": "Denyut jantung di luar batas aman",
  "RF-SELFHARM": "Butuh dukungan segera",
};
