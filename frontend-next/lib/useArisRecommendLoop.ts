"use client";

import { useEffect, useRef, useState } from "react";
import { annotateVsActivePlan, autoDecisionStatement, fetchRecommendation, recommendNarration, shouldFetchRecommend } from "@/lib/arisRecommend";
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
  const activeStrategy = useRaceStore((s) => s.activeStrategy);
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
    // The ghost already follows the plan the user picked pre-race — never
    // fire an independent lights-out recommend() that could immediately
    // contradict it. `force` (driver change / "Get strategy" click) must
    // NOT bypass this specific guard, only the cooldown/throttle checks
    // below it; otherwise the arisDriver-changed effect below fires a
    // same-tick force on mount and Auto mode auto-adopts a lap-1 "revision"
    // seconds after the race started, before the chosen plan ever raced.
    const lockedToPreRacePlan =
      Boolean(activeStrategy) && (currentLap === 1 || currentLap === 2) && lastLap.current == null;
    if (lockedToPreRacePlan) {
      lastPhase.current = racePhase;
      forceRef.current = false;
      return;
    }
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
        hasActiveStrategy: Boolean(activeStrategy),
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
        const active = store.activeStrategy;
        const recPit = rec.action.pit_lap ?? rec.action.pit_laps?.[0];
        const planPit = active?.pit_laps?.[0];
        const samePlan = active == null || recPit == null || recPit === planPit;
        const isAuto = store.arisMode === "auto";
        const text =
          isAuto && !samePlan
            ? autoDecisionStatement(rec, { phase: racePhase, rainfall: store.rainfall }).text
            : active
              ? annotateVsActivePlan(rec, active)
              : recommendNarration(rec);
        store.pushComms({
          id: `${rec.id}-e${store.strategyEpoch}`,
          lap: rec.lap,
          source: "ARIS",
          text,
          timestamp: Date.now(),
          wetHeuristic: rec.wet_heuristic,
          recommendationId: rec.id,
        });
        if (isAuto) {
          if (samePlan) {
            store.approveRecommendation();
          } else {
            // Auto mode never asks — it tells. A pit/strategy change is a big
            // decision, so it is applied immediately and surfaced in a
            // visibly bigger box rather than waiting on a click.
            const { text: reason, kind } = autoDecisionStatement(rec, { phase: racePhase, rainfall: store.rainfall });
            void store.adoptRecommendation(rec, { auto: true, reason, kind });
          }
        }
      })
      .finally(() => {
        inFlight.current = false;
        useRaceStore.getState().setStrategyLoading(false);
        if (forceRef.current) setRetry((n) => n + 1);
      });
  }, [isARISOn, playState, currentLap, racePhase, session, arisDriver, consoleMode, packStage, arisMode, strategyEpoch, retry, activeStrategy]);
}
