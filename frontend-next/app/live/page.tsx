"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useRaceStore } from "@/store/raceStore";
import { ARISConsole } from "@/components/layout/ARISConsole";
import { AppHeader } from "@/components/layout/AppHeader";
import { LiveSetupFlow } from "@/components/LiveSetupFlow";
import { getDrivers, getLiveHub } from "@/lib/api";
import type { LiveHub } from "@/lib/types";

export default function LivePage() {
  return (
    <Suspense fallback={<div className="flex-1 p-10 font-mono-data text-sm text-muted">Loading live hub…</div>}>
      <LivePageInner />
    </Suspense>
  );
}

function LivePageInner() {
  const search = useSearchParams();
  const demo = search.get("demo") === "1";
  const watch = search.get("watch") === "1";
  const autoSession = search.get("session");
  const autoAris = search.get("aris") === "1";
  const autoDriver = search.get("driver");
  const [hub, setHub] = useState<LiveHub | null>(null);
  const [hubTried, setHubTried] = useState(false);
  const [consoleMode, setConsoleMode] = useState<"live" | "replay" | null>(null);
  const [didEnterConsole, setDidEnterConsole] = useState(false);
  const [mockConsole, setMockConsole] = useState(false);
  const setSession = useRaceStore((s) => s.setSession);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);
  const setGridDrivers = useRaceStore((s) => s.setGridDrivers);
  const setWaiting = useRaceStore((s) => s.setWaiting);
  const setTotalLaps = useRaceStore((s) => s.setTotalLaps);

  useEffect(() => {
    if (demo) enterDemo();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demo]);

  useEffect(() => {
    if (consoleMode) return;
    let cancelled = false;
    async function load() {
      const next = await getLiveHub();
      if (cancelled) return;
      setHubTried(true);
      if (!next) return;
      setHub(next);
      const drivers = await getDrivers(next.next.year);
      if (!cancelled && drivers.length) setGridDrivers(drivers);
    }
    void load();
    const id = setInterval(() => void load(), 15000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [demo, consoleMode, setGridDrivers]);

  function enterDemo() {
    setSession({
      year: 2026,
      round: 12,
      sessionType: "R",
      circuitName: "Circuit Zandvoort",
      countryFlag: "🇳🇱",
      totalLaps: 72,
      date: new Date().toISOString(),
      driverCode: arisDriver ?? "VER",
    });
    setARISDriver(arisDriver ?? "VER");
    setWaiting(true, "Waiting for live data to come.");
    setTotalLaps(72);
    setMockConsole(true);
    setDidEnterConsole(true);
    setConsoleMode("live");
  }

  const enterConsole = useCallback((mode: "live" | "replay") => {
    setDidEnterConsole(true);
    setConsoleMode(mode);
  }, []);

  if (consoleMode) {
    return (
      <ARISConsole
        mode={consoleMode}
        allowMock={demo || mockConsole}
        onBack={() => setConsoleMode(null)}
      />
    );
  }

  return (
    <>
      <AppHeader backHref="/" />
      {!hub && hubTried ? (
        <div className="flex-1 p-10 font-mono-data text-sm text-muted">
          Could not reach the live hub. Confirm the FastAPI broker is running on port 8765, then refresh.
        </div>
      ) : !hub ? (
        <div className="flex-1 p-10 font-mono-data text-sm text-muted">Loading race weekend…</div>
      ) : (
        <LiveSetupFlow
          hub={hub}
          autoEnter={watch && !didEnterConsole}
          autoSession={autoSession}
          autoAris={autoAris}
          autoDriver={autoDriver}
          onLoaded={enterConsole}
        />
      )}
    </>
  );
}
