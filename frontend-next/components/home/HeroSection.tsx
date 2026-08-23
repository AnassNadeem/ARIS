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
    <section className="relative flex min-h-[92vh] flex-col items-center justify-center overflow-hidden px-6 py-16 text-center">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          backgroundColor: "#0A0A0A",
          backgroundImage:
            "radial-gradient(ellipse 60% 45% at 50% 8%, rgba(232,0,45,0.16), transparent 70%), " +
            "linear-gradient(rgba(255,255,255,0.035) 1px, transparent 1px), " +
            "linear-gradient(90deg, rgba(255,255,255,0.035) 1px, transparent 1px)",
          backgroundSize: "auto, 42px 42px, 42px 42px",
          maskImage: "linear-gradient(to bottom, black 0%, black 65%, transparent 100%)",
        }}
      />
      <div className="relative z-10 flex flex-col items-center">
        <h1
          className="text-[64px] leading-none font-extrabold tracking-[-0.03em] text-red sm:text-[96px]"
          style={{ letterSpacing: "-4px" }}
        >
          ARIS
        </h1>
        <p className="mt-5 font-mono-data text-[13px] uppercase tracking-[0.15em] text-muted sm:text-sm">
          Always On Race Intelligence System
        </p>
        <p className="mt-3 max-w-md font-mono-data text-[11px] leading-relaxed text-muted-2">
          Classical decision support, not a black box — ARIS shows its evidence and races a ghost
          driver against the field.
        </p>

        <div className="mt-10 grid w-full max-w-3xl grid-cols-1 gap-4 sm:grid-cols-2">
          <LiveRacePreview />
          <ReplayPreviewCards />
        </div>

        <div className="mt-8 font-mono-data text-[12px] text-muted">
          {status.version} · {status.last_gate} · {status.match_rate.toFixed(3)} match-rate ({status.match_rate_fraction})
        </div>
      </div>
    </section>
  );
}
