import type { Metadata } from "next";
import Navbar from "@/components/Navbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "EdgarStream — Real-time SEC Filings Pipeline",
  description:
    "Production-grade pipeline that monitors SEC EDGAR in real time, extracts structured XBRL financial data from 10-K, 10-Q, 13F, 8-K, and S-1 filings, and detects schema drift.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <main className="max-w-6xl mx-auto px-6 py-10">{children}</main>
        <footer className="border-t border-border mt-16">
          <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between text-xs text-muted">
            <span>EdgarStream — real-time SEC EDGAR pipeline</span>
            <div className="flex gap-4">
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/docs`}
                target="_blank"
                rel="noreferrer"
                className="hover:text-text transition-colors"
              >
                API docs ↗
              </a>
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/status`}
                target="_blank"
                rel="noreferrer"
                className="hover:text-text transition-colors"
              >
                Status ↗
              </a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
