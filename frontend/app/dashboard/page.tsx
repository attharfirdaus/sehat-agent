"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  ClipboardPen,
  Footprints,
  GlassWater,
  HeartPulse,
  MessageCircle,
  Minus,
  Moon,
  ShieldAlert,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { TrendChart } from "@/components/trend-chart";
import { api } from "@/lib/api";
import {
  BAND_LABEL,
  FLAG_LABEL,
  FRAMINGHAM_REASON,
  METRIC_LABEL,
  RED_FLAG_LABEL,
  SEVERITY_CLASS,
  featureText,
} from "@/lib/labels";
import type { Dashboard, MetricTrend, User } from "@/lib/types";

const CARD = "rounded-2xl bg-card p-5 shadow-card ring-1 ring-border/70";

function fmt(n: number | null | undefined, digits = 1): string {
  return n == null ? "–" : Number(n.toFixed(digits)).toLocaleString("id-ID");
}

function greeting(): string {
  const h = new Date().getHours();
  return h < 11
    ? "Selamat pagi"
    : h < 15
      ? "Selamat siang"
      : h < 18
        ? "Selamat sore"
        : "Selamat malam";
}

/** Perubahan vs periode sebelumnya: ikon + teks, tidak hanya warna. */
function Delta({
  trend,
  unit,
  digits = 1,
}: {
  trend?: MetricTrend;
  unit: string;
  digits?: number;
}) {
  if (!trend || trend.delta == null || trend.delta === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus aria-hidden className="size-3.5" /> belum ada pembanding
      </span>
    );
  }
  const up = trend.delta > 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-foreground">
      <Icon aria-hidden className="size-3.5 text-primary" />
      {up ? "naik" : "turun"} {fmt(Math.abs(trend.delta), digits)} {unit}
    </span>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  unit,
  children,
}: {
  icon: typeof Footprints;
  label: string;
  value: string;
  unit: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl bg-card p-4 shadow-card ring-1 ring-border/70 md:gap-3 md:p-5">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
        <span className="inline-flex size-8 items-center justify-center rounded-lg bg-secondary text-primary">
          <Icon aria-hidden className="size-4" />
        </span>
        {label}
      </div>
      <p className="text-2xl font-bold tracking-tight tabular-nums md:text-3xl">
        {value}{" "}
        <span className="text-sm font-medium text-muted-foreground">
          {unit}
        </span>
      </p>
      {children}
    </div>
  );
}

function DashboardContent({ user }: { user: User }) {
  const [days, setDays] = useState<7 | 30>(7);
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api<Dashboard>(`/dashboard?days=${days}`).then(
      (d) => {
        setData(d);
        setError(false);
      },
      () => setError(true),
    );
  }, [days]);

  if (error)
    return (
      <p className="p-4 text-sm text-destructive md:px-8">
        Gagal memuat dashboard.
      </p>
    );
  if (!data)
    return <p className="p-4 text-sm text-muted-foreground md:px-8">Memuat…</p>;
  const a = data.assessment;
  const m = data.trends.metrics;
  const adherence = Object.values(m)
    .map((t) => t.adherence_pct)
    .filter((x): x is number => x != null);

  return (
    <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
      <div className="grid grid-cols-2 gap-3 md:gap-4 xl:grid-cols-4">
        <section
          aria-label="Ringkasan hari ini"
          className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-primary to-foreground p-6 text-primary-foreground shadow-card col-span-2"
        >
          <HeartPulse
            aria-hidden
            className="absolute -right-6 -bottom-8 size-44 opacity-10"
          />
          <p className="text-sm opacity-90">
            {new Date().toLocaleDateString("id-ID", {
              weekday: "long",
              day: "numeric",
              month: "long",
            })}
          </p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight">
            {greeting()}, {user.name.split(" ")[0]}
          </h2>
          <p className="mt-2 max-w-md text-sm opacity-90">
            {data.assessment_at
              ? `Penilaian terakhir ${new Date(data.assessment_at).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short" })}.`
              : "Belum ada penilaian. Catat aktivitas hari ini untuk mendapat penilaian risiko dan rencana."}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link
              href="/chat?form=1"
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-white px-4 text-sm font-semibold text-primary transition-opacity duration-150 hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              <ClipboardPen aria-hidden className="size-4" /> Catat hari ini
            </Link>
            <Link
              href="/chat"
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-white/15 px-4 text-sm font-semibold ring-1 ring-white/40 transition-colors duration-150 hover:bg-white/25 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
              <MessageCircle aria-hidden className="size-4" /> Tanya SehatAgent
            </Link>
          </div>
        </section>

        <Kpi
          icon={Footprints}
          label={`Langkah rata-rata ${days} hari`}
          value={fmt(m.steps?.mean, 0)}
          unit="/hari"
        >
          <Delta trend={m.steps} unit="langkah" digits={0} />
        </Kpi>
        <Kpi
          icon={Moon}
          label="Tidur rata-rata"
          value={fmt(m.sleep_hours?.mean)}
          unit="jam"
        >
          <Delta trend={m.sleep_hours} unit="jam" />
        </Kpi>
        <Kpi
          icon={GlassWater}
          label="Air minum rata-rata"
          value={fmt(m.water_l?.mean)}
          unit="liter"
        >
          <Delta trend={m.water_l} unit="liter" />
        </Kpi>
        <Kpi
          icon={Target}
          label="Kepatuhan rencana"
          value={
            adherence.length
              ? fmt(adherence.reduce((s, x) => s + x, 0) / adherence.length, 0)
              : "–"
          }
          unit="%"
        >
          <span className="text-xs text-muted-foreground">
            {data.plan
              ? "Rata-rata semua target minggu ini"
              : "Belum ada rencana aktif"}
          </span>
        </Kpi>

        <section
          aria-labelledby="cvd-title"
          className={`${CARD} col-span-2 md:col-span-1`}
        >
          <h2 id="cvd-title" className="text-sm font-semibold">
            Risiko jantung 10 tahun
          </h2>
          <p className="text-xs text-muted-foreground">
            Perkiraan dari usia, tensi, BMI, rokok, dan diabetes
          </p>
          {!a ? (
            <p className="mt-4 text-sm text-muted-foreground">Belum dinilai.</p>
          ) : a.framingham.applicable ? (
            <>
              <p className="mt-4 text-3xl font-bold tabular-nums">
                {fmt(a.framingham.risk_10y_pct)}%
              </p>
              <div
                className="mt-3 h-2 overflow-hidden rounded-full bg-muted"
                aria-hidden
              >
                <div
                  className="h-full rounded-full bg-primary"
                  style={{
                    width: `${Math.min(100, (a.framingham.risk_10y_pct ?? 0) * 3.33)}%`,
                  }}
                />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Dikembangkan pada kohort AS; kalibrasi untuk Indonesia belum
                divalidasi.
              </p>
            </>
          ) : (
            <p className="mt-4 text-sm">
              Belum bisa dihitung, karena{" "}
              {FRAMINGHAM_REASON[a.framingham.reason ?? ""] ??
                a.framingham.reason}
            </p>
          )}
        </section>

        <section
          aria-labelledby="dm-title"
          className={`${CARD} col-span-2 md:col-span-1`}
        >
          <h2 id="dm-title" className="text-sm font-semibold">
            Kemungkinan diabetes
          </h2>
          <p className="text-xs text-muted-foreground">
            Perkiraan dari profil dan data harian Anda
          </p>
          {a ? (
            <>
              <p className="mt-4 flex items-baseline gap-2">
                <span className="text-3xl font-bold">
                  {BAND_LABEL[a.diabetes.band]}
                </span>
                <span className="text-sm text-muted-foreground tabular-nums">
                  {fmt(a.diabetes.prob * 100, 0)}%
                </span>
              </p>
              <ul className="mt-3 flex flex-col gap-1 text-xs">
                {a.diabetes.top_factors.map((f) => (
                  <li key={f.feature} className="flex items-center gap-1.5">
                    {f.direction === "increase" ? (
                      <ArrowUpRight
                        aria-hidden
                        className="size-3.5 text-destructive"
                      />
                    ) : (
                      <ArrowDownRight
                        aria-hidden
                        className="size-3.5 text-chart-2"
                      />
                    )}
                    {featureText(f)}{" "}
                    {f.direction === "increase" ? "menaikkan" : "menurunkan"}{" "}
                    risiko
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted-foreground">
                Data survei self-report AS. Indikasi skrining dini, bukan
                diagnosis.
              </p>
            </>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">Belum dinilai.</p>
          )}
        </section>

        <section
          aria-labelledby="flags-title"
          className={`${CARD} col-span-2 xl:col-span-4`}
        >
          <h2 id="flags-title" className="text-sm font-semibold">
            Yang perlu diperhatikan
          </h2>
          {!a ? (
            <p className="mt-3 text-sm text-muted-foreground">Belum dinilai.</p>
          ) : a.flags.length === 0 ? (
            <p className="mt-3 text-sm">
              Dari data saat ini, tidak ada hal yang perlu dikhawatirkan.
            </p>
          ) : (
            <ul className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
              {a.flags.map((f) => (
                <li
                  key={f.code}
                  className={`rounded-xl border px-3 py-2 text-sm ${SEVERITY_CLASS[f.severity]}`}
                >
                  <span className="font-semibold">
                    {FLAG_LABEL[f.code] ?? f.code}
                  </span>
                  <span className="block text-xs">
                    {String(f.value)} · batas {f.threshold}
                    {f.stale && " · data lama"}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-labelledby="trend-heading" className="mt-8">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 id="trend-heading" className="text-lg font-bold tracking-tight">
            Tren {days} hari
          </h2>
          <div
            role="group"
            aria-label="Rentang hari"
            className="flex gap-1 rounded-xl bg-muted p-1"
          >
            {([7, 30] as const).map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={days === d}
                onClick={() => setDays(d)}
                className="min-h-10 rounded-lg px-4 text-sm font-medium text-muted-foreground transition-colors duration-150 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring aria-pressed:bg-card aria-pressed:text-primary aria-pressed:shadow-card"
              >
                {d} hari
              </button>
            ))}
          </div>
        </div>
        {data.chart.series.length === 0 ? (
          <p className={`${CARD} text-sm text-muted-foreground`}>
            Belum ada data pada rentang ini.{" "}
            <Link
              href="/chat?form=1"
              className="font-medium text-primary underline"
            >
              Catat hari ini
            </Link>
          </p>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.chart.series.map((s) => (
              <TrendChart
                key={s}
                metric={s}
                data={data.chart.data}
                summary={
                  m[s]?.mean != null ? `rata-rata ${fmt(m[s].mean)}` : undefined
                }
              />
            ))}
          </div>
        )}
      </section>

      <div className="mt-8 grid gap-4 xl:grid-cols-3">
        <section
          aria-labelledby="plan-title"
          className={`${CARD} xl:col-span-2`}
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 id="plan-title" className="text-lg font-bold tracking-tight">
              Rencana aktif
            </h2>
            <span className="text-xs text-muted-foreground">
              {data.plan
                ? `Mulai ${data.plan.starts_on}`
                : "Belum ada rencana aktif"}
            </span>
          </div>
          {data.plan ? (
            <ol className="mt-4 grid gap-3 md:grid-cols-2">
              {data.plan.content.weeks.map((w, i) => (
                <li key={w.range} className="rounded-xl bg-muted/60 p-4">
                  <p className="flex items-center gap-2 text-sm font-semibold">
                    <span className="inline-flex size-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                      {i + 1}
                    </span>
                    {w.range}
                  </p>
                  {w.targets.length > 0 && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Target:{" "}
                      {w.targets
                        .map((t) => {
                          const pct = m[t.metric]?.adherence_pct;
                          return `${METRIC_LABEL[t.metric] ?? t.metric} ${fmt(t.target, 1)}${pct != null ? ` (kepatuhan ${fmt(pct, 0)}%)` : ""}`;
                        })
                        .join(" · ")}
                    </p>
                  )}
                  <ul className="mt-2 flex list-disc flex-col gap-1 pl-4 text-sm">
                    {w.actions.map((act) => (
                      <li key={act.text}>
                        {act.text}{" "}
                        <span className="text-xs text-muted-foreground">
                          [{act.citations.join(", ")}]
                        </span>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">
              Rencana dibuat otomatis setelah check-in lengkap.
            </p>
          )}
        </section>
        <section aria-labelledby="rf-title" className={CARD}>
          <h2
            id="rf-title"
            className="flex items-center gap-2 text-lg font-bold tracking-tight"
          >
            <ShieldAlert aria-hidden className="size-5 text-destructive" />{" "}
            Riwayat tanda bahaya
          </h2>
          {data.red_flags.length === 0 ? (
            <p className="mt-3 text-sm text-muted-foreground">Tidak ada.</p>
          ) : (
            <ul className="mt-3 flex flex-col gap-2 text-sm">
              {data.red_flags.map((r) => (
                <li
                  key={r.created_at + r.code}
                  className="rounded-xl border border-destructive/30 bg-destructive/5 px-3 py-2"
                >
                  <span className="font-semibold">
                    {RED_FLAG_LABEL[r.code] ?? r.code}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {new Date(r.created_at).toLocaleString("id-ID")}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
      <p className="mt-8 text-center text-xs text-muted-foreground">
        Hasil bukan diagnosis medis. Untuk keadaan darurat, hubungi 119.
      </p>
    </main>
  );
}

export default function DashboardPage() {
  return (
    <AppShell
      title="Dashboard"
      subtitle="Ringkasan risiko, tren, dan rencana Anda"
    >
      {(user) => <DashboardContent user={user} />}
    </AppShell>
  );
}
