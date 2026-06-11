import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InvestBest_V2",
  description: "Research-first successor to InvestBest",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
