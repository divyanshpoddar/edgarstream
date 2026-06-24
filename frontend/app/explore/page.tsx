"use client";

import { useEffect, useState, useRef } from "react";
import FinancialCard from "@/components/FinancialCard";
import { api } from "@/lib/api";
import type { FinancialStatement } from "@/lib/types";

const SUGGESTIONS = ["Apple", "Microsoft", "Alphabet", "Amazon", "ExxonMobil", "Walmart", "JPMorgan"];

export default function ExplorePage() {
  const [query, setQuery] = useState("");
  const [committed, setCommitted] = useState("");
  const [results, setResults] = useState<FinancialStatement[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function search(q: string) {
    setCommitted(q);
    setSearched(true);
    setLoading(true);
    api
      .financials({ company: q || undefined, limit: 30 })
      .then((res) =>
        setResults(
          res.data.filter(
            (s: import("@/lib/types").FinancialStatement) =>
              s.total_assets != null ||
              s.total_liabilities != null ||
              s.revenues != null ||
              s.net_income != null
          )
        )
      )
      .catch(() => setResults([]))
      .finally(() => setLoading(false));
  }

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value;
    setQuery(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => search(val), 400);
  }

  // Load all on mount so the page isn't blank
  useEffect(() => {
    search("");
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Financial Explorer</h1>
        <p className="text-muted text-sm">
          Search any company to see extracted XBRL financial data with tag provenance.
        </p>
      </div>

      {/* Search */}
      <div className="mb-3">
        <div className="relative max-w-md">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted text-sm">⌕</span>
          <input
            type="text"
            placeholder="Search company (e.g. Apple, JPMorgan)…"
            value={query}
            onChange={handleInput}
            onKeyDown={(e) => e.key === "Enter" && search(query)}
            className="w-full pl-8 pr-4 py-2.5 bg-surface border border-border rounded-md text-sm text-text placeholder-muted focus:outline-none focus:border-blue transition-colors"
          />
        </div>
      </div>

      {/* Quick suggestion chips */}
      <div className="flex flex-wrap gap-2 mb-8">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => { setQuery(s); search(s); }}
            className="px-3 py-1 text-xs border border-border rounded-full text-muted hover:text-text hover:border-muted transition-colors"
          >
            {s}
          </button>
        ))}
      </div>

      {/* Results */}
      {loading && (
        <div className="grid gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="bg-surface border border-border rounded-lg h-20 animate-pulse" />
          ))}
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="text-center py-16">
          <p className="text-3xl mb-3">🔍</p>
          <p className="text-text font-medium">No results found</p>
          <p className="text-muted text-sm mt-1">
            {committed
              ? `No financial data for "${committed}" yet. It will appear once a 10-K or 10-Q is processed.`
              : "The pipeline is listening — financial data will appear once the worker processes its first 10-K or 10-Q."}
          </p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <>
          <p className="text-xs text-muted mb-4">
            {results.length} result{results.length !== 1 ? "s" : ""}
            {committed ? ` for "${committed}"` : " — all companies"}
            {" "}· Click a card to expand financials
          </p>
          <div className="grid gap-3">
            {results.map((stmt) => (
              <FinancialCard key={stmt.accession_number} stmt={stmt} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
