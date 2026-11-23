"use client";

import {
  ClipboardPen,
  HelpCircle,
  ImagePlus,
  LineChart,
  Loader2,
  Notebook,
  SendHorizontal,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useEffectEvent, useRef, useState } from "react";

import { AppShell, BrandMark } from "@/components/app-shell";
import {
  type CheckinBody,
  CheckinForm,
  summarize,
} from "@/components/checkin-form";
import { InterruptCard } from "@/components/interrupt-card";
import { RichText } from "@/components/rich-text";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api, streamChat } from "@/lib/api";
import { NODE_LABEL } from "@/lib/labels";
import type { ChatEvent, InterruptPayload } from "@/lib/types";

type History = {
  messages: Message[];
  pending: InterruptPayload | null;
  running: boolean;
};

type Message = { role: "user" | "assistant"; text: string; image?: string };

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

const SUGGESTIONS = [
  {
    icon: Notebook,
    title: "Catat aktivitas",
    text: "jalan 6rb langkah, tidur 6 jam, minum 2 liter, tidak merokok, tidak minum alkohol",
  },
  {
    icon: LineChart,
    title: "Tanya tren saya",
    text: "kenapa tidur saya memburuk minggu ini?",
  },
  {
    icon: HelpCircle,
    title: "Info kesehatan",
    text: "berapa menit olahraga yang disarankan per minggu?",
  },
];

function ChatContent() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [pending, setPending] = useState<InterruptPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const streaming = useRef(false);
  const abort = useRef<AbortController | null>(null);

  const [showDashboardLink, setShowDashboardLink] = useState(false);
  // /chat?form=1 (dari dashboard) langsung membuka form check-in. Aman membaca window di sini:
  // ChatContent baru dirender di klien setelah AppShell memuat user.
  const [showForm, setShowForm] = useState(
    () => new URLSearchParams(window.location.search).get("form") === "1",
  );

  // Giliran tetap berjalan di backend walau halaman ditinggal; saat kembali, sambung ulang.
  const reattach = useEffectEvent(() => void run("/chat/stream", undefined));

  useEffect(() => () => abort.current?.abort(), []); // tutup koneksi saat pindah halaman

  useEffect(() => {
    api("/profile").catch((e) => {
      if (e instanceof ApiError && e.status === 404)
        router.replace("/onboarding");
    });
    api<History>("/chat/history").then(
      (h) => {
        setMessages(h.messages);
        setPending(h.pending);
        if (h.running) reattach();
      },
      () => undefined,
    );
    // Buang ?form=1 supaya reload tidak membuka form lagi.
    if (window.location.search.includes("form=1")) router.replace("/chat");
  }, [router]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, status, pending, showForm]);

  function onEvent(e: ChatEvent) {
    switch (e.event) {
      case "node_start":
        setStatus(NODE_LABEL[e.data.node] ?? null);
        break;
      case "token":
        if (streaming.current) {
          setMessages((m) => [
            ...m.slice(0, -1),
            { role: "assistant", text: m.at(-1)!.text + e.data.text },
          ]);
        } else {
          streaming.current = true; // pesan asisten baru, token berikutnya ditempel ke sini
          setMessages((m) => [...m, { role: "assistant", text: e.data.text }]);
        }
        break;
      case "interrupt": {
        const payload = e.data;
        setPending(payload);
        if (payload.type === "clarify") {
          const question = payload.question;
          setMessages((m) => [...m, { role: "assistant", text: question }]);
        }
        break;
      }
      case "chart":
        setShowDashboardLink(true);
        break;
      case "final":
        setMessages((m) =>
          streaming.current
            ? [...m.slice(0, -1), { role: "assistant", text: e.data.text }]
            : [...m, { role: "assistant", text: e.data.text }],
        );
        break;
      case "error":
        setError("Terjadi kesalahan saat memproses. Coba lagi.");
        break;
    }
  }

  async function run(path: string, body: unknown) {
    setBusy(true);
    setError(null);
    setShowDashboardLink(false);
    streaming.current = false;
    abort.current = new AbortController();
    try {
      await streamChat(path, body, onEvent, abort.current.signal);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return; // halaman ditinggal
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else if (
        e instanceof ApiError &&
        e.status === 409 &&
        body === undefined
      ) {
        // Giliran sudah selesai sebelum sempat tersambung: ambil hasilnya dari riwayat.
        const h = await api<History>("/chat/history").catch(() => null);
        if (h) {
          setMessages(h.messages);
          setPending(h.pending);
        }
      } else if (e instanceof ApiError && e.status === 409)
        setError("Pesan sebelumnya masih diproses. Tunggu sebentar.");
      else setError("Tidak bisa terhubung ke server. Coba lagi.");
    } finally {
      setBusy(false);
      setStatus(null);
    }
  }

  async function send(e?: React.FormEvent) {
    e?.preventDefault();
    const text = draft.trim();
    if ((!text && !image) || busy) return;
    setMessages((m) => [
      ...m,
      { role: "user", text, image: image ?? undefined },
    ]);
    setDraft("");
    setImage(null);
    setPending(null); // jawaban clarify dikirim sebagai pesan; interrupt lain ditinggalkan
    await run("/chat", {
      message: text,
      image_b64: image?.split(",")[1] ?? null,
    });
  }

  async function submitCheckin(body: CheckinBody) {
    setShowForm(false);
    setPending(null); // form memulai giliran baru; interrupt lama ditinggalkan
    setMessages((m) => [...m, { role: "user", text: summarize(body) }]);
    await run("/checkin", body);
  }

  async function resume(value: unknown) {
    setPending(null);
    await run("/chat/resume", { value });
  }

  function pickImage(file: File | undefined) {
    if (!file) return;
    if (file.size > MAX_IMAGE_BYTES) {
      setError("Ukuran foto maksimal 8 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => setImage(reader.result as string);
    reader.readAsDataURL(file);
  }

  return (
    <>
      <main
        className="flex-1 overflow-y-auto px-4 py-6 md:px-8"
        aria-live="polite"
      >
        <div className="mx-auto flex w-full max-w-4xl flex-col">
          {messages.length === 0 && (
            <div className="mt-6 flex flex-col items-center text-center md:mt-12">
              <BrandMark className="size-14" />
              <h2 className="mt-4 text-2xl font-bold tracking-tight">
                Halo! Ceritakan harimu.
              </h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Tulis dengan kalimat biasa, kirim foto makanan, atau tanyakan
                tren kesehatan Anda.
              </p>
              <div className="mt-6 grid w-full gap-3 sm:grid-cols-3">
                {SUGGESTIONS.map(({ icon: Icon, title, text }) => (
                  <button
                    key={title}
                    type="button"
                    onClick={() => setDraft(text)}
                    className="flex min-h-11 flex-col gap-1.5 rounded-2xl bg-card p-4 text-left shadow-card ring-1 ring-border/70 transition-shadow duration-150 hover:ring-primary/40 focus-visible:outline-2 focus-visible:outline-ring"
                  >
                    <span className="flex items-center gap-2 text-sm font-semibold">
                      <Icon aria-hidden className="size-4 text-primary" />{" "}
                      {title}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      &ldquo;{text}&rdquo;
                    </span>
                  </button>
                ))}
              </div>
              {!showForm && (
                <Button
                  variant="secondary"
                  size="lg"
                  className="mt-4"
                  onClick={() => setShowForm(true)}
                >
                  <ClipboardPen aria-hidden /> Lebih suka isian? Buka form
                  check-in
                </Button>
              )}
            </div>
          )}
          <ol className="flex flex-col gap-4">
            {messages.map((m, i) => (
              <li
                key={i}
                className={
                  m.role === "user"
                    ? "flex justify-end"
                    : "flex items-start gap-3"
                }
              >
                {m.role === "assistant" && (
                  <BrandMark className="mt-0.5 size-8" />
                )}
                <div
                  className={
                    m.role === "user"
                      ? "max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-base text-primary-foreground shadow-card sm:max-w-[70%] sm:text-sm"
                      : "max-w-[85%] rounded-2xl rounded-tl-md bg-card px-4 py-3 text-base shadow-card ring-1 ring-border/70 sm:max-w-[80%] sm:text-sm"
                  }
                >
                  {m.image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={m.image}
                      alt="Foto makanan yang dikirim"
                      className="mb-2 max-h-48 rounded-lg"
                    />
                  )}
                  {m.text && <RichText text={m.text} />}
                </div>
              </li>
            ))}
          </ol>
          {showForm && (
            <div className="mt-4 sm:pl-11">
              <CheckinForm
                onSubmit={submitCheckin}
                onClose={() => setShowForm(false)}
                disabled={busy}
              />
            </div>
          )}
          {pending && (
            <div className="mt-4 sm:pl-11">
              <InterruptCard
                payload={pending}
                onResume={resume}
                disabled={busy}
              />
            </div>
          )}
          {showDashboardLink && !busy && (
            <p className="mt-3 text-sm sm:pl-11">
              <Link
                href="/dashboard"
                className="font-medium text-primary underline"
              >
                Lihat grafik tren di dashboard
              </Link>
            </p>
          )}
          {status && (
            <p
              role="status"
              className="mt-4 flex items-center gap-2 text-sm text-muted-foreground sm:pl-11"
            >
              <Loader2
                aria-hidden
                className="size-4 motion-safe:animate-spin"
              />{" "}
              {status}
            </p>
          )}
          {error && (
            <p role="alert" className="mt-4 text-sm text-destructive sm:pl-11">
              {error}
            </p>
          )}
          <div ref={bottom} />
        </div>
      </main>

      <form onSubmit={send} className="px-4 pt-2 pb-3 md:px-8">
        <div className="mx-auto w-full max-w-4xl rounded-2xl bg-card p-2 shadow-card ring-1 ring-border/70 focus-within:ring-primary/50">
          {image && (
            <div className="mb-2 flex items-center gap-2 px-1 pt-1">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={image}
                alt="Pratinjau foto"
                className="h-14 rounded-lg"
              />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                aria-label="Hapus foto"
                onClick={() => setImage(null)}
              >
                <X aria-hidden />
              </Button>
            </div>
          )}
          <div className="flex items-end gap-2">
            <input
              ref={fileInput}
              type="file"
              accept="image/*"
              className="sr-only"
              tabIndex={-1}
              aria-hidden
              onChange={(e) => {
                pickImage(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              aria-label="Isi form check-in"
              aria-pressed={showForm}
              disabled={busy}
              onClick={() => setShowForm((v) => !v)}
              className="aria-pressed:bg-secondary aria-pressed:text-primary"
            >
              <ClipboardPen aria-hidden />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-lg"
              aria-label="Kirim foto makanan"
              disabled={busy}
              onClick={() => fileInput.current?.click()}
            >
              <ImagePlus aria-hidden />
            </Button>
            <Textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                // Enter saat komposisi IME mengonfirmasi teks, bukan mengirim pesan.
                if (
                  e.key === "Enter" &&
                  !e.shiftKey &&
                  !e.nativeEvent.isComposing
                ) {
                  e.preventDefault();
                  void send();
                }
              }}
              rows={1}
              maxLength={4000}
              aria-label="Pesan"
              placeholder={
                pending?.type === "clarify"
                  ? "Jawab pertanyaan di atas…"
                  : "Tulis pesan…"
              }
              className="max-h-40 min-h-11 flex-1 resize-none border-0 bg-transparent px-2 py-2.5 leading-6 shadow-none focus-visible:ring-0 md:py-3 md:leading-5 dark:bg-transparent"
            />
            <Button
              type="submit"
              size="icon-lg"
              aria-label="Kirim"
              disabled={busy || (!draft.trim() && !image)}
            >
              <SendHorizontal aria-hidden />
            </Button>
          </div>
        </div>
        <p className="mx-auto mt-2 max-w-4xl text-center text-xs text-muted-foreground">
          Hasil bukan diagnosis medis. Untuk keadaan darurat, hubungi 119.
        </p>
      </form>
    </>
  );
}

export default function ChatPage() {
  return <AppShell>{() => <ChatContent />}</AppShell>;
}
