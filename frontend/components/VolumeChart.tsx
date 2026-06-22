"use client";

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import type { VolumePoint } from "@/lib/types";

const FORM_COLORS: Record<string, string> = {
  "10-K":   "#58a6ff",
  "10-Q":   "#3fb950",
  "13F-HR": "#ffa657",
  "13F-NT": "#d29922",
  "8-K":    "#bc8cff",
  "S-1":    "#f85149",
  "S-1/A":  "#ff7b72",
};

interface Props {
  data: VolumePoint[];
}

export default function VolumeChart({ data }: Props) {
  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 text-muted text-sm">
        No filing data yet — pipeline is listening for SEC filings.
      </div>
    );
  }

  // Pivot: date → { date: string, "10-K": number, ... }
  type ChartRow = { date: string } & Record<string, number | string>;
  const dateMap = new Map<string, ChartRow>();
  const formTypes = new Set<string>();
  for (const pt of data) {
    formTypes.add(pt.form_type);
    if (!dateMap.has(pt.date)) dateMap.set(pt.date, { date: pt.date });
    const row = dateMap.get(pt.date)!;
    row[pt.form_type] = ((row[pt.form_type] as number) ?? 0) + pt.count;
  }
  const chartData = Array.from(dateMap.values()).sort((a, b) =>
    a.date.localeCompare(b.date)
  );
  const types = Array.from(formTypes);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={chartData} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "#8b949e", fontSize: 11 }}
          tickFormatter={(d: string) =>
            new Date(d).toLocaleDateString("en-US", { month: "short", day: "numeric" })
          }
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#8b949e", fontSize: 11 }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{ background: "#161b22", border: "1px solid #30363d", borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: "#e6edf3" }}
          itemStyle={{ color: "#8b949e" }}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, color: "#8b949e" }}
          iconType="circle"
          iconSize={8}
        />
        {types.map((ft) => (
          <Bar
            key={ft}
            dataKey={ft}
            stackId="a"
            fill={FORM_COLORS[ft] ?? "#8b949e"}
            radius={types.indexOf(ft) === types.length - 1 ? [3, 3, 0, 0] : [0, 0, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
