"use client";

import { useEffect, useState, useCallback } from "react";
import FilingsTable from "@/components/FilingsTable";
import FilingBadge from "@/components/FilingBadge";
import LiveBadge from "@/components/LiveBadge";
import { api } from "@/lib/api";
import type { Filing } from "@/lib/types";

const FORM_TYPES = ["10-K", "10-Q", "13F-HR", "8-K", "S-1", "S-1/A"];

export default function FeedPage() {
  const [filings, setFilings] = useState<Filing[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activeForm, setActiveForm] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.filings({ form: activeForm ?? undefined, limit: 100 });
      setFilings(res.data);
      setLastRefresh(new Date());
    } catch {
      // keep stale data
    } finally {
      setLoading(false);
    }
  }, [activeForm]);

  useEffect(() => {
    setLoading(true);
    load();
  }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(load, 30_000);
    return () => clearInterval(t);
  }, [autoRefresh, load]);

  const filtered = search
    ? filings.filter((f) =>
        f.company_name.toLowerCase().includes(search.toLowerCase())
      )
    : filings;

  return (
    <>
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Live Filing Feed</h1>
        <p className="text-muted text-sm">
          Real-time stream of processed SEC EDGAR filings.{" "}
          {lastRefresh && (
            <span>Last updated: {lastRefresh.toLocaleTimeString()}</span>
          )}
        </p>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-3 mb-6 items-center">
        {/* Company search */}
        <input
          type="text"
          placeholder="Search company…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="px-3 py-2 bg-surface border border-border rounded-md text-sm text-text placeholder-muted focus:outline-none focus:border-blue w-52"
        />

        {/* Form type filter */}
        <div className="flex gap-2 flex-wrap">
          {FORM_TYPES.map((ft) => (
            <button
              key={ft}
              onClick={() => setActiveForm(activeForm === ft ? null : ft)}
              className={`transition-opacity ${activeForm && activeForm !== ft ? "opacity-40" : ""}`}
            >
              <FilingBadge type={ft} />
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md border transition-colors ${
              autoRefresh
                ? "border-green/30 text-green bg-green/10"
                : "border-border text-muted hover:border-muted"
            }`}
          >
            {autoRefresh ? <LiveBadge label="Auto-refresh on" /> : "Auto-refresh off"}
          </button>
          <button
            onClick={load}
            className="text-xs px-3 py-1.5 rounded-md border border-border text-muted hover:text-text hover:border-muted transition-colors"
          >
            Refresh now
          </button>
        </div>
      </div>

      {/* Summary line */}
      {!loading && (
        <p className="text-xs text-muted mb-4">
          Showing {filtered.length} filing{filtered.length !== 1 ? "s" : ""}
          {activeForm ? ` · filtered to ${activeForm}` : ""}
          {search ? ` · matching "${search}"` : ""}
        </p>
      )}

      <div className="bg-surface border border-border rounded-lg p-6">
        <FilingsTable filings={filtered} loading={loading} />
      </div>
    </>
  );
}
