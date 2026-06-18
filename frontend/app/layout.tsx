import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Freight Agreement Intelligence",
  description: "AI-powered freight agreement extraction & search — Mankind Pharma",
};

const NAV = [
  { href: "/upload", label: "Upload" },
  { href: "/search", label: "Search" },
  { href: "/compare", label: "Compare" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen">
          <header className="bg-brand text-white">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
              <Link href="/" className="text-lg font-semibold">
                Freight Intelligence
              </Link>
              <nav className="flex gap-6 text-sm">
                {NAV.map((n) => (
                  <Link key={n.href} href={n.href} className="hover:underline">
                    {n.label}
                  </Link>
                ))}
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </div>
      </body>
    </html>
  );
}
