"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DailyLogIn, FoodItem, InterruptPayload } from "@/lib/types";

type Resume = (value: unknown) => void;

const NUMBER_FIELDS = [
  { key: "steps", label: "Langkah", step: 1 },
  { key: "sleep_hours", label: "Tidur (jam)", step: 0.5 },
  { key: "water_l", label: "Air minum (liter)", step: 0.1 },
  { key: "calories_kcal", label: "Kalori (kkal)", step: 1 },
] as const;

const BOOL_FIELDS = [
  { key: "smoked", label: "Merokok" },
  { key: "alcohol", label: "Minum alkohol" },
] as const;

const KIND_LABEL: Record<string, string> = {
  systolic: "Sistolik",
  diastolic: "Diastolik",
  resting_hr: "Denyut istirahat",
  weight_kg: "Berat (kg)",
  cholesterol_total: "Kolesterol total",
};

const SELECT =
  "h-10 w-full rounded-lg border border-input bg-transparent px-3 text-base sm:text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30";

function ConfirmLog({ log, measurements, onResume, disabled }: {
  log: DailyLogIn;
  measurements: { kind: string; value: number }[];
  onResume: Resume;
  disabled: boolean;
}) {
  const [draft, setDraft] = useState(log);
  const changed = JSON.stringify(draft) !== JSON.stringify(log);
  return (
    <Card size="sm" className="max-w-md">
      <CardHeader>
        <CardTitle>Periksa catatan hari ini</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="grid grid-cols-2 gap-3">
          {NUMBER_FIELDS.map((f) => (
            <div key={f.key} className="flex flex-col gap-1">
              <Label htmlFor={`log-${f.key}`}>{f.label}</Label>
              <Input
                id={`log-${f.key}`}
                type="number"
                inputMode="decimal"
                min={0}
                step={f.step}
                value={draft[f.key] ?? ""}
                onChange={(e) =>
                  setDraft({ ...draft, [f.key]: e.target.value === "" ? null : Number(e.target.value) })
                }
              />
            </div>
          ))}
          {BOOL_FIELDS.map((f) => (
            <div key={f.key} className="flex flex-col gap-1">
              <Label htmlFor={`log-${f.key}`}>{f.label}</Label>
              <select
                id={`log-${f.key}`}
                className={SELECT}
                value={draft[f.key] === null ? "" : String(draft[f.key])}
                onChange={(e) =>
                  setDraft({ ...draft, [f.key]: e.target.value === "" ? null : e.target.value === "true" })
                }
              >
                <option value="">Belum diisi</option>
                <option value="false">Tidak</option>
                <option value="true">Ya</option>
              </select>
            </div>
          ))}
        </div>
        {measurements.length > 0 && (
          <ul className="text-sm text-muted-foreground">
            {measurements.map((m) => (
              <li key={m.kind}>
                {KIND_LABEL[m.kind] ?? m.kind}: {m.value}
              </li>
            ))}
          </ul>
        )}
        <Button
          disabled={disabled}
          onClick={() => onResume(changed ? { action: "edit", log: draft } : { action: "confirm" })}
        >
          {changed ? "Simpan perubahan" : "Simpan"}
        </Button>
      </CardContent>
    </Card>
  );
}

function ConfirmMeal({ items, caveats, onResume, disabled }: {
  items: FoodItem[];
  caveats: string[];
  onResume: Resume;
  disabled: boolean;
}) {
  const [keep, setKeep] = useState(items.map(() => true));
  const kept = items.filter((_, i) => keep[i]);
  const low = kept.reduce((s, i) => s + i.kcal_low, 0);
  const high = kept.reduce((s, i) => s + i.kcal_high, 0);
  return (
    <Card size="sm" className="max-w-md">
      <CardHeader>
        <CardTitle>Perkiraan makanan</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <ul className="flex flex-col gap-2">
          {items.map((item, i) => (
            <li key={`${item.name}-${i}`}>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  className="size-4 accent-primary"
                  checked={keep[i]}
                  onChange={() => setKeep(keep.map((k, j) => (j === i ? !k : k)))}
                />
                <span className="flex-1">
                  {item.name} <span className="text-muted-foreground">({item.portion})</span>
                </span>
                <span className="tabular-nums">
                  {item.kcal_low}–{item.kcal_high} kkal
                </span>
              </label>
            </li>
          ))}
        </ul>
        <p className="text-sm font-medium tabular-nums">
          Total: {low}–{high} kkal
        </p>
        {caveats.map((c) => (
          <p key={c} className="text-xs text-muted-foreground">
            {c}
          </p>
        ))}
        <div className="flex gap-2">
          <Button
            className="flex-1"
            disabled={disabled || kept.length === 0}
            onClick={() =>
              onResume(kept.length === items.length ? { action: "confirm" } : { action: "edit", items: kept })
            }
          >
            Simpan
          </Button>
          <Button variant="outline" disabled={disabled} onClick={() => onResume({ action: "cancel" })}>
            Batal
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function InterruptCard({ payload, onResume, disabled }: {
  payload: InterruptPayload;
  onResume: Resume;
  disabled: boolean;
}) {
  if (payload.type === "confirm_log")
    return (
      <ConfirmLog
        log={payload.log}
        measurements={payload.measurements}
        onResume={onResume}
        disabled={disabled}
      />
    );
  if (payload.type === "confirm_meal")
    return (
      <ConfirmMeal
        items={payload.estimate.items}
        caveats={payload.estimate.caveats}
        onResume={onResume}
        disabled={disabled}
      />
    );
  return null; // clarify: pertanyaan tampil sebagai pesan, jawabannya lewat kotak chat
}
