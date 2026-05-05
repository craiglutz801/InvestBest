"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/diagnostics", label: "Diagnostics" },
  { href: "/holdings", label: "Holdings" },
  { href: "/universe", label: "Universe" },
  { href: "/trades", label: "Trades" },
  { href: "/decisions", label: "Decisions" },
  { href: "/settings", label: "Settings" },
];

export function AppNav() {
  const path = usePathname();
  return (
    <header className="border-b border-border bg-card/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link href="/dashboard" className="font-semibold tracking-tight text-foreground">
          InvestBest
        </Link>
        <nav className="flex flex-wrap items-center gap-1 text-sm">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={cn(
                "rounded-md px-2.5 py-1.5 transition-colors hover:bg-muted",
                path === l.href ? "bg-muted font-medium" : "text-muted-foreground",
              )}
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>
    </header>
  );
}
