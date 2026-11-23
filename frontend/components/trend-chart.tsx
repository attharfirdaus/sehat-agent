"use client";

import { useId } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { METRIC_LABEL } from "@/lib/labels";

/** Satu chart per metrik (skala langkah vs jam tidur berbeda jauh). Area fill 20% (ui-ux-pro-max
 *  "Trend Over Time"); judul + ringkasan teks supaya tidak bergantung pada warna. */
export function TrendChart({
  metric,
  data,
  summary,
}: {
  metric: string;
  data: Record<string, number | string | null>[];
  summary?: string;
}) {
  const gradientId = useId();
  const points = data.filter((d) => d[metric] != null);
  const label = METRIC_LABEL[metric] ?? metric;
  return (
    <figure className="rounded-2xl bg-card p-4 shadow-card ring-1 ring-border/70">
      <figcaption className="mb-3 flex items-baseline justify-between gap-2">
        <span className="text-sm font-semibold">{label}</span>
        {summary && <span className="text-xs text-muted-foreground">{summary}</span>}
      </figcaption>
      <div className="h-40" role="img" aria-label={`Grafik ${label}, ${points.length} hari tercatat`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points} margin={{ top: 4, right: 4, bottom: 0, left: -16 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-chart-1)" stopOpacity={0.25} />
                <stop offset="100%" stopColor="var(--color-chart-1)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => d.slice(8, 10) + "/" + d.slice(5, 7)}
              fontSize={11}
              tickLine={false}
              axisLine={false}
            />
            <YAxis fontSize={11} domain={["auto", "auto"]} tickLine={false} axisLine={false} width={44} />
            <Tooltip
              labelFormatter={(d) => String(d)}
              contentStyle={{ borderRadius: 12, border: "1px solid var(--color-border)", fontSize: 12 }}
            />
            <Area
              type="monotone"
              dataKey={metric}
              name={label}
              stroke="var(--color-chart-1)"
              strokeWidth={2.5}
              fill={`url(#${gradientId})`}
              dot={{ r: 3, fill: "var(--color-chart-1)" }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
