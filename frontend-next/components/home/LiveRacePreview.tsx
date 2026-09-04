"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArisHomeControls } from "@/components/home/ArisHomeControls";
import { getDrivers, getLiveHub, getLiveLeaderCode } from "@/lib/api";
import { isRaceSession, liveHubEnterHref } from "@/lib/liveSetup";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { sessionLabel } from "@/lib/sessionFlow";
import { applyLiveHubSessionWindows, featuredHubSession, sessionIsLiveNow } from "@/lib/sessionWindow";
import { useRaceStore } from "@/store/raceStore";
import type { DriverListing, LiveHub } from "@/lib/types";

export function LiveRacePreview() {
  const [raw, setRaw] = useState<LiveHub | null>(null);
  const [failed, setFailed] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [drivers, setDrivers] = useState<DriverListing[]>(MOCK_DRIVERS_2025);
  const [arisOn, setArisOn] = useState(true);
  const [driver, setDriver] = useState<string | null>(null);
  const setARISOn = useRaceStore((s) => s.setARISOn);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const next = await getLiveHub();
      if (cancelled) return;
      if (next) {
        setRaw(next);
        setFailed(false);
      } else {
        setFailed(true);
      }
    }
    void load();
    const id = setInterval(() => void load(), 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!raw) return;
    let cancelled = false;
    getDrivers(raw.next.year).then((d) => {
      if (!cancelled && d.length) setDrivers(d);
    });
    return () => {
      cancelled = true;
    };
  }, [raw]);

  const info = raw ? applyLiveHubSessionWindows(raw, now) : null;
  const liveSession = info?.weekend_sessions.find((s) => sessionIsLiveNow(s, now)) ?? null;
  const featured = info ? featuredHubSession(info.weekend_sessions, now) : null;
  const raceControls = Boolean(
    (liveSession && isRaceSession(liveSession.session_type)) ||
      (!liveSession && featured && isRaceSession(featured.session_type)),
  );

  useEffect(() => {
    if (driver || !drivers.length) return;
    setDriver(drivers.find((d) => d.driver_code === "VER")?.driver_code ?? drivers[0]?.driver_code ?? null);
  }, [drivers, driver]);

  useEffect(() => {
    if (!raceControls) return;
    let cancelled = false;
    getLiveLeaderCode().then((code) => {
      if (cancelled || !code) return;
      if (!drivers.some((d) => d.driver_code === code)) return;
      setDriver(code);
    });
    return () => {
      cancelled = true;
    };
  }, [raceControls, drivers]);

  function applyArisChoice(on: boolean, code: string | null) {
    setArisOn(on);
    setARISOn(on);
    if (on && code) setARISDriver(code);
  }

  if (!raw || !info) {
    return (
      <div className="flex flex-1 flex-col rounded-[8px] border border-border bg-surface p-5">
        <div className="font-mono-data text-xs uppercase text-muted">
          {failed ? "Live hub unreachable" : "Loading next race…"}
        </div>
        {failed && (
          <Link href="/live" className="mt-4 font-mono-data text-[11px] uppercase text-muted hover:text-white">
            → LIVE HUB
          </Link>
        )}
      </div>
    );
  }

  const isLive = Boolean(liveSession) || info.mode === "live_session" || info.live.is_live;
  const targetIso =
    liveSession?.datetime_utc ?? featured?.datetime_utc ?? info.countdown_target ?? info.next.next_session_datetime;
  const target = targetIso ? new Date(targetIso).getTime() : now;
  const diff = target - now;
  const nextLabel = featured && !isLive ? sessionLabel(featured.session_type) : null;

  const parts = [
    { label: "D", value: Math.max(0, Math.floor(diff / 86_400_000)) },
    { label: "H", value: Math.max(0, Math.floor((diff % 86_400_000) / 3_600_000)) },
    { label: "M", value: Math.max(0, Math.floor((diff % 3_600_000) / 60_000)) },
    { label: "S", value: Math.max(0, Math.floor((diff % 60_000) / 1000)) },
  ];

  const liveRace = Boolean(liveSession && isRaceSession(liveSession.session_type));
  const watchHref = liveHubEnterHref(liveSession, { arisOn, driver });

  return (
    <div className="flex flex-1 flex-col justify-between rounded-[8px] border border-border bg-surface p-5 text-left">
      <div>
        <div className="font-mono-data text-[11px] uppercase tracking-widest text-muted">
          {isLive ? (
            <span className="flex items-center gap-1.5 text-red">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-red" /> Live now
              {liveSession ? ` · ${sessionLabel(liveSession.session_type)}` : ""}
            </span>
          ) : nextLabel ? (
            `Next · ${nextLabel}`
          ) : (
            "Next race"
          )}
        </div>
        <h3 className="mt-1 text-lg font-bold text-white">
          {info.circuit.country_flag} {info.next.name}
        </h3>
        <p className="mt-0.5 font-mono-data text-[11px] text-muted">{info.circuit.circuit_name}</p>
        {raceControls && (
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
        )}
      </div>

      {isLive ? (
        <Link
          href={watchHref}
          onClick={() => applyArisChoice(arisOn && liveRace, driver)}
          className="mt-4 inline-flex items-center justify-center gap-2 rounded-[8px] bg-red px-5 py-2.5 font-mono-data text-xs font-semibold uppercase tracking-wide text-white transition-transform hover:scale-[1.02] hover:brightness-110"
        >
          {liveRace ? "● WATCH LIVE →" : "● LIVE HUB →"}
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
