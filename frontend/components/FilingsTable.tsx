"use client";

import FilingBadge from "./FilingBadge";
import { formatDate, formatLatency } from "@/lib/utils";
import type { Filing } from "@/lib/types";

interface Props {
  filings: Filing[];
  loading?: boolean;
  compact?: boolean;
}

export default function FilingsTable({ filings, loading, compact }: Props) {
  if (loading) {
    return <div className="text-muted text-sm py-8 text-center">Loading…</div>;
  }
  if (filings.length === 0) {
    return (
      <div className="text-muted text-sm py-10 text-center">
        No filings yet — the pipeline is listening for SEC EDGAR activity.
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
            {!compact && <th className="pb-3 text-left font-medium">Filed</th>}
            <th className="pb-3 text-left font-medium">Latency</th>
            {!compact && <th className="pb-3 text-left font-medium">Source</th>}
          </tr>
        </thead>
        <tbody>
          {filings.map((f) => (
            <tr
              key={f.accession_number}
              className="border-b border-border/50 hover:bg-surface-2 transition-colors"
            >
              <td className="py-3 pr-4 text-text font-medium max-w-[200px] truncate">
                {f.company_name}
              </td>
              <td className="py-3 pr-4">
                <FilingBadge type={f.form_type} />
              </td>
              {!compact && (
                <td className="py-3 pr-4 text-muted whitespace-nowrap">
                  {formatDate(f.filing_date)}
                </td>
              )}
              <td className="py-3 pr-4 text-muted font-mono text-xs">
                {formatLatency(f.latency_ms)}
              </td>
              {!compact && (
                <td className="py-3">
                  {f.document_url ? (
                    <a
                      href={f.document_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue hover:underline text-xs"
                    >
                      SEC ↗
                    </a>
                  ) : (
                    <span className="text-muted text-xs">—</span>
                  )}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
