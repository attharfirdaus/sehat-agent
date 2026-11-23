"use client";

import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { api } from "@/lib/api";
import { BAND_LABEL, SEVERITY_CLASS } from "@/lib/labels";
import type { PlanContent, ReviewItem } from "@/lib/types";

function ReviewDetail({ item, onDone }: { item: ReviewItem; onDone: () => void }) {
  const { plan, assessment } = item.payload;
  const [content, setContent] = useState<PlanContent>(plan.content);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const edited = JSON.stringify(content) !== JSON.stringify(plan.content);

  async function decide(decision: "approve" | "edit" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await api(`/clinician/reviews/${item.review_id}`, {
        method: "POST",
        body: { decision, note: note || null, edited_content: decision === "edit" ? content : null },
      });
      onDone();
    } catch {
      setError("Gagal menyimpan keputusan.");
      setBusy(false);
    }
  }

  function setAction(w: number, a: number, text: string) {
    setContent({
      weeks: content.weeks.map((week, i) =>
        i !== w ? week : { ...week, actions: week.actions.map((act, j) => (j === a ? { ...act, text } : act)) },
      ),
    });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          {item.user_name} · rencana #{plan.id}
        </CardTitle>
        <CardDescription>Diajukan {new Date(item.created_at).toLocaleString("id-ID")}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4 text-sm">
        <section aria-label="Assessment">
          <p className="font-medium">Assessment</p>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {assessment.flags.map((f) => (
              <li key={f.code} className={`rounded-md border px-2 py-0.5 text-xs ${SEVERITY_CLASS[f.severity]}`}>
                {f.code}: {String(f.value)}
              </li>
            ))}
          </ul>
          <p className="mt-2">
            Framingham:{" "}
            {assessment.framingham.applicable ? `${assessment.framingham.risk_10y_pct}%` : `tidak berlaku (${assessment.framingham.reason})`}
            {" · "}Diabetes: {BAND_LABEL[assessment.diabetes.band]} ({Math.round(assessment.diabetes.prob * 100)}%)
          </p>
        </section>
        <section aria-label="Draf rencana" className="flex flex-col gap-3">
          <p className="font-medium">Draf rencana (teks aksi bisa diedit)</p>
          {content.weeks.map((w, wi) => (
            <div key={wi} className="flex flex-col gap-1.5">
              <p className="text-xs font-medium">
                {w.range} · target {w.targets.map((t) => `${t.metric} ${t.target}`).join(", ") || "–"}
              </p>
              {w.actions.map((a, ai) => (
                <div key={ai}>
                  <Label htmlFor={`a-${wi}-${ai}`} className="sr-only">
                    Aksi {ai + 1} {w.range}
                  </Label>
                  <Textarea id={`a-${wi}-${ai}`} value={a.text} rows={2} onChange={(e) => setAction(wi, ai, e.target.value)} />
                  <p className="text-xs text-muted-foreground">Sitasi: {a.citations.join(", ")}</p>
                </div>
              ))}
            </div>
          ))}
        </section>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="note">Catatan untuk user (opsional)</Label>
          <Textarea id="note" value={note} rows={2} onChange={(e) => setNote(e.target.value)} />
        </div>
        {error && (
          <p role="alert" className="text-destructive">
            {error}
          </p>
        )}
        <div className="flex flex-wrap gap-2">
          <Button disabled={busy} onClick={() => decide(edited ? "edit" : "approve")}>
            {edited ? "Simpan editan dan setujui" : "Setujui"}
          </Button>
          <Button variant="destructive" disabled={busy} onClick={() => decide("reject")}>
            Tolak
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ClinicianContent() {
  const [queue, setQueue] = useState<ReviewItem[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const load = useCallback(() => {
    api<ReviewItem[]>("/clinician/queue").then((q) => {
      setQueue(q);
      setSelected(q[0]?.review_id ?? null);
    });
  }, []);
  useEffect(load, [load]);

  if (!queue) return <p className="p-4 text-sm text-muted-foreground">Memuat…</p>;
  const item = queue.find((q) => q.review_id === selected);
  return (
    <main className="grid flex-1 content-start gap-6 overflow-y-auto px-4 py-6 md:px-8 lg:grid-cols-[18rem_1fr]">
      <nav aria-label="Antrian review">
        <h2 className="mb-2 text-base font-semibold">Antrian review ({queue.length})</h2>
        {queue.length === 0 && <p className="text-sm text-muted-foreground">Tidak ada kasus yang menunggu.</p>}
        <ul className="flex flex-col gap-1">
          {queue.map((q) => (
            <li key={q.review_id}>
              <button
                type="button"
                aria-current={q.review_id === selected}
                onClick={() => setSelected(q.review_id)}
                className="w-full rounded-md px-2.5 py-2 text-left text-sm hover:bg-muted aria-[current=true]:bg-muted aria-[current=true]:font-medium focus-visible:outline-2 focus-visible:outline-ring"
              >
                {q.user_name}
                <span className="block text-xs text-muted-foreground">{new Date(q.created_at).toLocaleString("id-ID")}</span>
              </button>
            </li>
          ))}
        </ul>
      </nav>
      {item && <ReviewDetail key={item.review_id} item={item} onDone={load} />}
    </main>
  );
}

export default function ClinicianPage() {
  return (
    <AppShell roles={["clinician", "admin"]} title="Clinician" subtitle="Tinjau rencana untuk kasus berisiko tinggi">
      {() => <ClinicianContent />}
    </AppShell>
  );
}
