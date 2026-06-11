import Link from "next/link";
import type { ReactNode } from "react";

const nav = [
  { href: "/", label: "Dashboard" },
  { href: "/research", label: "Research" },
  { href: "/experiments", label: "Experiments" },
  { href: "/candidates", label: "Candidates" },
  { href: "/system", label: "System" },
  { href: "/chat", label: "Chat" },
];

export function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <div className="shell">
      <aside className="rail">
        <div className="brand">
          <div className="brand-mark">V2</div>
          <div>
            <div className="eyebrow">InvestBest</div>
            <div className="brand-name">Research-first trading</div>
          </div>
        </div>
        <div className="paper-lock">Paper trading hard lock</div>
        <nav className="nav">
          {nav.map((item) => (
            <Link key={item.href} href={item.href} className="nav-link">
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <main className="content">
        <header className="page-header">
          <div>
            <p className="eyebrow">InvestBest_V2</p>
            <h1>{title}</h1>
            <p className="subtitle">{subtitle}</p>
          </div>
          <div className="status-cluster">
            <div className="status-pill">Research-first</div>
            <div className="status-pill">Validation-gated</div>
            <div className="status-pill">No live capital</div>
          </div>
        </header>
        {children}
      </main>
    </div>
  );
}
