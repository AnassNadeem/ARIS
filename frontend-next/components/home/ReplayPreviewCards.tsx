"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getRecentRaces } from "@/lib/api";
import { useRaceStore } from "@/store/raceStore";
import type { RecentRaceCard } from "@/lib/types";

export function ReplayPreviewCards() {
  const router = useRouter();
  const [races, setRaces] = useState<RecentRaceCard[]>([]);
  const setSession = useRaceStore((s) => s.setSession);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);
  const setARISOn = useRaceStore((s) => s.setARISOn);

  useEffect(() => {
    getRecentRaces(3).then(setRaces);
  }, []);

  function jumpToReplay(r: RecentRaceCard) {
    // Previews skip the full selector — ARIS defaults off, driver defaults
    // to the race winner. Both are still adjustable inside the console.
    setARISOn(false);
    setARISDriver(r.winnerCode);
    setSession({
      year: r.year,
      round: r.round,
      sessionType: "R",
      circuitName: r.circuitName,
      countryFlag: r.countryFlag,
      totalLaps: 72,
      date: r.date,
      driverCode: r.winnerCode,
    });
    router.push("/replay/console");
  }

  return (
    <div className="flex flex-1 flex-col rounded-[8px] border border-border bg-surface p-5 text-left">
      <div className="font-mono-data text-[11px] uppercase tracking-widest text-muted">Replay a race</div>
      <div className="mt-3 flex flex-1 flex-col gap-2">
        {races.length === 0 &&
          [0, 1, 2].map((i) => (
            <div key={i} className="h-[42px] animate-pulse rounded border border-border bg-carbon" />
          ))}
        {races.map((r) => (
          <button
            key={`${r.year}-${r.round}`}
            onClick={() => jumpToReplay(r)}
            className="flex items-center justify-between gap-3 rounded border border-border bg-carbon px-3 py-2 text-left hover:border-white"
          >
            <span className="flex items-center gap-2 truncate font-mono-data text-[12px] text-white">
              <span>{r.countryFlag}</span>
              <span className="truncate">{r.circuitName}</span>
              {r.sessionType === "R" && (
                <span className="rounded bg-red/15 px-1 text-[9px] text-red">RACE</span>
              )}
            </span>
            <span className="shrink-0 font-mono-data text-[10px] text-muted">🏆 {r.winner}</span>
          </button>
        ))}
      </div>
      <Link
        href="/replay"
        className="mt-4 self-start font-mono-data text-[11px] uppercase text-muted hover:text-white"
      >
        See all races →
      </Link>
    </div>
  );
}
