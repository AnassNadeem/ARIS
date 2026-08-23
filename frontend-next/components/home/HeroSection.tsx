"use client";

import { useEffect, useState } from "react";
import { LAST_KNOWN_STATUS, getStatus } from "@/lib/api";
import type { StatusResponse } from "@/lib/types";
import { LiveRacePreview } from "@/components/home/LiveRacePreview";
import { ReplayPreviewCards } from "@/components/home/ReplayPreviewCards";

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
    <section className="flex min-h-[92vh] flex-col items-center justify-center px-6 py-16 text-center">
      <h1
        className="text-[64px] leading-none font-extrabold tracking-[-0.03em] text-white sm:text-[96px]"
        style={{ letterSpacing: "-4px" }}
      >
        ARIS
      </h1>
      <p className="mt-5 font-mono-data text-[13px] uppercase tracking-[0.15em] text-muted sm:text-sm">
        Always On Race Intelligence System
      </p>
      <p className="mt-4 max-w-xl font-mono-data text-[13px] leading-relaxed text-muted-2 sm:text-sm">
        Classical decision support stitched with modern ML — not an end-to-end black box. ARIS
        recommends a strategy, shows its evidence, and races a ghost driver against the field so you
        can see the road not taken.
      </p>

      <div className="mt-10 grid w-full max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
        <LiveRacePreview />
        <ReplayPreviewCards />
      </div>

      <div className="mt-8 font-mono-data text-[12px] text-muted">
        {status.version} · {status.last_gate} · {status.match_rate.toFixed(3)} match-rate ({status.match_rate_fraction})
      </div>
    </section>
  );
}
