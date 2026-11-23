"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { RichText } from "@/components/rich-text";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api, streamChat } from "@/lib/api";
import { NODE_LABEL } from "@/lib/labels";
import type { ChatEvent, DailyLogIn } from "@/lib/types";

const SELECT =
  "h-10 w-full rounded-lg border border-input bg-transparent px-3 text-base sm:text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30";

const REQUIRED = [
  { name: "steps", label: "Jumlah langkah", step: 1, min: 0, max: 200000, hint: "Dari ponsel atau jam tangan." },
  { name: "sleep_hours", label: "Tidur semalam (jam)", step: 0.5, min: 0, max: 24, hint: "Contoh: 6,5" },
  { name: "water_l", label: "Air minum (liter)", step: 0.1, min: 0, max: 20, hint: "1 gelas kira-kira 0,25 liter." },
] as const;

// Rentang sama dengan MEASUREMENT_RANGE di backend (validasi input, bukan ambang klinis).
const OPTIONAL = [
  { name: "weight_kg", label: "Berat badan (kg)", step: 0.1, min: 20, max: 300 },
  { name: "systolic", label: "Tensi sistolik (mmHg)", step: 1, min: 60, max: 260 },
  { name: "diastolic", label: "Tensi diastolik (mmHg)", step: 1, min: 30, max: 160 },
  { name: "resting_hr", label: "Denyut istirahat (bpm)", step: 1, min: 25, max: 250 },
  { name: "cholesterol_total", label: "Kolesterol total (mg/dL)", step: 1, min: 50, max: 600 },
] as const;

/** Tanggal hari ini di zona waktu perangkat (pengguna di Indonesia, sama dengan TZ backend). */
function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function CheckinContent() {
  const [existing, setExisting] = useState<DailyLogIn | null | undefined>(undefined);
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
    const num = (k: string) => (f.get(k) === "" || f.get(k) === null ? null : Number(f.get(k)));
    if ((num("systolic") === null) !== (num("diastolic") === null)) {
      setBpError(true);
      document.getElementById(num("systolic") === null ? "systolic" : "diastolic")?.focus();
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
      measurements: OPTIONAL.filter((o) => num(o.name) !== null).map((o) => ({ kind: o.name, value: num(o.name) })),
    };
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      await streamChat("/checkin", body, (ev: ChatEvent) => {
        if (ev.event === "node_start") setStatus(NODE_LABEL[ev.data.node] ?? null);
        else if (ev.event === "final") setResult(ev.data.text);
        else if (ev.event === "error") setError("Terjadi kesalahan saat menilai catatan. Data mungkin sudah tersimpan.");
      });
    } catch (err) {
      setError(err instanceof ApiError && err.status === 422 ? "Ada isian yang di luar rentang." : "Tidak bisa terhubung ke server.");
    } finally {
      setBusy(false);
      setStatus(null);
    }
  }

  return (
    <main className="flex-1 overflow-y-auto px-4 py-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Catat hari ini</CardTitle>
          <CardDescription>
            Lima isian wajib, sisanya opsional. Setelah disimpan, risiko dan rencana dinilai otomatis. Foto
            makanan dan pertanyaan bebas lewat{" "}
            <Link href="/chat" className="text-foreground underline">
              chat
            </Link>
            .
          </CardDescription>
        </CardHeader>
        <CardContent>
          {existing === undefined ? (
            <p className="text-sm text-muted-foreground">Memuat…</p>
          ) : (
            <form onSubmit={onSubmit} className="flex flex-col gap-6">
              {existing && (
                <p className="rounded-lg bg-muted px-3 py-2 text-sm">
                  Hari ini sudah ada catatan. Isian di bawah terisi dari catatan itu; mengirim ulang akan
                  memperbaruinya.
                </p>
              )}
              <fieldset className="grid gap-4 sm:grid-cols-3">
                <legend className="mb-2 text-sm font-medium">Wajib</legend>
                {REQUIRED.map((r) => (
                  <div key={r.name} className="flex flex-col gap-1.5">
                    <Label htmlFor={r.name}>{r.label}</Label>
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
                    <p id={`${r.name}-hint`} className="text-xs text-muted-foreground">
                      {r.hint}
                    </p>
                  </div>
                ))}
                {(["smoked", "alcohol"] as const).map((k) => (
                  <div key={k} className="flex flex-col gap-1.5">
                    <Label htmlFor={k}>{k === "smoked" ? "Merokok hari ini?" : "Minum alkohol hari ini?"}</Label>
                    <select
                      id={k}
                      name={k}
                      required
                      className={SELECT}
                      defaultValue={existing?.[k] == null ? "" : String(existing[k])}
                    >
                      <option value="" disabled>
                        Pilih
                      </option>
                      <option value="false">Tidak</option>
                      <option value="true">Ya</option>
                    </select>
                  </div>
                ))}
              </fieldset>

              <fieldset className="grid gap-4 sm:grid-cols-3">
                <legend className="mb-2 text-sm font-medium">Opsional (isi kalau memang diukur hari ini)</legend>
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
                      aria-invalid={bpError && (o.name === "systolic" || o.name === "diastolic")}
                      aria-describedby={bpError && (o.name === "systolic" || o.name === "diastolic") ? "bp-error" : undefined}
                    />
                    {bpError && o.name === "diastolic" && (
                      <p id="bp-error" role="alert" className="text-xs text-destructive">
                        Isi tensi sistolik dan diastolik sekaligus.
                      </p>
                    )}
                  </div>
                ))}
                <p className="text-xs text-muted-foreground sm:col-span-3">
                  Berat badan perlu dicatat minimal sekali agar skor jantung dan risiko diabetes bisa dihitung.
                </p>
              </fieldset>

              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" size="lg" disabled={busy}>
                  {busy ? "Memproses…" : "Simpan dan nilai"}
                </Button>
                <Link
                  href="/chat"
                  className="inline-flex h-11 items-center rounded-lg border border-border bg-card px-4 text-base sm:text-sm hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
                >
                  Tambah foto makanan
                </Link>
              </div>
            </form>
          )}
          {status && (
            <p role="status" className="mt-4 motion-safe:animate-pulse text-sm text-muted-foreground">
              {status}
            </p>
          )}
          {result && (
            <section aria-label="Hasil penilaian" className="mt-6 rounded-xl bg-muted p-4 text-base sm:text-sm">
              <RichText text={result} />
              <p className="mt-3 flex gap-4">
                <Link href="/dashboard" className="underline">
                  Lihat dashboard
                </Link>
                <Link href="/chat" className="underline">
                  Lanjut di chat
                </Link>
              </p>
            </section>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

export default function CheckinPage() {
  return <AppShell>{() => <CheckinContent />}</AppShell>;
}
