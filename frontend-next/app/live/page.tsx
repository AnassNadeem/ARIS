"use client";

import { useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { ARISConsole } from "@/components/layout/ARISConsole";
import { AppHeader } from "@/components/layout/AppHeader";
import { NoLiveSession } from "@/components/live/NoLiveSession";

export default function LivePage() {
  const [liveActive, setLiveActive] = useState(false);
  const setSession = useRaceStore((s) => s.setSession);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const setARISDriver = useRaceStore((s) => s.setARISDriver);

  function enterDemoLiveSession() {
    setSession({
      year: 2026,
      round: 15,
      sessionType: "R",
      circuitName: "Circuit Zandvoort",
      countryFlag: "🇳🇱",
      totalLaps: 72,
      date: new Date().toISOString(),
      driverCode: arisDriver ?? "VER",
    });
    setARISDriver(arisDriver ?? "VER");
    setLiveActive(true);
  }

  if (liveActive) {
    return <ARISConsole mode="live" />;
  }

  return (
    <>
      <AppHeader backHref="/" />
      <NoLiveSession onEnterDemo={enterDemoLiveSession} />
    </>
  );
}
