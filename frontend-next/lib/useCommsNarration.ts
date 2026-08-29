"use client";

import { useEffect, useRef } from "react";
import { detectCommsEvents, type CommsSnapshot } from "@/lib/commsEvents";
import { useRaceStore } from "@/store/raceStore";

/** Push FIELD/ARIS narration into Main Comms as race state changes. */
export function useCommsNarration() {
  const prev = useRef<CommsSnapshot | null>(null);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const playState = useRaceStore((s) => s.consolePlayState);
  const currentLap = useRaceStore((s) => s.currentLap);
  const racePhase = useRaceStore((s) => s.racePhase);
  const rainfall = useRaceStore((s) => s.rainfall);
  const recId = useRaceStore((s) => s.pendingRecommendation?.id ?? null);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const carFp = useRaceStore((s) => {
    const code = s.arisDriver ?? s.focusDriver;
    const c = code ? s.cars[code] : null;
    return `${s.racePhase}|${s.rainfall}|${c?.status}|${c?.fastest_lap}|${c?.sector2_s}|${c?.gap_to_leader_s}|${Object.values(s.cars).filter((x) => x.is_dnf).length}`;
  });

  const sessionKey = useRaceStore((s) => (s.session ? `${s.session.year}-${s.session.round}` : ""));

  useEffect(() => {
    prev.current = null;
  }, [sessionKey]);

  useEffect(() => {
    if (!isARISOn || playState !== "racing") return;
    const s = useRaceStore.getState();
    const next: CommsSnapshot = {
      lap: s.currentLap,
      phase: s.racePhase,
      rainfall: s.rainfall,
      cars: s.cars,
      focus: s.arisDriver ?? s.focusDriver,
      rec: s.pendingRecommendation,
    };
    const msgs = detectCommsEvents(prev.current, next);
    prev.current = next;
    const seen = new Set(s.commsLog.map((c) => c.id));
    for (const m of msgs) {
      if (!seen.has(m.id)) s.pushComms(m);
    }
  }, [isARISOn, playState, currentLap, racePhase, rainfall, recId, arisDriver, carFp]);
}
