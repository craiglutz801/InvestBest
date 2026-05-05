import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InvestBest — Paper Trading",
  description: "Hourly paper-trading agent with auditable decisions",
  icons: { icon: "/favicon.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background font-sans text-foreground antialiased">
        {children}
      </body>
    </html>
  );
}
