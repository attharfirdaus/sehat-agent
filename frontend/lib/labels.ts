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

export const BAND_LABEL = { low: "Rendah", moderate: "Sedang", high: "Tinggi" } as const;

export const FRAMINGHAM_REASON: Record<string, string> = {
  age_out_of_range: "tidak berlaku untuk usia di luar 30–74 tahun",
  missing_weight: "butuh data berat badan",
  missing_systolic: "butuh data tekanan darah",
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
