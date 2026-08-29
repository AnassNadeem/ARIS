"use client";

import { useEffect, useRef, useState } from "react";
import { fetchRecommendation, recommendNarration, shouldFetchRecommend } from "@/lib/arisRecommend";
import { useRaceStore } from "@/store/raceStore";

/**
 * When ARIS strategy is on and the console is racing, call POST /api/aris/recommend
 * at lights-out, around pit windows, on driver change, and when the user clicks Get strategy.
 */
export function useArisRecommendLoop() {
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const playState = useRaceStore((s) => s.consolePlayState);
  const currentLap = useRaceStore((s) => s.currentLap);
  const racePhase = useRaceStore((s) => s.racePhase);
  const session = useRaceStore((s) => s.session);
  const arisDriver = useRaceStore((s) => s.arisDriver);
  const consoleMode = useRaceStore((s) => s.consoleMode);
  const packStage = useRaceStore((s) => s.packStage);
  const arisMode = useRaceStore((s) => s.arisMode);
  const strategyEpoch = useRaceStore((s) => s.strategyEpoch);
  const lastLap = useRef<number | null>(null);
  const lastPhase = useRef<string | null>(null);
  const inFlight = useRef(false);
  const forceRef = useRef(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    lastLap.current = null;
    lastPhase.current = null;
  }, [session?.year, session?.round]);

  useEffect(() => {
    lastLap.current = null;
    forceRef.current = true;
  }, [arisDriver, strategyEpoch]);

  useEffect(() => {
    if (!isARISOn || !session) return;
    const driver = arisDriver ?? session.driverCode;
    if (!driver) return;
    const packOk = consoleMode !== "replay" || packStage === "minimal" || packStage === "full";
    if (!packOk) return;
    const force = forceRef.current;
    if (playState !== "racing" && !force) return;
    const car = useRaceStore.getState().cars[driver];
    const tyreLife = car?.tyre_life ?? 0;
    if (
      !force &&
      !shouldFetchRecommend({
        isARISOn,
        playState,
        lap: currentLap,
        lastLap: lastLap.current,
        tyreLife,
        phase: racePhase,
        lastPhase: lastPhase.current,
      })
    ) {
      lastPhase.current = racePhase;
      return;
    }
    if (inFlight.current) return;
    inFlight.current = true;
    forceRef.current = false;
    const lap = currentLap;
    lastLap.current = lap;
    lastPhase.current = racePhase;
    useRaceStore.getState().setStrategyLoading(true);
    void fetchRecommendation({
      year: session.year,
      round: session.round,
      sessionType: session.sessionType,
      driver,
      lap,
      mode: consoleMode,
      force,
    })
      .then((rec) => {
        const store = useRaceStore.getState();
        if (!store.isARISOn) return;
        store.setPendingRecommendation(rec);
        store.pushComms({
          id: `${rec.id}-e${store.strategyEpoch}`,
          lap: rec.lap,
          source: "ARIS",
          text: recommendNarration(rec),
          timestamp: Date.now(),
          wetHeuristic: rec.wet_heuristic,
          recommendationId: rec.id,
        });
        if (store.arisMode === "auto") {
          store.approveRecommendation();
        }
      })
      .finally(() => {
        inFlight.current = false;
        useRaceStore.getState().setStrategyLoading(false);
        if (forceRef.current) setRetry((n) => n + 1);
      });
  }, [isARISOn, playState, currentLap, racePhase, session, arisDriver, consoleMode, packStage, arisMode, strategyEpoch, retry]);
}
