"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArisHomeControls } from "@/components/home/ArisHomeControls";
import { getDrivers, getRecentRaces } from "@/lib/api";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { useRaceStore } from "@/store/raceStore";
import type { DriverListing, RecentRaceCard } from "@/lib/types";

export function ReplayPreviewCards() {
  const router = useRouter();
  const [races, setRaces] = useState<RecentRaceCard[]>([]);
  const [drivers, setDrivers] = useState<DriverListing[]>(MOCK_DRIVERS_2025);
  const [arisOn, setArisOn] = useState(true);
  const [driver, setDriver] = useState<string | null>(null);
  const setARISOn = useRaceStore((s) => s.setARISOn);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);

  useEffect(() => {
    getRecentRaces(3).then(setRaces);
  }, []);

  useEffect(() => {
    const year = races[0]?.year;
    if (!year) return;
    let cancelled = false;
    getDrivers(year).then((d) => {
      if (cancelled || !d.length) return;
      setDrivers(d);
      setDriver((cur) => cur ?? d.find((x) => x.driver_code === races[0]?.winnerCode)?.driver_code ?? d[0]?.driver_code ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, [races]);

  function applyArisChoice(on: boolean, code: string | null) {
    setArisOn(on);
    setARISOn(on);
    if (on && code) setARISDriver(code);
  }

  function jumpToReplay(r: RecentRaceCard) {
    applyArisChoice(arisOn, driver ?? r.winnerCode);
    const qs = new URLSearchParams({ year: String(r.year), round: String(r.round) });
    if (arisOn) {
      qs.set("aris", "1");
      if (driver ?? r.winnerCode) qs.set("driver", driver ?? r.winnerCode);
    } else {
      qs.set("start", "1");
    }
    router.push(`/replay?${qs.toString()}`);
  }

  return (
    <div className="flex flex-1 flex-col rounded-[8px] border border-border bg-surface p-5 text-left">
      <div className="font-mono-data text-[11px] uppercase tracking-widest text-muted">Replay a race</div>
      <ArisHomeControls
        arisOn={arisOn}
        drivers={drivers}
        driver={driver}
        onArisChange={(on) => applyArisChoice(on, driver)}
        onDriverChange={(code) => {
          setDriver(code);
          applyArisChoice(true, code);
        }}
      />
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
              <span className="truncate">
                {r.year} · {r.circuitName}
              </span>
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
