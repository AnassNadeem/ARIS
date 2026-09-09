"use client";

import { useEffect, useRef, useState } from "react";
import {
  annotateVsActivePlan,
  autoDecisionStatement,
  fetchRecommendation,
  isLightsOutLap,
  lightsOutPlanStatement,
  recommendFetchWanted,
  recommendNarration,
  shouldFetchRecommend,
} from "@/lib/arisRecommend";
import { useRaceStore } from "@/store/raceStore";

/**
 * A resolved recommendation dispatched more than this many laps ago is
 * stale — the replay clock moved on while the request was in flight, so
 * showing/adopting it now would surface a decision (e.g. "pit now") for a
 * lap that has already passed.
 */
const STALE_RECOMMEND_LAP_TOLERANCE = 2;

/**
 * When ARIS strategy is on and the console is racing, call POST /api/aris/recommend
 * around pit windows, on driver change, and when the user clicks Get strategy.
 * At lights-out the ghost already follows Strat B — we only confirm that plan
 * in comms (never an independent recommend() that ranks lap-1+8=9).
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
  const selectedStrategy = useRaceStore((s) => s.selectedStrategy);
  const isRaining = useRaceStore((s) => s.rainfall);
  const lastLap = useRef<number | null>(null);
  const lastPhase = useRef<string | null>(null);
  const lightsOutPlanAnnounced = useRef(false);
  const inFlight = useRef(false);
  const forceRef = useRef(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    lastLap.current = null;
    lastPhase.current = null;
    lightsOutPlanAnnounced.current = false;
  }, [session?.year, session?.round]);

  useEffect(() => {
    lastLap.current = null;
    forceRef.current = true;
  }, [arisDriver, strategyEpoch]);

  useEffect(() => {
    if (consoleMode === "live" || !isARISOn || !session) return;
    const driver = arisDriver ?? session.driverCode;
    if (!driver) return;
    const packOk = consoleMode !== "replay" || packStage === "minimal" || packStage === "full";
    if (!packOk) return;
    const force = forceRef.current;
    if (playState !== "racing" && !force) return;
    const car = useRaceStore.getState().cars[driver];
    const tyreLife = car?.tyre_life ?? 0;
    const storeSnap = useRaceStore.getState();
    // Lights-out / plan statement must match the Strat B (or A/C) card the
    // user picked in setup. Prefer selectedStrategy over activeStrategy:
    // ghost-recompute failure used to overwrite activeStrategy with the
    // baked R2 pit lap (e.g. Strat B L22 card vs ghost L24 comms).
    const plan =
      storeSnap.selectedStrategy ??
      storeSnap.activeStrategy ??
      (storeSnap.r2Ghost?.strategy?.pit_laps?.length
        ? {
            pit_laps: storeSnap.r2Ghost.strategy.pit_laps,
            pit_compounds: storeSnap.r2Ghost.strategy.compounds,
            name: storeSnap.r2Ghost.strategy.label,
          }
        : null);
    // The ghost already follows the plan the user picked pre-race — never
    // fire an independent lights-out recommend() that could immediately
    // contradict it (engine top card at lap 1 is often pit lap 9 = +8 offset).
    // `force` (driver change / "Get strategy") must NOT bypass this guard.
    const atLightsOut = isLightsOutLap(currentLap) && lastLap.current == null;
    const wasRaining = storeSnap.wasRaining;
    const consumeRainTick = () => {
      if (wasRaining !== isRaining) {
        useRaceStore.getState().setWasRaining(isRaining);
      }
    };

    if (atLightsOut) {
      if (!plan) {
        // Plan still loading into the store — wait; do not mock-pit.
        lastPhase.current = racePhase;
        forceRef.current = false;
        consumeRainTick();
        return;
      }
      if (!lightsOutPlanAnnounced.current) {
        lightsOutPlanAnnounced.current = true;
        const text = lightsOutPlanStatement(plan);
        useRaceStore.getState().pushComms({
          id: `lights-out-plan-${session.year}-R${session.round}-${driver}`,
          lap: Math.max(0, currentLap),
          source: "ARIS",
          text,
          timestamp: Date.now(),
        });
      }
      lastLap.current = Math.max(1, currentLap);
      lastPhase.current = racePhase;
      forceRef.current = false;
      consumeRainTick();
      return;
    }

    if (
      !force &&
      !recommendFetchWanted(
        shouldFetchRecommend({
          isARISOn,
          playState,
          lap: currentLap,
          lastLap: lastLap.current,
          tyreLife,
          phase: racePhase,
          lastPhase: lastPhase.current,
          hasActiveStrategy: Boolean(activeStrategy || plan),
          hasSelectedStrategy: Boolean(selectedStrategy),
          wasRaining,
          isRaining,
        }),
      )
    ) {
      lastPhase.current = racePhase;
      consumeRainTick();
      return;
    }
    if (inFlight.current) return;
    inFlight.current = true;
    forceRef.current = false;
    consumeRainTick();
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
      isRaining,
      wasRaining,
    })
      .then((rec) => {
        const store = useRaceStore.getState();
        if (!store.isARISOn) return;
        const staleLaps = store.currentLap - lap;
        if (staleLaps > STALE_RECOMMEND_LAP_TOLERANCE) {
          // Dispatched at `lap`, but the replay clock has moved on well
          // past it by the time this resolved — discard rather than show
          // a "pit now" banner/comms line for a lap that already passed.
          console.warn(
            `[ARIS] discarding stale recommendation dispatched at lap ${lap}, now at lap ${store.currentLap}`,
          );
          return;
        }
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
  }, [
    isARISOn,
    playState,
    currentLap,
    racePhase,
    session,
    arisDriver,
    consoleMode,
    packStage,
    arisMode,
    strategyEpoch,
    retry,
    activeStrategy,
    selectedStrategy,
    isRaining,
  ]);
}
