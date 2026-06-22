const STYLES: Record<string, string> = {
  "10-K":   "bg-blue/10 text-blue border-blue/20",
  "10-Q":   "bg-green/10 text-green border-green/20",
  "13F-HR": "bg-orange/10 text-orange border-orange/20",
  "13F-NT": "bg-orange/10 text-orange border-orange/20",
  "8-K":    "bg-purple/10 text-purple border-purple/20",
  "S-1":    "bg-purple/10 text-purple border-purple/20",
  "S-1/A":  "bg-purple/10 text-purple border-purple/20",
};

export default function FilingBadge({ type }: { type: string }) {
  const style = STYLES[type] ?? "bg-muted/10 text-muted border-muted/20";
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-semibold rounded-full border ${style}`}>
      {type}
    </span>
  );
}
