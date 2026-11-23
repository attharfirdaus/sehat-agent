"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
      const hasProfile = await api("/profile").then(() => true, () => false);
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
    <main className="flex flex-1 items-center justify-center px-4 py-10">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-lg">{register ? "Daftar SehatAgent" : "Masuk"}</CardTitle>
          <CardDescription>
            {register ? "Profil hanya diisi sekali." : "Lanjutkan pencatatan harian Anda."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            {register && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="name">Nama</Label>
                <Input id="name" name="name" required maxLength={100} autoComplete="name" />
              </div>
            )}
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input id="email" name="email" type="email" required autoComplete="email" />
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
              {register && <p className="text-xs text-muted-foreground">Minimal 8 karakter.</p>}
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
              <Link href={register ? "/login" : "/register"} className="text-foreground underline">
                {register ? "Masuk" : "Daftar"}
              </Link>
            </p>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
