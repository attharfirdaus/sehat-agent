"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { TrendChart } from "@/components/trend-chart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";
import { BAND_LABEL, FRAMINGHAM_REASON, METRIC_LABEL, SEVERITY_CLASS } from "@/lib/labels";
import type { Dashboard } from "@/lib/types";

function fmt(n: number | null | undefined, digits = 1): string {
  return n == null ? "–" : Number(n.toFixed(digits)).toLocaleString("id-ID");
}

function DashboardContent() {
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

  if (error) return <p className="p-4 text-sm text-destructive">Gagal memuat dashboard.</p>;
  if (!data) return <p className="p-4 text-sm text-muted-foreground">Memuat…</p>;
  const a = data.assessment;

  return (
    <main className="flex-1 overflow-y-auto px-4 py-6">
      <div className="grid gap-4 md:grid-cols-3">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Faktor risiko</CardTitle>
            <CardDescription>
              {data.assessment_at
                ? `Penilaian ${new Date(data.assessment_at).toLocaleString("id-ID")}`
                : "Belum ada penilaian. Lakukan check-in lengkap lewat chat."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {a && a.flags.length === 0 && <p className="text-sm">Tidak ada faktor yang ditandai.</p>}
            <ul className="flex flex-col gap-1.5">
              {a?.flags.map((f) => (
                <li key={f.code} className={`rounded-md border px-2 py-1 text-xs ${SEVERITY_CLASS[f.severity]}`}>
                  <span className="font-medium">{f.code}</span>: {String(f.value)} (acuan {f.threshold})
                  {f.stale && " · data lama"}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle>Risiko kardiovaskular 10 tahun</CardTitle>
            <CardDescription>Framingham 2008 non-lab</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {!a ? (
              "–"
            ) : a.framingham.applicable ? (
              <>
                <p className="text-2xl font-semibold tabular-nums">{fmt(a.framingham.risk_10y_pct)}%</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Dikembangkan pada kohort AS; kalibrasi untuk Indonesia belum divalidasi.
                </p>
              </>
            ) : (
              <p>Tidak berlaku: {FRAMINGHAM_REASON[a.framingham.reason ?? ""] ?? a.framingham.reason}</p>
            )}
          </CardContent>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle>Indikasi risiko diabetes</CardTitle>
            <CardDescription>Model ML (CDC BRFSS 2015)</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {a ? (
              <>
                <p className="text-2xl font-semibold">
                  {BAND_LABEL[a.diabetes.band]}{" "}
                  <span className="text-base font-normal tabular-nums">({fmt(a.diabetes.prob * 100, 0)}%)</span>
                </p>
                <p className="mt-2 text-xs font-medium">Faktor paling berpengaruh</p>
                <ul className="text-xs">
                  {a.diabetes.top_factors.map((f) => (
                    <li key={f.feature}>
                      {f.feature} {f.direction === "increase" ? "menaikkan" : "menurunkan"} risiko
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted-foreground">
                  Data survei self-report AS, fitur biner. Indikasi skrining dini, bukan diagnosis.
                </p>
              </>
            ) : (
              "–"
            )}
          </CardContent>
        </Card>
      </div>

      <section aria-labelledby="trend-heading" className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 id="trend-heading" className="text-base font-semibold">
            Tren {days} hari
          </h2>
          <div role="group" aria-label="Rentang hari" className="flex gap-2">
            {([7, 30] as const).map((d) => (
              <button
                key={d}
                type="button"
                aria-pressed={days === d}
                onClick={() => setDays(d)}
                className="min-h-10 rounded-lg border border-border bg-card px-3.5 text-sm transition-colors duration-150 hover:bg-muted aria-pressed:bg-primary aria-pressed:text-primary-foreground focus-visible:outline-2 focus-visible:outline-ring"
              >
                {d} hari
              </button>
            ))}
          </div>
        </div>
        {data.chart.series.length === 0 ? (
          <p className="text-sm text-muted-foreground">Belum ada data pada rentang ini.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {data.chart.series.map((m) => (
              <TrendChart key={m} metric={m} data={data.chart.data} />
            ))}
          </div>
        )}
      </section>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <Card size="sm">
          <CardHeader>
            <CardTitle>Rencana aktif</CardTitle>
            <CardDescription>
              {data.plan ? `Mulai ${data.plan.starts_on}` : "Belum ada rencana aktif."}
            </CardDescription>
          </CardHeader>
          {data.plan && (
            <CardContent className="flex flex-col gap-3 text-sm">
              {data.plan.content.weeks.map((w) => (
                <div key={w.range}>
                  <p className="font-medium">{w.range}</p>
                  <ul className="list-disc pl-5">
                    {w.targets.map((t) => (
                      <li key={t.metric}>
                        Target {METRIC_LABEL[t.metric] ?? t.metric}: {fmt(t.target, 1)}
                        {data.trends.metrics[t.metric]?.adherence_pct != null &&
                          ` · kepatuhan ${fmt(data.trends.metrics[t.metric].adherence_pct, 0)}%`}
                      </li>
                    ))}
                    {w.actions.map((act) => (
                      <li key={act.text}>
                        {act.text} <span className="text-xs text-muted-foreground">[{act.citations.join(", ")}]</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </CardContent>
          )}
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardTitle>Riwayat tanda bahaya</CardTitle>
          </CardHeader>
          <CardContent className="text-sm">
            {data.red_flags.length === 0 ? (
              <p className="text-muted-foreground">Tidak ada.</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {data.red_flags.map((r) => (
                  <li key={r.created_at + r.code}>
                    <span className="font-medium">{r.code}</span> · {new Date(r.created_at).toLocaleString("id-ID")}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
      <p className="mt-6 text-center text-xs text-muted-foreground">
        Hasil bukan diagnosis medis. Untuk keadaan darurat, hubungi 119.
      </p>
    </main>
  );
}

export default function DashboardPage() {
  return <AppShell wide>{() => <DashboardContent />}</AppShell>;
}
