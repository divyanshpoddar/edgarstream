"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import LiveBadge from "./LiveBadge";

const LINKS = [
  { href: "/",        label: "Home" },
  { href: "/feed",    label: "Live Feed" },
  { href: "/explore", label: "Explore" },
  { href: "/drift",   label: "Drift Alerts" },
];

export default function Navbar() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-50 bg-surface border-b border-border">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="text-lg font-bold tracking-tight">
            Edgar<span className="text-blue">Stream</span>
          </Link>
          <nav className="hidden sm:flex items-center gap-1">
            {LINKS.map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  path === href
                    ? "bg-surface-2 text-text font-medium"
                    : "text-muted hover:text-text hover:bg-surface-2"
                }`}
              >
                {label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          <LiveBadge label="Pipeline active" />
          <a
            href="/docs"
            className="text-xs text-muted hover:text-text transition-colors"
            target="_blank"
            rel="noreferrer"
          >
            API docs ↗
          </a>
        </div>
      </div>
    </header>
  );
}
