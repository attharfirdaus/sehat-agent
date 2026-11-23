"use client";

import { ClipboardPen, LayoutDashboard, LogOut, MessageCircle, Settings, Stethoscope } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { User } from "@/lib/types";

/** Header + navigasi untuk halaman yang butuh login. Redirect ke /login kalau belum login.
 *  Desktop: tab di header. Ponsel: tab bar bawah (maks. 5 item, ikon + label). */
export function AppShell({
  children,
  roles,
  wide = false,
}: {
  children: (user: User) => React.ReactNode;
  roles?: User["role"][];
  wide?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    api<User>("/auth/me").then(
      (u) => (roles && !roles.includes(u.role) ? router.replace("/chat") : setUser(u)),
      (e) => e instanceof ApiError && e.status === 401 && router.replace("/login"),
    );
  }, [router, roles]);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    router.replace("/login");
  }

  const links = [
    { href: "/chat", label: "Chat", icon: MessageCircle },
    { href: "/checkin", label: "Catat", icon: ClipboardPen },
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    { href: "/settings", label: "Pengaturan", icon: Settings },
    ...(user && user.role !== "user" ? [{ href: "/clinician", label: "Clinician", icon: Stethoscope }] : []),
  ];

  return (
    <div className={`mx-auto flex h-dvh w-full flex-col ${wide ? "max-w-5xl" : "max-w-3xl"}`}>
      <header className="flex items-center gap-2 border-b border-border bg-card/80 px-4 py-2 pt-[max(0.5rem,env(safe-area-inset-top))] backdrop-blur">
        <span className="mr-2 text-base font-semibold text-primary">SehatAgent</span>
        <nav aria-label="Navigasi utama" className="hidden flex-1 gap-1 sm:flex">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              aria-current={pathname === l.href ? "page" : undefined}
              className="inline-flex min-h-10 items-center rounded-lg px-3 text-sm whitespace-nowrap text-muted-foreground transition-colors duration-150 hover:bg-muted hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring aria-[current=page]:bg-secondary aria-[current=page]:font-medium aria-[current=page]:text-primary"
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <Button variant="ghost" size="sm" onClick={logout} className="ml-auto">
          <LogOut aria-hidden /> Keluar
        </Button>
      </header>
      {user ? children(user) : <p className="flex-1 p-4 text-sm text-muted-foreground">Memuat…</p>}
      <nav
        aria-label="Navigasi utama"
        className="grid border-t border-border bg-card pb-[env(safe-area-inset-bottom)] sm:hidden"
        style={{ gridTemplateColumns: `repeat(${links.length}, minmax(0, 1fr))` }}
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
  );
}
