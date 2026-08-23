"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LAST_KNOWN_STATUS, getStatus } from "@/lib/api";
import type { StatusResponse } from "@/lib/types";

export function HeroSection() {
  const [status, setStatus] = useState<StatusResponse>(LAST_KNOWN_STATUS);

  useEffect(() => {
    let mounted = true;
    getStatus().then((s) => {
      if (mounted) setStatus(s);
    });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="flex min-h-[92vh] flex-col items-center justify-center px-6 text-center">
      <h1
        className="text-[64px] leading-none font-extrabold tracking-[-0.03em] text-white sm:text-[96px]"
        style={{ letterSpacing: "-4px" }}
      >
        ARIS
      </h1>
      <p className="mt-5 font-mono-data text-[13px] uppercase tracking-[0.15em] text-muted sm:text-sm">
        Always On Race Intelligence System
      </p>

      <div className="mt-10 flex flex-col gap-3 sm:flex-row">
        <Link
          href="/live"
          className="inline-flex items-center justify-center gap-2 rounded-[8px] bg-red px-7 py-3 font-mono-data text-sm font-semibold uppercase tracking-wide text-white transition-transform hover:scale-[1.02] hover:brightness-110"
        >
          → LIVE RACE
        </Link>
        <Link
          href="/replay"
          className="inline-flex items-center justify-center gap-2 rounded-[8px] border border-border px-7 py-3 font-mono-data text-sm font-semibold uppercase tracking-wide text-white transition-colors hover:border-white"
        >
          REPLAY A RACE
        </Link>
      </div>

      <div className="mt-8 font-mono-data text-[12px] text-muted">
        {status.version} · {status.last_gate} · {status.match_rate.toFixed(3)} match-rate ({status.match_rate_fraction})
      </div>
    </section>
  );
}
