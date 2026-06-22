"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import MetricCard from "@/components/MetricCard";
import FilingsTable from "@/components/FilingsTable";
import LiveBadge from "@/components/LiveBadge";
import { api } from "@/lib/api";
import type { PipelineMetrics, Filing, VolumePoint } from "@/lib/types";

const VolumeChart = dynamic(() => import("@/components/VolumeChart"), { ssr: false });

export default function Home() {
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null);
  const [filings, setFilings] = useState<Filing[]>([]);
  const [volume, setVolume] = useState<VolumePoint[]>([]);
  const [driftCount, setDriftCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const [m, f, v, d] = await Promise.all([
        api.metrics(),
        api.filings({ limit: 5 }),
        api.volume(7),
        api.drift({ limit: 100 }),
      ]);
      setMetrics(m);
      setFilings(f.data);
      setVolume(v.data);
      setDriftCount(d.count);
    } catch {
      // API not yet reachable — leave state as empty
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {/* Hero */}
      <section className="mb-12">
        <div className="flex items-center gap-3 mb-4">
          <LiveBadge label="Pipeline active · updates every 30s" />
        </div>
        <h1 className="text-4xl font-bold tracking-tight mb-3">
          Edgar<span className="text-blue">Stream</span>
        </h1>
        <p className="text-muted text-lg max-w-2xl leading-relaxed">
          Real-time SEC EDGAR filings pipeline. Monitors RSS feeds every 30 seconds,
          extracts structured XBRL financial data from 10-K, 10-Q, 13F, 8-K, and S-1 filings,
          and detects schema drift automatically.
        </p>
        <div className="flex gap-3 mt-6">
          <Link
            href="/explore"
            className="px-4 py-2 bg-blue text-bg font-semibold rounded-md text-sm hover:bg-blue/90 transition-colors"
          >
            Explore financials →
          </Link>
          <Link
            href="/feed"
            className="px-4 py-2 bg-surface border border-border text-text rounded-md text-sm hover:bg-surface-2 transition-colors"
          >
            Live feed
          </Link>
        </div>
      </section>

      {/* KPI cards */}
      <section className="mb-10">
        <h2 className="text-xs text-muted uppercase tracking-widest mb-4 font-medium">
          Pipeline · Last 24 Hours
        </h2>
        {loading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-surface border border-border rounded-lg p-5 animate-pulse h-24" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <MetricCard
              label="Filings ingested"
              value={metrics?.total_filings_ingested ?? 0}
              sub="24-hour window"
              accent="green"
            />
            <MetricCard
              label="Avg latency"
              value={`${metrics?.pipeline_health.average_latency_ms ?? 0}ms`}
              sub="end-to-end"
              accent="blue"
            />
            <MetricCard
              label="Success rate"
              value={metrics?.pipeline_health.extraction_success_rate ?? "—"}
              sub="extraction accuracy"
              accent="purple"
            />
            <MetricCard
              label="Drift alerts"
              value={driftCount}
              sub="schema changes detected"
              accent="yellow"
            />
          </div>
        )}
      </section>

      {/* Volume chart */}
      <section className="mb-10">
        <h2 className="text-xs text-muted uppercase tracking-widest mb-4 font-medium">
          Filing Volume · Last 7 Days
        </h2>
        <div className="bg-surface border border-border rounded-lg p-6">
          <VolumeChart data={volume} />
        </div>
      </section>

      {/* Recent filings */}
      <section className="mb-10">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs text-muted uppercase tracking-widest font-medium">
            Recent Filings
          </h2>
          <Link href="/feed" className="text-xs text-blue hover:underline">
            View all →
          </Link>
        </div>
        <div className="bg-surface border border-border rounded-lg p-6">
          <FilingsTable filings={filings} loading={loading} compact />
        </div>
      </section>

      {/* Tech callouts */}
      <section>
        <h2 className="text-xs text-muted uppercase tracking-widest mb-4 font-medium">
          How It Works
        </h2>
        <div className="grid sm:grid-cols-3 gap-4">
          {[
            {
              title: "EDGAR RSS polling",
              desc: "Monitors the SEC EDGAR real-time feed every 30 seconds across all form types. Deduplicates via Redis seen-set.",
              color: "text-blue",
            },
            {
              title: "XBRL extraction",
              desc: "Uses Arelle to parse XBRL instance documents. Records the exact concept tag (e.g. RevenueFromContractWithCustomer) that produced each metric.",
              color: "text-green",
            },
            {
              title: "Schema drift detection",
              desc: "Checks every filing for missing or zero-valued XBRL tags. Alerts immediately when SEC changes its taxonomy.",
              color: "text-orange",
            },
          ].map(({ title, desc, color }) => (
            <div key={title} className="bg-surface border border-border rounded-lg p-5">
              <p className={`font-semibold mb-2 ${color}`}>{title}</p>
              <p className="text-muted text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}
