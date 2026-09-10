import { mockRecommendation, postRecommend } from "@/lib/api";
import { normalizeCompound } from "@/lib/compounds";
import type { ARISRecommendation, RecommendApiResponse, StratPlan, StrategyAction } from "@/lib/types";

export interface StintSegment {
  index: number;
  compound: string;
  startLap: number;
  /** Inclusive last lap of the stint; null while the final stint is open-ended. */
  endLap: number | null;
}

/**
 * Turn a flat StratPlan (start compound + pit laps/compounds) into a stint
 * list for the strategy panel: each entry is compound + start/end lap. The
 * final stint runs to `totalLaps` (or stays open if totalLaps is unknown).
 */
export function buildStintPlan(plan: StratPlan | null, totalLaps: number): StintSegment[] {
  if (!plan) return [];
  const pitLaps = (plan.pit_laps ?? []).filter((n) => n > 0).sort((a, b) => a - b);
  const compounds = plan.pit_compounds ?? [];
  const segments: StintSegment[] = [];
  let start = 1;
  let compound = plan.start_compound || "MEDIUM";
  for (let i = 0; i < pitLaps.length; i++) {
    const pitLap = pitLaps[i];
    segments.push({ index: i, compound, startLap: start, endLap: pitLap });
    start = pitLap + 1;
    compound = compounds[i] || compound;
  }
  segments.push({
    index: segments.length,
    compound,
    startLap: start,
    endLap: totalLaps > 0 && totalLaps >= start ? totalLaps : null,
  });
  return segments;
}

export function currentStintIndex(segments: StintSegment[], currentLap: number): number {
  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i];
    if (currentLap >= seg.startLap && (seg.endLap == null || currentLap <= seg.endLap)) return i;
  }
  return Math.max(0, segments.length - 1);
}

export function fmtDeltaVsStay(delta: number): string {
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(1)} s`;
}

export function mapRecommendResponse(res: RecommendApiResponse, lap: number): ARISRecommendation {
  const compound = res.compound_recommendation ? normalizeCompound(res.compound_recommendation) : undefined;
  const extractedPit = extractRecommendedPitLap(res);
  const isImminentPit = res.action === "BOX" || res.action === "PIT_SOON";
  // Far PIT_LAP cards are collapsed to STAY_OUT on the wire when outside the
  // +3-lap window, but evidence still has `pit L{n}` (and often a large
  // negative net delta). Surface those as pit_lap so Auto/comms compare
  // against Strat B. At lap 1 the engine's top card is often L9 (+8 offset)
  // - useArisRecommendLoop must not call recommend() at lights-out.
  const isDeferredPit =
    res.action === "STAY_OUT" &&
    extractedPit != null &&
    extractedPit > lap + 3 &&
    res.net_delta_s < -0.2 &&
    Boolean(compound);
  const isPit = isImminentPit || isDeferredPit;
  const pitLap = isPit ? (extractedPit ?? lap) : undefined;
  const label =
    isPit && compound
      ? `Pit lap ${pitLap ?? lap} for ${compound}`
      : res.action === "STAY_OUT"
        ? "Stay out"
        : res.action.replace(/_/g, " ");
  const action: StrategyAction = isPit
    ? {
        kind: res.action === "BOX" ? "pit_now" : "pit_lap",
        pit_lap: pitLap ?? lap,
        pit_compound: compound ?? "HARD",
      }
    : { kind: "stay_out" };
  return {
    id: res.decision_record_id || `rec-${lap}`,
    lap,
    rank: 1,
    label,
    action,
    delta_vs_stay_out_s: res.net_delta_s,
    mean_race_time_s: 0,
    confidence_std_s: res.confidence ?? 0,
    p10_delta_s: res.p10_delta_s ?? res.net_delta_s,
    p90_delta_s: res.p90_delta_s ?? res.net_delta_s,
    evidence: res.reasoning || label,
    narration_context: { data_source: res.data_source, lap_note: res.lap_note },
    tactical: res.lap_note ?? null,
    extrapolation_beyond_laps: 0,
    extrapolation_weight: 1,
    wet_heuristic: Boolean(res.wet_heuristic),
    cql_q_delta: 0,
    rank_score: Math.max(0, Math.min(1, res.confidence || 0.5)),
  };
}

/** Absolute pit lap from recommend evidence (`pit L9->HARD`) or alt notes (`Pit lap 9 for HARD`). */
export function extractRecommendedPitLap(res: Pick<RecommendApiResponse, "reasoning" | "alternatives">): number | undefined {
  const blob = [res.reasoning, ...(res.alternatives ?? []).map((a) => a.note)]
    .filter(Boolean)
    .join(" ");
  const m = blob.match(/\bpit\s+L(\d+)\b/i) || blob.match(/\bPit lap (\d+)\b/i);
  if (!m) return undefined;
  const n = Number(m[1]);
  return Number.isFinite(n) && n > 0 ? n : undefined;
}

export function recommendNarration(rec: ARISRecommendation): string {
  const compound = rec.action.pit_compound;
  const pitLap = rec.action.pit_lap ?? rec.lap;
  const core =
    rec.action.kind === "stay_out"
      ? rec.label
      : compound
        ? `Pit lap ${pitLap} for ${compound}`
        : rec.label;
  return `ARIS recommends: ${core}, Δ ${fmtDeltaVsStay(rec.delta_vs_stay_out_s)} vs stay`;
}

export type RecommendFetchDecision =
  | boolean
  | { fetch: true; bypassCooldown: true; reason: "rain_started" | "rain_stopped" };

export function recommendFetchWanted(decision: RecommendFetchDecision): boolean {
  return typeof decision === "object" ? decision.fetch : decision;
}

/** Lap 0 (pre-grid clock) through lap 2 - lights-out / opening stint. */
export function isLightsOutLap(lap: number): boolean {
  return lap <= 2;
}

/**
 * Comms line for the locked pre-race plan at lights-out.
 * Uses Strat B (active/selected) pit lap - never the engine's lap-1+8=9 candidate.
 */
export function lightsOutPlanStatement(plan: {
  pit_laps?: number[] | null;
  pit_compounds?: string[] | null;
  name?: string | null;
}): string {
  const pitLap = (plan.pit_laps ?? []).find((n) => n > 0);
  const compound = plan.pit_compounds?.[0] ? normalizeCompound(plan.pit_compounds[0]) : "HARD";
  if (pitLap != null) {
    return `ARIS is pitting on lap ${pitLap} for ${compound}.`;
  }
  return "ARIS is staying out on the locked pre-race plan.";
}

export function shouldFetchRecommend(opts: {
  isARISOn: boolean;
  playState: "ready" | "starting" | "racing";
  lap: number;
  lastLap: number | null;
  tyreLife: number;
  phase: string;
  lastPhase: string | null;
  hasActiveStrategy?: boolean;
  /** Plan selected in setup but not yet copied to activeStrategy. */
  hasSelectedStrategy?: boolean;
  wasRaining?: boolean;
  isRaining?: boolean;
}): RecommendFetchDecision {
  if (!opts.isARISOn || opts.playState !== "racing") return false;
  // Backend rejects current_lap < 1; never invent a mock pit from lap 0.
  if (opts.lap < 1) return false;
  const planReady = Boolean(opts.hasActiveStrategy || opts.hasSelectedStrategy);
  if (planReady && isLightsOutLap(opts.lap) && opts.lastLap == null) {
    // Ghost already follows the selected setup plan - skip the independent
    // lights-out recommend(). At lap 1 the engine's top card is often
    // "Pit lap 9 for HARD" (candidate offset +8), which is not Strat B.
    return false;
  }
  const wasRaining = Boolean(opts.wasRaining);
  const isRaining = Boolean(opts.isRaining);
  // Rainfall flips are urgent: bypass the 8-lap cooldown and same-lap guard.
  if (!wasRaining && isRaining) {
    return { fetch: true, bypassCooldown: true, reason: "rain_started" };
  }
  if (wasRaining && !isRaining) {
    return { fetch: true, bypassCooldown: true, reason: "rain_stopped" };
  }
  // Opening laps with no plan yet: wait - do not call recommend() / mock pit.
  if (opts.lastLap == null && isLightsOutLap(opts.lap) && !planReady) return false;
  if (opts.lastLap == null && opts.lap <= 2) return true;
  if (opts.lastLap != null && opts.lap === opts.lastLap) {
    return opts.phase !== opts.lastPhase && (opts.phase === "SC" || opts.phase === "VSC" || opts.phase === "RED_FLAG");
  }
  if (opts.lastLap != null && opts.lap - opts.lastLap < 8 && opts.phase === opts.lastPhase) return false;
  if (isLightsOutLap(opts.lap)) return !planReady;
  if (opts.phase !== opts.lastPhase && (opts.phase === "SC" || opts.phase === "VSC" || opts.phase === "RED_FLAG")) {
    return true;
  }
  // Pit windows: first-stop band and a later second-stop band.
  if (opts.tyreLife >= 16 && opts.tyreLife <= 18) return true;
  if (opts.tyreLife >= 28 && opts.tyreLife <= 30) return true;
  if (opts.lap === 18 || opts.lap === 25 || opts.lap === 33) return true;
  return false;
}

/**
 * Auto mode never asks - it tells. This composes a declarative statement of
 * what ARIS is doing (not "should I…"/"consider…") for the given race
 * context, used for the big strategy-change box and its comms line.
 */
export function autoDecisionStatement(
  rec: ARISRecommendation,
  ctx: { phase: string; rainfall?: boolean; wasRaining?: boolean },
): { text: string; kind: "strategy_change" | "sc_window" | "red_flag_reset" | "wet_switch" } {
  const compound = rec.action.pit_compound ?? "the recommended tyre";
  const pitLap = rec.action.pit_lap ?? rec.action.pit_laps?.[0] ?? rec.lap;
  const isPit = rec.action.kind !== "stay_out";

  if (ctx.phase === "RED_FLAG") {
    return {
      text: `RED FLAG. Free tyre change. ARIS is restarting on ${compound}.`,
      kind: "red_flag_reset",
    };
  }
  if (ctx.phase === "SC" || ctx.phase === "VSC") {
    const window = ctx.phase === "SC" ? "SC WINDOW" : "VSC WINDOW";
    return isPit
      ? { text: `${window}. ARIS is pitting now for ${compound}.`, kind: "sc_window" }
      : { text: `${window}. ARIS is staying out.`, kind: "sc_window" };
  }
  if (rec.wet_heuristic) {
    const label = ctx.rainfall ? "RAIN DETECTED" : "TRACK DRYING";
    return { text: `${label}. ARIS is pitting for ${compound}.`, kind: "wet_switch" };
  }
  return {
    text: isPit
      ? `ARIS is pitting on lap ${pitLap} for ${compound}.`
      : `ARIS strategy update: staying out.`,
    kind: "strategy_change",
  };
}

export function annotateVsActivePlan(
  rec: ARISRecommendation,
  active: { pit_laps: number[]; name?: string } | null,
): string {
  const planned = active?.pit_laps?.[0];
  const recPit = rec.action.pit_lap ?? rec.action.pit_laps?.[0];
  if (planned != null && recPit != null && planned === recPit) {
    return `Your lap ${planned} stop is still optimal.`;
  }
  if (planned != null && recPit != null && recPit !== planned) {
    return `Consider moving to lap ${recPit} (plan was lap ${planned}).`;
  }
  if (rec.action.kind === "stay_out" && planned != null) {
    return `Stay out. Your lap ${planned} stop is still the call.`;
  }
  return recommendNarration(rec);
}

/** Offline fallback that does not invent an early-race pit (mockRecommendation pits "this lap"). */
function stayOutFallback(lap: number): ARISRecommendation {
  return {
    id: `rec-stay-${lap}`,
    lap,
    rank: 1,
    label: "Stay out",
    action: { kind: "stay_out" },
    delta_vs_stay_out_s: 0,
    mean_race_time_s: 0,
    confidence_std_s: 0,
    p10_delta_s: 0,
    p90_delta_s: 0,
    evidence: "No live recommend payload. Holding the current plan.",
    narration_context: {},
    tactical: null,
    extrapolation_beyond_laps: 0,
    extrapolation_weight: 1,
    wet_heuristic: false,
    cql_q_delta: 0,
    rank_score: 0.4,
  };
}

export async function fetchRecommendation(opts: {
  year: number;
  round: number;
  sessionType: string;
  driver: string;
  lap: number;
  mode: "live" | "replay";
  force?: boolean;
  /** Current tick rainfall - forwarded as override_rainfall for replay rain edge. */
  isRaining?: boolean;
  /** Prior tick rainfall - dry→wet edge for INTER debounce. */
  wasRaining?: boolean;
}): Promise<ARISRecommendation> {
  if (opts.lap < 1) return stayOutFallback(Math.max(0, opts.lap));
  const live = await postRecommend(
    {
      year: opts.year,
      round_number: opts.round,
      session_type: opts.sessionType,
      driver_code: opts.driver,
      current_lap: opts.lap,
      mode: opts.mode,
      ...(opts.isRaining !== undefined
        ? { override_rainfall: opts.isRaining }
        : {}),
      ...(opts.wasRaining !== undefined ? { was_raining: opts.wasRaining } : {}),
    },
    { force: opts.force },
  );
  if (live) return mapRecommendResponse(live, opts.lap);
  // Opening laps: never fall back to mockRecommendation (always "pit this lap for HARD").
  if (isLightsOutLap(opts.lap)) return stayOutFallback(opts.lap);
  return mockRecommendation(opts.lap);
}
