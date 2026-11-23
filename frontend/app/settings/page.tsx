"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { ProfileForm } from "@/components/profile-form";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import type { Profile, User } from "@/lib/types";

function DeleteAccount({ user }: { user: User }) {
  const router = useRouter();
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    try {
      await api("/account", { method: "DELETE" });
      router.replace("/register");
    } catch {
      setError("Gagal menghapus akun. Coba lagi.");
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Hapus akun dan semua data</CardTitle>
        <CardDescription>
          Menghapus profil, catatan harian, pengukuran, foto makanan, rencana, dan riwayat chat.
          Tidak bisa dibatalkan.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="confirm-email">Ketik email Anda ({user.email}) untuk konfirmasi</Label>
          <Input
            id="confirm-email"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="off"
          />
        </div>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button
          variant="destructive"
          disabled={busy || confirm.trim().toLowerCase() !== user.email}
          onClick={remove}
        >
          {busy ? "Menghapus…" : "Hapus akun permanen"}
        </Button>
      </CardContent>
    </Card>
  );
}

function SettingsContent({ user }: { user: User }) {
  const [profile, setProfile] = useState<Profile | null | undefined>(undefined);
  useEffect(() => {
    api<Profile>("/profile").then(setProfile, () => setProfile(null));
  }, []);

  return (
    <main className="flex-1 overflow-y-auto px-4 py-6">
      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Profil kesehatan</CardTitle>
            <CardDescription>Perubahan dipakai pada penilaian risiko berikutnya.</CardDescription>
          </CardHeader>
          <CardContent>
            {profile !== undefined && (
              <ProfileForm initial={profile} requireConsent={!profile} submitLabel="Simpan profil" />
            )}
          </CardContent>
        </Card>
        {/* TODO(PRD): "Hubungkan Telegram" dan toggle reminder menunggu M6 (dilewati, 2026-11-21). */}
        <DeleteAccount user={user} />
      </div>
    </main>
  );
}

export default function SettingsPage() {
  return <AppShell>{(user) => <SettingsContent user={user} />}</AppShell>;
}
