"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";

const SELECT =
  "h-10 w-full rounded-lg border border-input bg-transparent px-3 text-base sm:text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30";

// Pertanyaan ya/tidak di tabel `profiles` (bagian 9). Penjelasan mengikuti codebook BRFSS
// supaya jawaban cocok dengan fitur model diabetes (bagian 8.3).
const QUESTIONS: { name: string; label: string; help: string }[] = [
  {
    name: "dx_hypertension",
    label: "Pernah diberi tahu dokter bahwa tekanan darah Anda tinggi?",
    help: "Diagnosis oleh dokter atau tenaga kesehatan, kapan pun.",
  },
  {
    name: "bp_treated",
    label: "Saat ini sedang menjalani pengobatan tekanan darah?",
    help: "Dipakai skor risiko kardiovaskular (Framingham).",
  },
  {
    name: "dx_high_chol",
    label: "Pernah diberi tahu dokter bahwa kolesterol Anda tinggi?",
    help: "Diagnosis oleh dokter atau tenaga kesehatan, kapan pun.",
  },
  {
    name: "dx_diabetes",
    label: "Pernah didiagnosis diabetes?",
    help: "Diagnosis oleh dokter atau tenaga kesehatan.",
  },
  {
    name: "family_history_cvd",
    label: "Ada keluarga inti dengan penyakit jantung atau stroke?",
    help: "Orang tua atau saudara kandung.",
  },
  {
    name: "family_history_diabetes",
    label: "Ada keluarga inti dengan diabetes?",
    help: "Orang tua atau saudara kandung.",
  },
  {
    name: "smoker_lifetime_100",
    label: "Pernah merokok minimal 100 batang seumur hidup?",
    help: "Definisi BRFSS: 100 batang kira-kira 5 bungkus.",
  },
  {
    name: "phys_activity_30d",
    label:
      "Dalam 30 hari terakhir, melakukan aktivitas fisik atau olahraga di luar pekerjaan?",
    help: "Contoh: jalan kaki, lari, bersepeda, berkebun.",
  },
  {
    name: "fruits_daily",
    label: "Makan buah 1 kali atau lebih setiap hari?",
    help: "Definisi BRFSS.",
  },
  {
    name: "veggies_daily",
    label: "Makan sayur 1 kali atau lebih setiap hari?",
    help: "Definisi BRFSS.",
  },
  {
    name: "heavy_alcohol",
    label: "Minum alkohol berat?",
    help: "Definisi BRFSS: pria 14 gelas atau lebih per minggu, wanita 7 gelas atau lebih per minggu.",
  },
  {
    name: "diff_walk",
    label: "Mengalami kesulitan serius berjalan atau naik tangga?",
    help: "Definisi BRFSS.",
  },
];

const GEN_HEALTH = [
  "Sangat baik sekali",
  "Sangat baik",
  "Baik",
  "Cukup",
  "Buruk",
];

function triState(v: FormDataEntryValue | null): boolean | null {
  return v === "true" ? true : v === "false" ? false : null;
}

function triDefault(v: unknown): string {
  return v === true ? "true" : v === false ? "false" : "";
}

/** Form profil statis (tabel `profiles`), dipakai /onboarding dan /settings. */
export function ProfileForm({
  initial,
  requireConsent,
  submitLabel,
  onSaved,
}: {
  initial?: Profile | null;
  requireConsent: boolean;
  submitLabel: string;
  onSaved?: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const body = {
      birth_date: f.get("birth_date"),
      sex: f.get("sex"),
      height_cm: Number(f.get("height_cm")),
      gen_health: f.get("gen_health") ? Number(f.get("gen_health")) : null,
      ...Object.fromEntries(
        QUESTIONS.map((q) => [q.name, triState(f.get(q.name))]),
      ),
    };
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      await api("/profile", { method: "PUT", body });
      setSaved(true);
      onSaved?.();
    } catch {
      setError(
        "Ada isian yang belum valid. Periksa tanggal lahir dan tinggi badan.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      <fieldset className="grid gap-4 sm:grid-cols-3">
        <legend className="mb-2 text-sm font-medium">Data dasar</legend>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="birth_date">Tanggal lahir</Label>
          <Input
            id="birth_date"
            name="birth_date"
            type="date"
            required
            defaultValue={initial?.birth_date}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="sex">Jenis kelamin</Label>
          <select
            id="sex"
            name="sex"
            required
            className={SELECT}
            defaultValue={initial?.sex ?? ""}
          >
            <option value="" disabled>
              Pilih
            </option>
            <option value="female">Perempuan</option>
            <option value="male">Laki-laki</option>
          </select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="height_cm">Tinggi badan (cm)</Label>
          <Input
            id="height_cm"
            name="height_cm"
            type="number"
            inputMode="decimal"
            min={50}
            max={250}
            step={0.1}
            required
            defaultValue={initial?.height_cm}
          />
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-4">
        <legend className="mb-2 text-sm font-medium">
          Riwayat dan kebiasaan (boleh &quot;Tidak tahu&quot;)
        </legend>
        {QUESTIONS.map((q) => (
          <div
            key={q.name}
            className="grid gap-1.5 sm:grid-cols-[1fr_9rem] sm:items-center"
          >
            <div>
              <Label htmlFor={q.name}>{q.label}</Label>
              <p
                id={`${q.name}-help`}
                className="text-xs text-muted-foreground"
              >
                {q.help}
              </p>
            </div>
            <select
              id={q.name}
              name={q.name}
              aria-describedby={`${q.name}-help`}
              className={SELECT}
              defaultValue={triDefault(initial?.[q.name])}
            >
              <option value="">Tidak tahu</option>
              <option value="true">Ya</option>
              <option value="false">Tidak</option>
            </select>
          </div>
        ))}
        <div className="grid gap-1.5 sm:grid-cols-[1fr_9rem] sm:items-center">
          <div>
            <Label htmlFor="gen_health">
              Secara umum, kesehatan Anda saat ini?
            </Label>
            <p className="text-xs text-muted-foreground">
              Penilaian diri sendiri (BRFSS).
            </p>
          </div>
          <select
            id="gen_health"
            name="gen_health"
            className={SELECT}
            defaultValue={initial?.gen_health ?? ""}
          >
            <option value="">Tidak tahu</option>
            {GEN_HEALTH.map((label, i) => (
              <option key={label} value={i + 1}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </fieldset>

      {requireConsent && (
        <label className="flex items-start gap-2 rounded-lg border border-border p-3 text-sm">
          <input
            type="checkbox"
            required
            className="mt-0.5 size-4 accent-primary"
          />
          <span>
            Saya setuju profil, catatan harian, dan foto makanan saya disimpan
            di server lokal aplikasi ini untuk menilai risiko dan membuat
            rekomendasi. Saya paham hasilnya bukan diagnosis medis.
          </span>
        </label>
      )}
      {/* TODO(PRD): persetujuan belum disimpan; tabel profiles tidak punya kolomnya. */}

      {saved && (
        <p role="status" className="text-sm text-muted-foreground">
          Profil tersimpan.
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" size="lg" disabled={busy}>
        {busy ? "Menyimpan…" : submitLabel}
      </Button>
    </form>
  );
}
