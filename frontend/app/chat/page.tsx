"use client";

import { ImagePlus, SendHorizontal, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { InterruptCard } from "@/components/interrupt-card";
import { RichText } from "@/components/rich-text";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, api, streamChat } from "@/lib/api";
import { NODE_LABEL } from "@/lib/labels";
import type { ChatEvent, InterruptPayload } from "@/lib/types";

type History = { messages: Message[]; pending: InterruptPayload | null };

type Message = { role: "user" | "assistant"; text: string; image?: string };

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

const EXAMPLE = "jalan 6rb langkah, tidur 6 jam, minum 2 liter, tidak merokok, tidak minum alkohol";

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

  const [showDashboardLink, setShowDashboardLink] = useState(false);

  useEffect(() => {
    api("/profile").catch((e) => {
      if (e instanceof ApiError && e.status === 404) router.replace("/onboarding");
    });
    api<History>("/chat/history").then((h) => {
      setMessages(h.messages);
      setPending(h.pending);
    }, () => undefined);
  }, [router]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, status, pending]);

  function onEvent(e: ChatEvent) {
    switch (e.event) {
      case "node_start":
        setStatus(NODE_LABEL[e.data.node] ?? null);
        break;
      case "token":
        if (streaming.current) {
          setMessages((m) => [...m.slice(0, -1), { role: "assistant", text: m.at(-1)!.text + e.data.text }]);
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
    try {
      await streamChat(path, body, onEvent);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
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
    setMessages((m) => [...m, { role: "user", text, image: image ?? undefined }]);
    setDraft("");
    setImage(null);
    setPending(null); // jawaban clarify dikirim sebagai pesan; interrupt lain ditinggalkan
    await run("/chat", { message: text, image_b64: image?.split(",")[1] ?? null });
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

      <main className="flex-1 overflow-y-auto px-4 py-4" aria-live="polite">
        {messages.length === 0 && (
          <div className="mt-10 text-center text-sm text-muted-foreground">
            <p>Ceritakan aktivitas hari ini dengan kalimat biasa, misalnya:</p>
            <button
              type="button"
              onClick={() => setDraft(EXAMPLE)}
              className="mt-2 rounded-lg border border-border px-3 py-2 text-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
            >
              &ldquo;{EXAMPLE}&rdquo;
            </button>
            <p className="mt-3">Atau tanyakan tren Anda: &ldquo;kenapa tidur saya memburuk?&rdquo;</p>
            <p className="mt-3">
              Lebih suka isian?{" "}
              <Link href="/checkin" className="text-foreground underline">
                Isi form check-in harian
              </Link>
            </p>
          </div>
        )}
        <ol className="flex flex-col gap-3">
          {messages.map((m, i) => (
            <li key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
              <div
                className={
                  m.role === "user"
                    ? "max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-base sm:text-sm text-primary-foreground"
                    : "max-w-[85%] rounded-2xl rounded-bl-sm bg-card px-3.5 py-2 text-base ring-1 ring-border sm:text-sm"
                }
              >
                {m.image && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={m.image} alt="Foto makanan yang dikirim" className="mb-2 max-h-48 rounded-lg" />
                )}
                {m.text && <RichText text={m.text} />}
              </div>
            </li>
          ))}
        </ol>
        {pending && (
          <div className="mt-3">
            <InterruptCard payload={pending} onResume={resume} disabled={busy} />
          </div>
        )}
        {showDashboardLink && !busy && (
          <p className="mt-2 text-sm">
            <Link href="/dashboard" className="underline">
              Lihat grafik tren di dashboard
            </Link>
          </p>
        )}
        {status && (
          <p role="status" className="mt-3 motion-safe:animate-pulse text-sm text-muted-foreground">
            {status}
          </p>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {error}
          </p>
        )}
        <div ref={bottom} />
      </main>

      <form onSubmit={send} className="border-t border-border px-4 pt-3 pb-2">
        {image && (
          <div className="mb-2 flex items-center gap-2">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={image} alt="Pratinjau foto" className="h-14 rounded-md" />
            <Button type="button" variant="ghost" size="icon-sm" aria-label="Hapus foto" onClick={() => setImage(null)}>
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
            variant="outline"
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
              if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                void send();
              }
            }}
            rows={1}
            maxLength={4000}
            aria-label="Pesan"
            placeholder={pending?.type === "clarify" ? "Jawab pertanyaan di atas…" : "Tulis pesan…"}
            className="max-h-40 min-h-9 flex-1 resize-none"
          />
          <Button type="submit" size="icon-lg" aria-label="Kirim" disabled={busy || (!draft.trim() && !image)}>
            <SendHorizontal aria-hidden />
          </Button>
        </div>
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Hasil bukan diagnosis medis. Untuk keadaan darurat, hubungi 119.
        </p>
      </form>
    </>
  );
}

export default function ChatPage() {
  return <AppShell>{() => <ChatContent />}</AppShell>;
}
