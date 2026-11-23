"use client";

import {
  HeartPulse,
  LayoutDashboard,
  LogOut,
  MessageCircle,
  Settings,
  Stethoscope,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { User } from "@/lib/types";

const ROLE_LABEL: Record<User["role"], string> = {
  user: "Pengguna",
  clinician: "Tenaga medis",
  admin: "Admin",
};

export function BrandMark({ className = "size-9" }: { className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-flex shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-chart-2 text-primary-foreground shadow-card ${className}`}
    >
      <HeartPulse className="size-1/2" />
    </span>
  );
}

/** Kerangka halaman yang butuh login (redirect ke /login kalau belum login), selebar layar.
 *  Desktop (md+): sidebar kiri. Ponsel: header tipis + tab bar bawah (maks. 5 item). */
export function AppShell({
  children,
  roles,
  title,
  subtitle,
}: {
  children: (user: User) => React.ReactNode;
  roles?: User["role"][];
  title?: string;
  subtitle?: string;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  const allowed = roles?.join(","); // string stabil: array literal baru tiap render memicu fetch ulang
  useEffect(() => {
    api<User>("/auth/me").then(
      (u) =>
        allowed && !allowed.split(",").includes(u.role)
          ? router.replace("/chat")
          : setUser(u),
      (e) =>
        e instanceof ApiError && e.status === 401 && router.replace("/login"),
    );
  }, [router, allowed]);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }

  const links = [
    { href: "/chat", label: "Chat", icon: MessageCircle },
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/settings", label: "Pengaturan", icon: Settings },
    ...(user && user.role !== "user"
      ? [{ href: "/clinician", label: "Clinician", icon: Stethoscope }]
      : []),
  ];

  return (
    <div className="flex h-dvh w-full">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-card md:flex">
        <div className="flex items-center gap-3 px-5 py-5">
          <BrandMark />
          <div className="leading-tight">
            <p className="text-base font-bold tracking-tight">SehatAgent</p>
            <p className="text-xs text-muted-foreground">
              Teman hidup sehat harian
            </p>
          </div>
        </div>
        <nav
          aria-label="Navigasi utama"
          className="flex flex-1 flex-col gap-1 px-3"
        >
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className="group flex min-h-11 items-center gap-3 rounded-xl px-3 text-sm font-medium text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring aria-[current=page]:bg-secondary aria-[current=page]:text-primary"
            >
              <Icon aria-hidden className="size-5" />
              {label}
            </Link>
          ))}
        </nav>
        {user && (
          <div className="m-3 flex items-center gap-3 rounded-xl bg-muted p-3">
            <span
              aria-hidden
              className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground"
            >
              {user.name.slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1 leading-tight">
              <p className="truncate text-sm font-semibold">{user.name}</p>
              <p className="text-xs text-muted-foreground">
                {ROLE_LABEL[user.role]}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Keluar"
              onClick={logout}
            >
              <LogOut aria-hidden />
            </Button>
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border bg-card/90 px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] backdrop-blur md:hidden">
          <BrandMark className="size-8" />
          <span className="text-base font-bold tracking-tight">SehatAgent</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={logout}
            className="ml-auto"
          >
            <LogOut aria-hidden /> Keluar
          </Button>
        </header>
        {title && (
          <div className="border-b border-border/70 bg-card/60 px-4 py-4 md:px-8 md:py-5">
            <h1 className="text-xl font-bold tracking-tight md:text-2xl">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
            )}
          </div>
        )}
        {user ? (
          children(user)
        ) : (
          <p className="flex-1 p-4 text-sm text-muted-foreground md:px-8">
            Memuat…
          </p>
        )}
        <nav
          aria-label="Navigasi utama"
          className="grid border-t border-border bg-card pb-[env(safe-area-inset-bottom)] md:hidden"
          style={{
            gridTemplateColumns: `repeat(${links.length}, minmax(0, 1fr))`,
          }}
        >
          {links.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              aria-current={pathname === href ? "page" : undefined}
              className="flex min-h-14 flex-col items-center justify-center gap-0.5 text-xs leading-tight text-muted-foreground focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring aria-[current=page]:font-semibold aria-[current=page]:text-primary"
            >
              <Icon aria-hidden className="size-5" />
              {label}
            </Link>
          ))}
        </nav>
      </div>
    </div>
  );
}
