"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import AnimatedDemo from "@/components/AnimatedDemo";
import { api } from "@/lib/api";

export default function LandingPage() {
  const [stats, setStats] = useState<{ filings: number; rate: string } | null>(null);

  useEffect(() => {
    api
      .metrics()
      .then((m) =>
        setStats({
          filings: m.total_filings_ingested,
          rate: m.pipeline_health.extraction_success_rate,
        })
      )
      .catch(() => {});
  }, []);

  return (
    <div className="-mx-6 -mt-10">

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section className="px-6 pt-16 pb-24 bg-gradient-to-b from-[#161b22] to-[#0d1117]">
        <div className="max-w-6xl mx-auto grid lg:grid-cols-2 gap-14 items-center">
          {/* Left */}
          <div>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-[#30363d] text-xs text-[#8b949e] mb-8">
              <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950] animate-pulse inline-block" />
              Pipeline active · polling every 30 min
            </div>
            <h1 className="text-5xl sm:text-6xl font-bold tracking-tight leading-[1.1] mb-6">
              Real-time financial<br />
              intelligence from<br />
              <span className="text-[#58a6ff]">SEC filings.</span>
            </h1>
            <p className="text-[#8b949e] text-lg leading-relaxed mb-10 max-w-lg">
              EdgarStream monitors the SEC EDGAR feed, extracts clean financial
              data from XBRL-tagged filings, and detects taxonomy changes
              automatically — so analysts and engineers don&apos;t have to.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link
                href="/dashboard"
                className="px-5 py-2.5 bg-[#58a6ff] text-[#0d1117] font-bold rounded-md text-sm hover:bg-[#58a6ff]/90 transition-colors"
              >
                Open Dashboard →
              </Link>
              <Link
                href="/explore"
                className="px-5 py-2.5 bg-[#161b22] border border-[#30363d] text-[#e6edf3] rounded-md text-sm hover:bg-[#1c2128] transition-colors"
              >
                Explore financials
              </Link>
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL ?? ""}/docs`}
                target="_blank"
                rel="noreferrer"
                className="px-5 py-2.5 bg-[#161b22] border border-[#30363d] text-[#8b949e] rounded-md text-sm hover:text-[#e6edf3] transition-colors"
              >
                API docs ↗
              </a>
            </div>
          </div>

          {/* Right: animated pipeline demo */}
          <div>
            <AnimatedDemo />
          </div>
        </div>
      </section>

      {/* ── Live stats strip ──────────────────────────────────────────── */}
      <section className="px-6 py-5 bg-[#161b22] border-y border-[#30363d]">
        <div className="max-w-6xl mx-auto flex flex-wrap gap-8">
          {[
            { label: "Form types ingested", value: "5" },
            { label: "Filings processed today", value: stats ? String(stats.filings) : "—" },
            { label: "Extraction success rate", value: stats?.rate ?? "—" },
            { label: "XBRL tags traced per filing", value: "4" },
          ].map(({ label, value }) => (
            <div key={label} className="flex items-center gap-2 text-sm text-[#8b949e]">
              <span className="font-mono font-bold text-[#e6edf3] text-base">{value}</span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Context: what is EDGAR ────────────────────────────────────── */}
      <section className="px-6 py-20 bg-[#0d1117]">
        <div className="max-w-6xl mx-auto">
          <p className="text-xs text-[#8b949e] uppercase tracking-widest mb-12 font-medium">
            Why this exists
          </p>
          <div className="grid sm:grid-cols-3 gap-10">
            {[
              {
                icon: "📋",
                title: "What is SEC EDGAR?",
                body: "Every US public company must file financial reports with the Securities and Exchange Commission. EDGAR is the public database hosting all of them — 10-K annual reports, 10-Q quarterly filings, 13F hedge fund holdings, 8-K event disclosures, and IPO prospectuses (S-1).",
              },
              {
                icon: "🔍",
                title: "The problem with raw XBRL",
                body: "Financial filings use XBRL — a structured markup format. But the taxonomy is inconsistent across companies: Apple calls revenue RevenueFromContractWithCustomerExcludingAssessedTax, ExxonMobil calls it Revenues, JPMorgan uses InterestAndDividendIncomeOperating. Normalising this at scale is hard.",
              },
              {
                icon: "⚡",
                title: "What EdgarStream does",
                body: "EdgarStream polls EDGAR every 30 minutes, routes each filing to the right parser, extracts standardised financial metrics with XBRL tag provenance, and stores them in a queryable REST API — so any number can be traced back to the exact taxonomy concept and source filing.",
              },
            ].map(({ icon, title, body }) => (
              <div key={title}>
                <div className="text-3xl mb-5">{icon}</div>
                <h3 className="font-semibold text-[#e6edf3] mb-3 text-base">{title}</h3>
                <p className="text-[#8b949e] text-sm leading-relaxed">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Pipeline steps ────────────────────────────────────────────── */}
      <section className="px-6 py-20 bg-[#0d1117] border-t border-[#30363d]">
        <div className="max-w-6xl mx-auto">
          <p className="text-xs text-[#8b949e] uppercase tracking-widest mb-3 font-medium">
            How it works
          </p>
          <h2 className="text-2xl font-bold text-[#e6edf3] mb-12">
            From raw filing to queryable data in seconds
          </h2>
          <div className="grid sm:grid-cols-5 gap-6">
            {[
              {
                step: "01",
                color: "#58a6ff",
                title: "RSS poll",
                desc: "Upstash monitors the EDGAR Atom feed every 30 min. New accession numbers are pushed to a Redis queue.",
              },
              {
                step: "02",
                color: "#3fb950",
                title: "Dedup",
                desc: "A Redis seen-set blocks duplicates. The same filing is never processed twice, even if the feed re-publishes it.",
              },
              {
                step: "03",
                color: "#d29922",
                title: "Extract",
                desc: "Arelle parses XBRL for 10-K / 10-Q. XML parsers handle 13F holdings. HTML heuristics cover 8-K and S-1.",
              },
              {
                step: "04",
                color: "#bc8cff",
                title: "Persist",
                desc: "Clean rows go to Neon PostgreSQL. A per-filing MERGE upsert syncs to Snowflake for analytics queries.",
              },
              {
                step: "05",
                color: "#ffa657",
                title: "Serve",
                desc: "FastAPI serves the data via REST. The Next.js dashboard queries it and auto-refreshes every 30 seconds.",
              },
            ].map(({ step, color, title, desc }) => (
              <div key={step}>
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm mb-4"
                  style={{ background: `${color}20`, color }}
                >
                  {step}
                </div>
                <p className="font-semibold text-[#e6edf3] mb-2 text-sm">{title}</p>
                <p className="text-[#8b949e] text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Feature cards ─────────────────────────────────────────────── */}
      <section className="px-6 py-20 bg-[#161b22] border-t border-[#30363d]">
        <div className="max-w-6xl mx-auto">
          <p className="text-xs text-[#8b949e] uppercase tracking-widest mb-12 font-medium">
            Engineering highlights
          </p>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {[
              {
                color: "#58a6ff",
                icon: "🔗",
                title: "XBRL tag provenance",
                desc: "Every metric records the exact XBRL concept that produced it. Any number is fully auditable back to the source filing.",
              },
              {
                color: "#3fb950",
                icon: "🔁",
                title: "Idempotent ingestion",
                desc: "Redis seen-set + DB upsert keyed on accession number. Re-processing the same filing is always a no-op.",
              },
              {
                color: "#d29922",
                icon: "📡",
                title: "Schema drift detection",
                desc: "Every extraction checks for missing or zero XBRL tags and alerts when SEC changes its taxonomy.",
              },
              {
                color: "#bc8cff",
                icon: "🏗️",
                title: "Dual worker design",
                desc: "Lightweight worker runs in prod. A Prefect-orchestrated version with per-task retries is ready for bank infrastructure.",
              },
            ].map(({ color, icon, title, desc }) => (
              <div
                key={title}
                className="bg-[#0d1117] border border-[#30363d] rounded-xl p-6 hover:border-[#58a6ff]/40 transition-colors"
              >
                <div className="text-2xl mb-4">{icon}</div>
                <p className="font-semibold mb-2 text-sm" style={{ color }}>
                  {title}
                </p>
                <p className="text-[#8b949e] text-xs leading-relaxed">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tech stack ────────────────────────────────────────────────── */}
      <section className="px-6 py-16 bg-[#0d1117] border-t border-[#30363d]">
        <div className="max-w-6xl mx-auto">
          <p className="text-xs text-[#8b949e] uppercase tracking-widest mb-8 font-medium">
            Stack
          </p>
          <div className="flex flex-wrap gap-3">
            {[
              "Python 3.12", "FastAPI", "Next.js 14", "Arelle (XBRL)",
              "Neon PostgreSQL", "Upstash Redis", "Snowflake", "Prometheus",
              "Vercel", "Render", "GitHub Actions CI",
            ].map((tech) => (
              <span
                key={tech}
                className="px-3 py-1.5 rounded-md border border-[#30363d] text-xs text-[#8b949e] bg-[#161b22] font-mono"
              >
                {tech}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ───────────────────────────────────────────────────────── */}
      <section className="px-6 py-24 bg-[#161b22] border-t border-[#30363d] text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-3xl font-bold text-[#e6edf3] mb-4">
            The pipeline is running right now.
          </h2>
          <p className="text-[#8b949e] mb-10 leading-relaxed">
            Open the dashboard to see real-time filings, search extracted financials
            with XBRL tag provenance, and explore schema drift alerts.
          </p>
          <div className="flex flex-wrap gap-4 justify-center">
            <Link
              href="/dashboard"
              className="px-7 py-3 bg-[#58a6ff] text-[#0d1117] font-bold rounded-md hover:bg-[#58a6ff]/90 transition-colors"
            >
              Open Dashboard →
            </Link>
            <Link
              href="/explore"
              className="px-7 py-3 bg-[#0d1117] border border-[#30363d] text-[#e6edf3] rounded-md hover:bg-[#161b22] transition-colors"
            >
              Explore financials
            </Link>
          </div>
        </div>
      </section>

    </div>
  );
}
