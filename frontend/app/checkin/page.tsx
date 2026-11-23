"use client";

import {
  CheckCircle2,
  ClipboardPen,
  Footprints,
  GlassWater,
  ImagePlus,
  Loader2,
  Moon,
  Ruler,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { RichText } from "@/components/rich-text";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api, streamChat } from "@/lib/api";
import { NODE_LABEL } from "@/lib/labels";
import type { ChatEvent, DailyLogIn } from "@/lib/types";

const CARD = "rounded-2xl bg-card p-5 shadow-card ring-1 ring-border/70 md:p-6";

const REQUIRED = [
  {
    name: "steps",
    label: "Jumlah langkah",
    step: 1,
    min: 0,
    max: 200000,
    hint: "Dari ponsel atau jam tangan.",
    icon: Footprints,
  },
  {
    name: "sleep_hours",
    label: "Tidur semalam (jam)",
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
    hint: "1 gelas kira-kira 0,25 liter.",
    icon: GlassWater,
  },
] as const;

// Rentang sama dengan MEASUREMENT_RANGE di backend (validasi input, bukan ambang klinis).
const OPTIONAL = [
  {
    name: "weight_kg",
    label: "Berat badan (kg)",
    step: 0.1,
    min: 20,
    max: 300,
  },
  {
    name: "systolic",
    label: "Tensi sistolik (mmHg)",
    step: 1,
    min: 60,
    max: 260,
  },
  {
    name: "diastolic",
    label: "Tensi diastolik (mmHg)",
    step: 1,
    min: 30,
    max: 160,
  },
  {
    name: "resting_hr",
    label: "Denyut istirahat (bpm)",
    step: 1,
    min: 25,
    max: 250,
  },
  {
    name: "cholesterol_total",
    label: "Kolesterol total (mg/dL)",
    step: 1,
    min: 50,
    max: 600,
  },
] as const;

/** Tanggal hari ini di zona waktu perangkat (pengguna di Indonesia, sama dengan TZ backend). */
function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function CheckinContent() {
  const [existing, setExisting] = useState<DailyLogIn | null | undefined>(
    undefined,
  );
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bpError, setBpError] = useState(false);

  useEffect(() => {
    const day = localToday();
    api<DailyLogIn[]>(`/logs?from=${day}&to=${day}`).then(
      (logs) => setExisting(logs[0] ?? null),
      () => setExisting(null),
    );
  }, []);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const num = (k: string) =>
      f.get(k) === "" || f.get(k) === null ? null : Number(f.get(k));
    if ((num("systolic") === null) !== (num("diastolic") === null)) {
      setBpError(true);
      document
        .getElementById(num("systolic") === null ? "systolic" : "diastolic")
        ?.focus();
      return;
    }
    setBpError(false);
    const body = {
      steps: num("steps"),
      sleep_hours: num("sleep_hours"),
      water_l: num("water_l"),
      smoked: f.get("smoked") === "true",
      alcohol: f.get("alcohol") === "true",
      calories_kcal: num("calories_kcal"),
      measurements: OPTIONAL.filter((o) => num(o.name) !== null).map((o) => ({
        kind: o.name,
        value: num(o.name),
      })),
    };
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      await streamChat("/checkin", body, (ev: ChatEvent) => {
        if (ev.event === "node_start")
          setStatus(NODE_LABEL[ev.data.node] ?? null);
        else if (ev.event === "final") setResult(ev.data.text);
        else if (ev.event === "error")
          setError(
            "Terjadi kesalahan saat menilai catatan. Data mungkin sudah tersimpan.",
          );
      });
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422
          ? "Ada isian yang di luar rentang."
          : "Tidak bisa terhubung ke server.",
      );
    } finally {
      setBusy(false);
      setStatus(null);
    }
  }

  return (
    <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
      {existing === undefined ? (
        <p className="text-sm text-muted-foreground">Memuat…</p>
      ) : (
        <div className="grid items-start gap-6 xl:grid-cols-[1fr_26rem]">
          <form onSubmit={onSubmit} className="flex flex-col gap-6">
            {existing && (
              <p className="flex items-center gap-2 rounded-xl bg-secondary px-4 py-3 text-sm">
                <CheckCircle2
                  aria-hidden
                  className="size-4 shrink-0 text-primary"
                />
                Hari ini sudah ada catatan. Isian terisi dari catatan itu;
                mengirim ulang akan memperbaruinya.
              </p>
            )}
            <fieldset className={CARD}>
              <legend className="sr-only">Isian wajib</legend>
              <h2 className="text-base font-bold tracking-tight">
                Aktivitas hari ini
              </h2>
              <p className="text-sm text-muted-foreground">Lima isian wajib.</p>
              <div className="mt-5 grid gap-5 md:grid-cols-3">
                {REQUIRED.map((r) => (
                  <div key={r.name} className="flex flex-col gap-1.5">
                    <Label htmlFor={r.name} className="flex items-center gap-2">
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
              <div className="mt-5 grid gap-5 md:grid-cols-2">
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
            </fieldset>

            <fieldset className={CARD}>
              <legend className="sr-only">Isian opsional</legend>
              <h2 className="flex items-center gap-2 text-base font-bold tracking-tight">
                <Ruler aria-hidden className="size-4 text-primary" /> Pengukuran
                (opsional)
              </h2>
              <p className="text-sm text-muted-foreground">
                Isi kalau memang diukur hari ini. Berat badan perlu dicatat
                minimal sekali agar skor jantung dan risiko diabetes bisa
                dihitung.
              </p>
              <div className="mt-5 grid gap-5 sm:grid-cols-2 md:grid-cols-3">
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
                {OPTIONAL.map((o) => (
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
                      aria-invalid={
                        bpError &&
                        (o.name === "systolic" || o.name === "diastolic")
                      }
                      aria-describedby={
                        bpError &&
                        (o.name === "systolic" || o.name === "diastolic")
                          ? "bp-error"
                          : undefined
                      }
                    />
                    {bpError && o.name === "diastolic" && (
                      <p
                        id="bp-error"
                        role="alert"
                        className="text-xs text-destructive"
                      >
                        Isi tensi sistolik dan diastolik sekaligus.
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </fieldset>

            {error && (
              <p role="alert" className="text-sm text-destructive">
                {error}
              </p>
            )}
            <div className="flex flex-wrap gap-3">
              <Button type="submit" size="lg" disabled={busy}>
                <ClipboardPen aria-hidden />{" "}
                {busy ? "Memproses…" : "Simpan dan nilai"}
              </Button>
              <Link
                href="/chat"
                className="inline-flex h-11 items-center gap-2 rounded-lg bg-card px-4 text-base font-medium shadow-card ring-1 ring-border/70 hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring sm:text-sm"
              >
                <ImagePlus aria-hidden className="size-4" /> Tambah foto makanan
              </Link>
            </div>
          </form>

          <aside
            aria-label="Hasil"
            className="flex flex-col gap-4 xl:sticky xl:top-0"
          >
            {status && (
              <p
                role="status"
                className={`${CARD} flex items-center gap-3 text-sm`}
              >
                <Loader2
                  aria-hidden
                  className="size-5 text-primary motion-safe:animate-spin"
                />{" "}
                {status}
              </p>
            )}
            {result ? (
              <section
                aria-label="Hasil penilaian"
                className={`${CARD} text-base sm:text-sm`}
              >
                <h2 className="mb-3 flex items-center gap-2 text-base font-bold tracking-tight">
                  <CheckCircle2 aria-hidden className="size-5 text-primary" />{" "}
                  Hasil penilaian
                </h2>
                <RichText text={result} />
                <p className="mt-4 flex gap-4">
                  <Link
                    href="/dashboard"
                    className="font-medium text-primary underline"
                  >
                    Lihat dashboard
                  </Link>
                  <Link
                    href="/chat"
                    className="font-medium text-primary underline"
                  >
                    Lanjut di chat
                  </Link>
                </p>
              </section>
            ) : (
              !status && (
                <div
                  className={`${CARD} bg-gradient-to-br from-secondary to-card`}
                >
                  <h2 className="text-base font-bold tracking-tight">
                    Setelah disimpan
                  </h2>
                  <ol className="mt-3 flex flex-col gap-2 text-sm text-muted-foreground">
                    <li>1. Catatan tersimpan dan dicek tanda bahayanya.</li>
                    <li>2. Risiko dinilai dari profil dan tren 7 hari.</li>
                    <li>3. Rencana 4 minggu disusun dengan sumber pedoman.</li>
                  </ol>
                  <p className="mt-3 text-xs text-muted-foreground">
                    Biasanya selesai dalam 1–2 menit.
                  </p>
                </div>
              )
            )}
          </aside>
        </div>
      )}
    </main>
  );
}

export default function CheckinPage() {
  return (
    <AppShell
      title="Catat hari ini"
      subtitle="Isi data harian, lalu risiko dan rencana dinilai otomatis"
    >
      {() => <CheckinContent />}
    </AppShell>
  );
}
