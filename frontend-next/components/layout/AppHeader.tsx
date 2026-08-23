"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/live", label: "Live" },
  { href: "/replay", label: "Replay" },
];

/**
 * Shared top navigation bar. Used standalone on marketing/selector pages and
 * with a `right` slot of page-specific controls (session info, ARIS toggle,
 * connection status…) on the full-bleed console pages.
 */
export function AppHeader({
  backHref,
  right,
  compact,
}: {
  /** Explicit back target. Omit to use browser history; pass null to hide the arrow. */
  backHref?: string | null;
  right?: ReactNode;
  compact?: boolean;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const showBack = backHref !== null && pathname !== "/";

  return (
    <header
      className={`flex shrink-0 items-center gap-2 border-b border-border bg-surface-2 px-3 ${
        compact ? "h-11" : "h-14"
      }`}
    >
      {showBack && (
        <button
          onClick={() => (backHref ? router.push(backHref) : router.back())}
          title="Back"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-lg text-muted hover:bg-surface hover:text-white"
        >
          ←
        </button>
      )}
      <Link
        href="/"
        className="flex shrink-0 items-center gap-2 font-mono-data text-sm font-bold uppercase tracking-widest text-white"
      >
        <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-red" />
        ARIS
      </Link>
      <nav className="ml-1 hidden items-center gap-2 sm:flex">
        {NAV_LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`rounded px-2 py-1 font-mono-data text-[13px] uppercase tracking-wide ${
              pathname === l.href ? "text-white" : "text-muted hover:text-white"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </nav>
      <div className="ml-auto flex min-w-0 items-center gap-2">{right}</div>
    </header>
  );
}
