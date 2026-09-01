"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/live", label: "Live" },
  { href: "/replay", label: "Replay" },
  { href: "/standings", label: "Standings" },
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
      className={`relative z-30 flex shrink-0 items-center gap-2 overflow-visible border-b border-border bg-surface-2 px-3 sm:px-4 ${
        compact ? "min-h-11 flex-wrap py-1 lg:h-11 lg:flex-nowrap lg:py-0" : "h-14"
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
        <span className="rounded bg-red/20 px-1.5 py-0.5 font-sans text-[9px] font-semibold uppercase tracking-wider text-red">
          Beta
        </span>
      </Link>
      <nav className="ml-1 flex items-center gap-1 overflow-x-auto sm:gap-2">
        {NAV_LINKS.map((l) => {
          const active = l.href === "/" ? pathname === "/" : pathname === l.href || pathname.startsWith(`${l.href}/`);
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded px-2 py-1 font-sans text-xs uppercase tracking-wide ${
                active ? "text-red" : "text-muted hover:text-white"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
      <div className="ml-auto flex shrink-0 items-center gap-2 overflow-visible">{right}</div>
    </header>
  );
}
