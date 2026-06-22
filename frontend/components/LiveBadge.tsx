"use client";

export default function LiveBadge({ label = "Live" }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-green font-medium">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-green" />
      </span>
      {label}
    </span>
  );
}
