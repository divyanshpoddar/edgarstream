"use client";

import { useEffect, useState } from "react";
import DriftTable from "@/components/DriftTable";
import LiveBadge from "@/components/LiveBadge";
import { api } from "@/lib/api";
import type { DriftAlert } from "@/lib/types";

export default function DriftPage() {
  const [alerts, setAlerts] = useState<DriftAlert[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    try {
      const res = await api.drift({ limit: 50 });
      setAlerts(res.data);
    } catch {
      // keep stale
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
      <div className="mb-8 flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold mb-1">Schema Drift Alerts</h1>
          <p className="text-muted text-sm max-w-xl">
            Fires when a filing is missing expected XBRL tags — a signal that the SEC has changed its taxonomy
            or a company filed non-standard XBRL.
          </p>
        </div>
        <LiveBadge label="Auto-refresh 30s" />
      </div>

      {/* How it works */}
      <div className="grid sm:grid-cols-3 gap-4 mb-8">
        {[
          {
            label: "10-K / 10-Q",
            expected: ["Assets", "Liabilities", "Revenues", "NetIncomeLoss"],
            color: "text-blue",
          },
          {
            label: "13F-HR",
            expected: ["issuer", "cusip", "value_usd_thousands", "shares"],
            color: "text-orange",
          },
          {
            label: "8-K",
            expected: ["summary", "event_type"],
            color: "text-purple",
          },
        ].map(({ label, expected, color }) => (
          <div key={label} className="bg-surface border border-border rounded-lg p-4">
            <p className={`text-xs font-semibold mb-2 ${color}`}>{label} — expected tags</p>
            <div className="flex flex-wrap gap-1">
              {expected.map((tag) => (
                <span key={tag} className="px-1.5 py-0.5 text-[10px] font-mono bg-surface-2 border border-border rounded text-muted">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Alerts */}
      <div className="bg-surface border border-border rounded-lg p-6">
        <DriftTable alerts={alerts} loading={loading} />
      </div>

      {!loading && alerts.length > 0 && (
        <p className="text-xs text-muted mt-4">
          Showing {alerts.length} most recent alert{alerts.length !== 1 ? "s" : ""}.
          Each alert is also emitted as a Prometheus counter{" "}
          <code className="font-mono text-muted/80">edgar_schema_drift_total</code>.
        </p>
      )}
    </>
  );
}
