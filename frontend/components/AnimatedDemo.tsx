"use client";

import { useEffect, useState } from "react";

const FILINGS = [
  {
    company: "APPLE INC",
    form: "10-K",
    accession: "0001193125-24-320762",
    entries: "47 entries · 1 new",
    metrics: [
      { label: "Total Assets", value: "$364.9B" },
      { label: "Revenues",     value: "$391.0B" },
      { label: "Net Income",   value: "$93.7B"  },
    ],
    tag: "RevenueFromContractWithCustomerExcludingAssessedTax",
    latency: "843ms",
    formColor: "bg-[#1f3a5c] text-[#58a6ff]",
  },
  {
    company: "JPMORGAN CHASE & CO.",
    form: "10-Q",
    accession: "0000070858-24-000180",
    entries: "31 entries · 1 new",
    metrics: [
      { label: "Total Assets", value: "$3.9T"   },
      { label: "Net Revenue",  value: "$158.1B" },
      { label: "Net Income",   value: "$49.6B"  },
    ],
    tag: "InterestAndDividendIncomeOperating",
    latency: "1.1s",
    formColor: "bg-[#1a3a2a] text-[#3fb950]",
  },
  {
    company: "BLACKROCK INC",
    form: "13F-HR",
    accession: "0001086364-24-003948",
    entries: "12 entries · 1 new",
    metrics: [
      { label: "Holdings",    value: "4,291"  },
      { label: "AUM (est.)",  value: "$10.2T" },
      { label: "Top holding", value: "AAPL"   },
    ],
    tag: "infotable / nameOfIssuer",
    latency: "2.1s",
    formColor: "bg-[#2a1a4a] text-[#bc8cff]",
  },
];

// ms to spend in each stage: polling → detected → extracting → done
const STAGE_MS = [800, 1000, 1400, 3000];

export default function AnimatedDemo() {
  const [filingIdx, setFilingIdx] = useState(0);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    let id: ReturnType<typeof setTimeout>;

    function runStage(s: number) {
      setStage(s);
      id = setTimeout(() => {
        const next = (s + 1) % STAGE_MS.length;
        if (next === 0) setFilingIdx((i) => (i + 1) % FILINGS.length);
        runStage(next);
      }, STAGE_MS[s]);
    }

    runStage(0);
    return () => clearTimeout(id);
  }, []);

  const f = FILINGS[filingIdx];

  return (
    <div className="rounded-xl overflow-hidden border border-[#30363d] shadow-2xl text-[13px] font-mono bg-[#0d1117] select-none">
      {/* Window chrome */}
      <div className="flex items-center gap-1.5 px-4 py-3 bg-[#161b22] border-b border-[#30363d]">
        <span className="w-3 h-3 rounded-full bg-[#f85149]/60" />
        <span className="w-3 h-3 rounded-full bg-[#d29922]/60" />
        <span className="w-3 h-3 rounded-full bg-[#3fb950]/60" />
        <span className="mx-auto text-[11px] text-[#8b949e]">pipeline_worker.py</span>
        <span className="flex items-center gap-1.5 text-[10px] text-[#3fb950]">
          <span className="w-1.5 h-1.5 rounded-full bg-[#3fb950] animate-pulse inline-block" />
          LIVE
        </span>
      </div>

      {/* Log output */}
      <div className="px-5 py-5 space-y-1.5 min-h-[230px]">
        <Line c="#3fb950">✓&nbsp; Connected — Redis · Neon · Snowflake</Line>
        <Line c="#8b949e">→&nbsp; Polling SEC EDGAR Atom feed…</Line>

        {stage >= 1 && (
          <>
            <Line c="#8b949e">&nbsp;&nbsp;&nbsp;↳ {f.entries}</Line>
            <Line c="#58a6ff">↳&nbsp; {f.form} detected · {f.company}</Line>
            <Line c="#8b949e" dim>&nbsp;&nbsp;&nbsp;{f.accession}</Line>
          </>
        )}

        {stage >= 2 && (
          <Line c="#d29922">
            ↳&nbsp; {stage === 2
              ? "Extracting XBRL instance document…"
              : `XBRL parsed in ${f.latency}`}
          </Line>
        )}

        {stage >= 3 && (
          <>
            {f.metrics.map((m) => (
              <div key={m.label} className="leading-relaxed" style={{ color: "#e6edf3" }}>
                &nbsp;&nbsp;&nbsp;{m.label}:{" "}
                <span style={{ color: "#58a6ff" }}>{m.value}</span>
              </div>
            ))}
            <Line c="#8b949e" dim>&nbsp;&nbsp;&nbsp;tag: {f.tag}</Line>
            <Line c="#3fb950">✓&nbsp; Persisted → Neon · Snowflake</Line>
          </>
        )}
      </div>

      {/* Status bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#161b22] border-t border-[#30363d] text-[10px] text-[#8b949e]">
        <span>queue: 0 · success: 100%</span>
        <span className={`px-2 py-0.5 rounded font-bold text-[10px] ${f.formColor}`}>
          {f.form}
        </span>
      </div>
    </div>
  );
}

function Line({
  c,
  dim,
  children,
}: {
  c: string;
  dim?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`leading-relaxed ${dim ? "opacity-40" : ""}`}
      style={{ color: c }}
    >
      {children}
    </div>
  );
}
