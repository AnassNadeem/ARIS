"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getNextRace } from "@/lib/api";
import type { NextRaceInfo } from "@/lib/types";

// A race counts as "live" from its scheduled start until this many ms later —
// wide enough to cover a red-flagged / extended session.
const RACE_WINDOW_MS = 3 * 60 * 60 * 1000;

export function LiveRacePreview() {
  const [info, setInfo] = useState<NextRaceInfo | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    getNextRace().then(setInfo);
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  if (!info) {
    return (
      <div className="flex flex-1 flex-col rounded-[8px] border border-border bg-surface p-5">
        <div className="font-mono-data text-xs uppercase text-muted">Loading next race…</div>
      </div>
    );
  }

  const target = new Date(info.countdownTargetIso).getTime();
  const diff = target - now;
  const isLive = diff <= 0 && diff > -RACE_WINDOW_MS;

  const parts = [
    { label: "D", value: Math.max(0, Math.floor(diff / 86_400_000)) },
    { label: "H", value: Math.max(0, Math.floor((diff % 86_400_000) / 3_600_000)) },
    { label: "M", value: Math.max(0, Math.floor((diff % 3_600_000) / 60_000)) },
    { label: "S", value: Math.max(0, Math.floor((diff % 60_000) / 1000)) },
  ];

  return (
    <div className="flex flex-1 flex-col justify-between rounded-[8px] border border-border bg-surface p-5 text-left">
      <div>
        <div className="font-mono-data text-[11px] uppercase tracking-widest text-muted">
          {isLive ? (
            <span className="flex items-center gap-1.5 text-red">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red" /> Live now
            </span>
          ) : (
            "Next race"
          )}
        </div>
        <h3 className="mt-1 text-lg font-bold text-white">
          {info.countryFlag} {info.raceName}
        </h3>
        <p className="mt-0.5 font-mono-data text-[11px] text-muted">{info.circuitName}</p>
      </div>

      {isLive ? (
        <Link
          href="/live"
          className="mt-4 inline-flex items-center justify-center gap-2 rounded-[8px] bg-red px-5 py-2.5 font-mono-data text-xs font-semibold uppercase tracking-wide text-white transition-transform hover:scale-[1.02] hover:brightness-110"
        >
          ● WATCH LIVE →
        </Link>
      ) : (
        <>
          <div className="mt-4 flex gap-2 font-mono-data">
            {parts.map((p) => (
              <div
                key={p.label}
                className="flex flex-1 flex-col items-center rounded border border-border bg-carbon px-2 py-1.5"
              >
                <span className="text-lg text-white">{String(p.value).padStart(2, "0")}</span>
                <span className="text-[9px] uppercase text-muted-2">{p.label}</span>
              </div>
            ))}
          </div>
          <Link
            href="/live"
            className="mt-4 inline-flex items-center justify-center gap-2 rounded-[8px] border border-border px-5 py-2.5 font-mono-data text-xs font-semibold uppercase tracking-wide text-white transition-colors hover:border-white"
          >
            → LIVE HUB
          </Link>
        </>
      )}
    </div>
  );
}
