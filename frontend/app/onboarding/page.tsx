"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ProfileForm } from "@/components/profile-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import type { Profile } from "@/lib/types";

export default function OnboardingPage() {
  const router = useRouter();
  const [initial, setInitial] = useState<Profile | null | undefined>(undefined);

  useEffect(() => {
    api<Profile>("/profile").then(setInitial, (e) => {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setInitial(null);
    });
  }, [router]);

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-8">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Profil kesehatan</CardTitle>
          <CardDescription>
            Diisi sekali saja dan bisa diubah nanti di Pengaturan. Data harian (langkah, tidur, air)
            dicatat lewat chat, bukan di sini.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {initial !== undefined && (
            <ProfileForm
              initial={initial}
              requireConsent
              submitLabel="Simpan dan mulai"
              onSaved={() => router.push("/chat")}
            />
          )}
        </CardContent>
      </Card>
    </main>
  );
}
