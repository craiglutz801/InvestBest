import { AppNav } from "@/components/AppNav";

export const dynamic = "force-dynamic";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs leading-relaxed text-muted-foreground">
        Research and paper trading only. Simulated results are not evidence of alpha, not a live track
        record, and not financial advice. No live broker or real-money orders.
      </footer>
    </>
  );
}
