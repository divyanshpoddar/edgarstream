"use client";

import { useState } from "react";
import FilingBadge from "./FilingBadge";
import { formatCurrency, formatDate } from "@/lib/utils";
import type { FinancialStatement } from "@/lib/types";

interface Props {
  stmt: FinancialStatement;
}

const METRICS = [
  { key: "total_assets",      label: "Total Assets",      field: "Assets" },
  { key: "total_liabilities", label: "Total Liabilities", field: "Liabilities" },
  { key: "revenues",          label: "Revenues",          field: "Revenues" },
  { key: "net_income",        label: "Net Income",        field: "NetIncomeLoss" },
] as const;

export default function FinancialCard({ stmt }: Props) {
  const [open, setOpen] = useState(false);

  const assets = stmt.total_assets ?? 0;
  const liabilities = stmt.total_liabilities ?? 0;
  const balanceOk = assets > 0 && liabilities > 0 && assets >= liabilities;

  return (
    <div className="bg-surface border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left p-4 hover:bg-surface-2 transition-colors flex items-center justify-between gap-4"
      >
        {/* Left: name + badge + date */}
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-text truncate">{stmt.company_name}</p>
          <div className="flex items-center gap-2 mt-1">
            {stmt.form_type && <FilingBadge type={stmt.form_type} />}
            <span className="text-xs text-muted">{formatDate(stmt.filing_date)}</span>
          </div>
        </div>

        {/* Right: 3 fixed-width metric columns */}
        <div className="hidden sm:flex items-center gap-6 shrink-0">
          {(
            [
              { label: "Assets",     value: stmt.total_assets },
              { label: "Revenue",    value: stmt.revenues },
              { label: "Net Income", value: stmt.net_income },
            ] as const
          ).map(({ label, value }) => (
            <div key={label} className="text-right w-24">
              <p className="text-xs text-muted">{label}</p>
              <p className={`text-sm font-mono font-semibold ${value != null ? "text-blue" : "text-muted/40"}`}>
                {formatCurrency(value)}
              </p>
            </div>
          ))}
        </div>

        {/* Mobile: just assets */}
        <div className="sm:hidden text-right shrink-0">
          <p className="text-xs text-muted">Assets</p>
          <p className="text-sm font-mono font-semibold text-blue">
            {formatCurrency(stmt.total_assets)}
          </p>
        </div>

        <span className="text-muted text-lg shrink-0">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-border">
          {/* Financial metrics grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-px bg-border">
            {METRICS.map(({ key, label, field }) => {
              const value = stmt[key as keyof FinancialStatement] as number | null;
              const tag = stmt.tag_provenance[field];
              return (
                <div key={key} className="bg-surface p-4">
                  <p className="text-xs text-muted mb-1">{label}</p>
                  <p className="text-lg font-bold text-text font-mono">
                    {formatCurrency(value)}
                  </p>
                  {tag && (
                    <p
                      title={tag}
                      className="text-[10px] text-muted/70 font-mono mt-1 truncate"
                    >
                      {tag}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Balance sheet identity check */}
          <div className="px-4 py-3 flex items-center justify-between flex-wrap gap-3 text-xs">
            <span className={`font-medium ${balanceOk ? "text-green" : "text-muted"}`}>
              {balanceOk
                ? "✓ Balance sheet: Assets ≥ Liabilities"
                : "Balance sheet check unavailable"}
            </span>
            <div className="flex items-center gap-3">
              {stmt.source_xbrl_url && (
                <a
                  href={stmt.source_xbrl_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-blue hover:underline"
                >
                  View XBRL source ↗
                </a>
              )}
              <span className="text-muted font-mono">{stmt.accession_number}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
