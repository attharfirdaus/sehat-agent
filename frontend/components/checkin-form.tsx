"use client";

import {
  ChevronDown,
  ClipboardPen,
  Footprints,
  GlassWater,
  Moon,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { DailyLogIn } from "@/lib/types";

const REQUIRED = [
  {
    name: "steps",
    label: "Langkah",
    step: 1,
    min: 0,
    max: 200000,
    hint: "Dari ponsel atau jam tangan.",
    icon: Footprints,
  },
  {
    name: "sleep_hours",
    label: "Tidur (jam)",
    step: 0.5,
    min: 0,
    max: 24,
    hint: "Contoh: 6,5",
    icon: Moon,
  },
  {
    name: "water_l",
    label: "Air minum (liter)",
    step: 0.1,
    min: 0,
    max: 20,
    hint: "1 gelas ≈ 0,25 liter.",
    icon: GlassWater,
  },
] as const;

// Rentang sama dengan MEASUREMENT_RANGE di backend (validasi input, bukan ambang klinis).
// Berat, tensi, dan denyut istirahat wajib (keputusan 2026-11-23, sama dengan CheckinIn backend);
// kolesterol butuh cek lab sehingga tetap opsional.
const MEASURES = [
  {
    name: "weight_kg",
    required: true,
    label: "Berat badan (kg)",
    step: 0.1,
    min: 20,
    max: 300,
    short: "berat",
  },
  {
    name: "systolic",
    required: true,
    label: "Tensi atas (sistolik)",
    step: 1,
    min: 60,
    max: 260,
    short: "sistolik",
  },
  {
    name: "diastolic",
    required: true,
    label: "Tensi bawah (diastolik)",
    step: 1,
    min: 30,
    max: 160,
    short: "diastolik",
  },
  {
    name: "resting_hr",
    required: true,
    label: "Denyut nadi istirahat",
    step: 1,
    min: 25,
    max: 250,
    short: "nadi istirahat",
  },
  {
    name: "cholesterol_total",
    required: false,
    label: "Kolesterol total",
    step: 1,
    min: 50,
    max: 600,
    short: "kolesterol total",
  },
] as const;

export type CheckinBody = {
  steps: number;
  sleep_hours: number;
  water_l: number;
  smoked: boolean;
  alcohol: boolean;
  calories_kcal: number | null;
  measurements: { kind: string; value: number }[];
};

/** Ringkasan untuk gelembung chat user; sama dengan teks yang disimpan backend di riwayat. */
export function summarize(b: CheckinBody): string {
  const parts = [
    `langkah ${b.steps}`,
    `tidur ${b.sleep_hours} jam`,
    `air ${b.water_l} liter`,
    b.smoked ? "merokok" : "tidak merokok",
    b.alcohol ? "minum alkohol" : "tidak minum alkohol",
    ...(b.calories_kcal != null ? [`kalori ${b.calories_kcal} kkal`] : []),
    ...b.measurements.map(
      (m) =>
        `${MEASURES.find((o) => o.name === m.kind)?.short ?? m.kind} ${m.value}`,
    ),
  ];
  return "Check-in lewat form: " + parts.join(", ");
}

/** Tanggal hari ini di zona waktu perangkat (pengguna di Indonesia, sama dengan TZ backend). */
function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Form check-in harian yang tampil di dalam chat (POST /api/checkin lewat onSubmit). */
export function CheckinForm({
  onSubmit,
  onClose,
  disabled,
}: {
  onSubmit: (body: CheckinBody) => void;
  onClose: () => void;
  disabled: boolean;
}) {
  const [existing, setExisting] = useState<DailyLogIn | null | undefined>(
    undefined,
  );

  useEffect(() => {
    const day = localToday();
    api<DailyLogIn[]>(`/logs?from=${day}&to=${day}`).then(
      (logs) => setExisting(logs[0] ?? null),
      () => setExisting(null),
    );
  }, []);

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const num = (k: string) =>
      f.get(k) === "" || f.get(k) === null ? null : Number(f.get(k));
    onSubmit({
      steps: num("steps")!,
      sleep_hours: num("sleep_hours")!,
      water_l: num("water_l")!,
      smoked: f.get("smoked") === "true",
      alcohol: f.get("alcohol") === "true",
      calories_kcal: num("calories_kcal"),
      measurements: MEASURES.filter((o) => num(o.name) !== null).map((o) => ({
        kind: o.name,
        value: num(o.name)!,
      })),
    });
  }

  return (
    <section
      aria-labelledby="checkin-title"
      className="rounded-2xl bg-card p-4 shadow-card ring-1 ring-primary/30 md:p-5"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2
            id="checkin-title"
            className="flex items-center gap-2 text-base font-bold tracking-tight"
          >
            <ClipboardPen aria-hidden className="size-4 text-primary" /> Catat
            hari ini
          </h2>
          <p className="text-sm text-muted-foreground">
            {existing
              ? "Sudah ada catatan hari ini; isian terisi dari catatan itu dan akan diperbarui."
              : "Isi semua data wajib, lalu risiko dan rencana dinilai otomatis."}
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          aria-label="Tutup form"
          onClick={onClose}
        >
          <X aria-hidden />
        </Button>
      </div>

      {existing === undefined ? (
        <p className="mt-4 text-sm text-muted-foreground">Memuat…</p>
      ) : (
        <form onSubmit={submit} className="mt-4 flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-3">
            {REQUIRED.map((r) => (
              <div key={r.name} className="flex flex-col gap-1.5">
                <Label htmlFor={r.name} className="flex items-center gap-1.5">
                  <r.icon aria-hidden className="size-4 text-primary" />{" "}
                  {r.label}
                </Label>
                <Input
                  id={r.name}
                  name={r.name}
                  type="number"
                  inputMode="decimal"
                  required
                  min={r.min}
                  max={r.max}
                  step={r.step}
                  defaultValue={existing?.[r.name] ?? undefined}
                  aria-describedby={`${r.name}-hint`}
                />
                <p
                  id={`${r.name}-hint`}
                  className="text-xs text-muted-foreground"
                >
                  {r.hint}
                </p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {(["smoked", "alcohol"] as const).map((k) => (
              <fieldset key={k}>
                <legend className="mb-1.5 text-sm font-medium">
                  {k === "smoked"
                    ? "Merokok hari ini?"
                    : "Minum alkohol hari ini?"}
                </legend>
                <div className="grid grid-cols-2 gap-1 rounded-xl bg-muted p-1">
                  {(["false", "true"] as const).map((v) => (
                    <label key={v} className="relative">
                      <input
                        type="radio"
                        name={k}
                        value={v}
                        required
                        defaultChecked={
                          existing?.[k] != null && String(existing[k]) === v
                        }
                        className="peer sr-only"
                      />
                      <span className="flex min-h-10 cursor-pointer items-center justify-center rounded-lg text-sm font-medium text-muted-foreground transition-colors duration-150 peer-checked:bg-card peer-checked:text-primary peer-checked:shadow-card peer-focus-visible:outline-2 peer-focus-visible:outline-ring">
                        {v === "true" ? "Ya" : "Tidak"}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
            ))}
          </div>

          <fieldset>
            <legend className="mb-1 text-sm font-semibold">
              Pengukuran hari ini
            </legend>
            <p className="mb-3 text-xs text-muted-foreground">
              Pakai timbangan, tensimeter, atau jam pintar. Denyut nadi bisa
              dihitung sendiri selama 1 menit saat duduk santai.
            </p>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              {MEASURES.filter((o) => o.required).map((o) => (
                <div key={o.name} className="flex flex-col gap-1.5">
                  <Label htmlFor={o.name}>{o.label}</Label>
                  <Input
                    id={o.name}
                    name={o.name}
                    type="number"
                    inputMode="decimal"
                    required
                    min={o.min}
                    max={o.max}
                    step={o.step}
                  />
                </div>
              ))}
            </div>
          </fieldset>

          <details className="group rounded-xl bg-muted/60 px-4 py-1">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between text-sm font-medium [&::-webkit-details-marker]:hidden">
              Tambahan (opsional): kalori dan kolesterol
              <ChevronDown
                aria-hidden
                className="size-4 transition-transform duration-150 group-open:rotate-180"
              />
            </summary>
            <div className="grid gap-4 py-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="calories_kcal">Kalori (kkal)</Label>
                <Input
                  id="calories_kcal"
                  name="calories_kcal"
                  type="number"
                  inputMode="numeric"
                  min={0}
                  max={20000}
                  defaultValue={existing?.calories_kcal ?? undefined}
                />
              </div>
              {MEASURES.filter((o) => !o.required).map((o) => (
                <div key={o.name} className="flex flex-col gap-1.5">
                  <Label htmlFor={o.name}>{o.label}</Label>
                  <Input
                    id={o.name}
                    name={o.name}
                    type="number"
                    inputMode="decimal"
                    min={o.min}
                    max={o.max}
                    step={o.step}
                  />
                  <p className="text-xs text-muted-foreground">
                    Isi kalau baru cek lab.
                  </p>
                </div>
              ))}
            </div>
          </details>

          <div className="flex flex-wrap gap-2">
            <Button type="submit" size="lg" disabled={disabled}>
              <ClipboardPen aria-hidden /> Simpan dan nilai
            </Button>
            <Button type="button" variant="ghost" size="lg" onClick={onClose}>
              Batal
            </Button>
          </div>
        </form>
      )}
    </section>
  );
}
