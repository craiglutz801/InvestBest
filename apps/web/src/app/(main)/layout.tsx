import { AppNav } from "@/components/AppNav";

export const dynamic = "force-dynamic";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AppNav />
      <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
    </>
  );
}
