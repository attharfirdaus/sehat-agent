"use client";

import { Activity, HeartPulse, ShieldCheck, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { BrandMark } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, api } from "@/lib/api";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const register = mode === "register";

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = Object.fromEntries(new FormData(e.currentTarget));
    setBusy(true);
    setError(null);
    try {
      await api(`/auth/${mode}`, { method: "POST", body: form });
      const hasProfile = await api("/profile").then(
        () => true,
        () => false,
      );
      router.push(hasProfile ? "/chat" : "/onboarding");
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? "Email sudah terdaftar."
          : err instanceof ApiError && err.status === 401
            ? "Email atau kata sandi salah."
            : "Periksa kembali isian Anda.",
      );
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-dvh flex-1 lg:grid-cols-2">
      <section
        aria-label="Tentang SehatAgent"
        className="relative hidden overflow-hidden bg-gradient-to-br from-primary to-foreground p-12 text-primary-foreground lg:flex lg:flex-col lg:justify-between"
      >
        <div className="flex items-center gap-3">
          <span
            aria-hidden
            className="inline-flex size-11 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/30"
          >
            <HeartPulse className="size-6" />
          </span>
          <span className="text-xl font-bold tracking-tight">SehatAgent</span>
        </div>
        <div>
          <h1 className="max-w-md text-4xl leading-tight font-bold tracking-tight">
            Catat kebiasaan, pahami risiko, perbaiki pelan-pelan.
          </h1>
          <ul className="mt-8 flex flex-col gap-4 text-sm">
            {[
              {
                icon: Activity,
                text: "Pantau langkah, tidur, air, dan tekanan darah dalam satu tempat.",
              },
              {
                icon: Sparkles,
                text: "Rencana 4 minggu yang disusun bertahap, setiap saran ada sumbernya.",
              },
              {
                icon: ShieldCheck,
                text: "AI berjalan lokal: data kesehatan Anda tidak dikirim ke layanan cloud.",
              },
            ].map(({ icon: Icon, text }) => (
              <li key={text} className="flex max-w-md items-start gap-3">
                <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-white/15">
                  <Icon aria-hidden className="size-4" />
                </span>
                <span className="pt-1.5 opacity-95">{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs opacity-80">Hasil bukan diagnosis medis.</p>
      </section>
      <div className="flex items-center justify-center px-4 py-10">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="mb-2 lg:hidden">
              <BrandMark className="size-10" />
            </div>
            <CardTitle className="text-xl font-bold tracking-tight">
              {register ? "Buat akun" : "Selamat datang kembali"}
            </CardTitle>
            <CardDescription>
              {register
                ? "Profil kesehatan hanya diisi sekali."
                : "Masuk untuk lanjut mencatat."}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={onSubmit} className="flex flex-col gap-4">
              {register && (
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="name">Nama</Label>
                  <Input
                    id="name"
                    name="name"
                    required
                    maxLength={100}
                    autoComplete="name"
                  />
                </div>
              )}
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password">Kata sandi</Label>
                <Input
                  id="password"
                  name="password"
                  type="password"
                  required
                  minLength={register ? 8 : undefined}
                  autoComplete={register ? "new-password" : "current-password"}
                />
                {register && (
                  <p className="text-xs text-muted-foreground">
                    Minimal 8 karakter.
                  </p>
                )}
              </div>
              {error && (
                <p role="alert" className="text-sm text-destructive">
                  {error}
                </p>
              )}
              <Button type="submit" size="lg" disabled={busy}>
                {busy ? "Memproses…" : register ? "Daftar" : "Masuk"}
              </Button>
              <p className="text-center text-sm text-muted-foreground">
                {register ? "Sudah punya akun? " : "Belum punya akun? "}
                <Link
                  href={register ? "/login" : "/register"}
                  className="text-foreground underline"
                >
                  {register ? "Masuk" : "Daftar"}
                </Link>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
