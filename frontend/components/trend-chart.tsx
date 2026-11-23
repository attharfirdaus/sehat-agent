"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { METRIC_LABEL } from "@/lib/labels";

/** Satu chart per metrik: skala tiap metrik berbeda jauh (langkah vs jam tidur). */
export function TrendChart({
  metric,
  data,
}: {
  metric: string;
  data: Record<string, number | string | null>[];
}) {
  const points = data.filter((d) => d[metric] != null);
  return (
    <figure className="rounded-xl p-3 ring-1 ring-foreground/10">
      <figcaption className="mb-2 text-sm font-medium">{METRIC_LABEL[metric] ?? metric}</figcaption>
      <div className="h-36" role="img" aria-label={`Grafik ${METRIC_LABEL[metric] ?? metric}, ${points.length} hari tercatat`}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={points} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" tickFormatter={(d: string) => d.slice(5)} fontSize={11} />
            <YAxis fontSize={11} domain={["auto", "auto"]} />
            <Tooltip labelFormatter={(d) => String(d)} />
            <Line
              type="monotone"
              dataKey={metric}
              name={METRIC_LABEL[metric] ?? metric}
              stroke="var(--color-chart-1)"
              strokeWidth={2}
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
