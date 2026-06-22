"use client";

import FilingBadge from "./FilingBadge";
import { formatDate } from "@/lib/utils";
import type { DriftAlert } from "@/lib/types";

interface Props {
  alerts: DriftAlert[];
  loading?: boolean;
}

export default function DriftTable({ alerts, loading }: Props) {
  if (loading) return <div className="text-muted text-sm py-8 text-center">Loading…</div>;

  if (alerts.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-green text-4xl mb-3">✓</p>
        <p className="text-text font-medium">No drift detected</p>
        <p className="text-muted text-sm mt-1">
          All expected XBRL tags are present across recent filings.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-muted text-xs uppercase tracking-wider">
            <th className="pb-3 text-left font-medium">Company</th>
            <th className="pb-3 text-left font-medium">Form</th>
            <th className="pb-3 text-left font-medium">Missing Fields</th>
            <th className="pb-3 text-left font-medium">Detected</th>
            <th className="pb-3 text-left font-medium">Filing</th>
          </tr>
        </thead>
        <tbody>
          {alerts.map((a, i) => {
            let missing: string[] = [];
            try { missing = JSON.parse(a.missing_fields); } catch { missing = [a.missing_fields]; }

            return (
              <tr key={`${a.accession_number}-${i}`} className="border-b border-border/50">
                <td className="py-3 pr-4 font-medium text-text max-w-[180px] truncate">
                  {a.company_name}
                </td>
                <td className="py-3 pr-4">
                  <FilingBadge type={a.form_type} />
                </td>
                <td className="py-3 pr-4">
                  <div className="flex flex-wrap gap-1">
                    {missing.map((f) => (
                      <span
                        key={f}
                        className="px-1.5 py-0.5 text-[10px] font-mono bg-yellow/10 text-yellow border border-yellow/20 rounded"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="py-3 pr-4 text-muted text-xs whitespace-nowrap">
                  {formatDate(a.detected_at)}
                </td>
                <td className="py-3 text-xs font-mono text-muted">{a.accession_number}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
