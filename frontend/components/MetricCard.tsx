interface MetricCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "green" | "blue" | "orange" | "purple" | "yellow";
}

const ACCENT = {
  green:  "text-green",
  blue:   "text-blue",
  orange: "text-orange",
  purple: "text-purple",
  yellow: "text-yellow",
};

export default function MetricCard({ label, value, sub, accent = "blue" }: MetricCardProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-5">
      <p className="text-xs text-muted uppercase tracking-widest mb-2">{label}</p>
      <p className={`text-3xl font-bold leading-none ${ACCENT[accent]}`}>{value}</p>
      {sub && <p className="text-xs text-muted mt-2">{sub}</p>}
    </div>
  );
}
