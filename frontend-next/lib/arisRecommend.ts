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
  const isPit = res.action === "BOX" || res.action === "PIT_SOON";
  const pitLap = isPit ? lap : undefined;
  const label =
    isPit && compound
      ? `Pit lap ${lap} for ${compound}`
      : res.action === "STAY_OUT"
        ? "Stay out"
        : res.action.replace(/_/g, " ");
  const action: StrategyAction = isPit
    ? { kind: res.action === "BOX" ? "pit_now" : "pit_lap", pit_lap: pitLap ?? lap, pit_compound: compound ?? "HARD" }
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

export function shouldFetchRecommend(opts: {
  isARISOn: boolean;
  playState: "ready" | "starting" | "racing";
  lap: number;
  lastLap: number | null;
  tyreLife: number;
  phase: string;
  lastPhase: string | null;
  hasActiveStrategy?: boolean;
}): boolean {
  if (!opts.isARISOn || opts.playState !== "racing") return false;
  if (opts.hasActiveStrategy && (opts.lap === 1 || opts.lap === 2) && opts.lastLap == null) {
    // Ghost already follows the selected setup plan — skip the independent lap-1 recommend().
    return false;
  }
  if (opts.lastLap == null && opts.lap <= 2) return true;
  if (opts.lastLap != null && opts.lap === opts.lastLap) {
    return opts.phase !== opts.lastPhase && (opts.phase === "SC" || opts.phase === "VSC" || opts.phase === "RED_FLAG");
  }
  if (opts.lastLap != null && opts.lap - opts.lastLap < 8 && opts.phase === opts.lastPhase) return false;
  if (opts.lap === 1 || opts.lap === 2) return !opts.hasActiveStrategy;
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
 * Auto mode never asks — it tells. This composes a declarative statement of
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
      text: `RED FLAG — free tyre change. ARIS is restarting on ${compound}.`,
      kind: "red_flag_reset",
    };
  }
  if (ctx.phase === "SC" || ctx.phase === "VSC") {
    const window = ctx.phase === "SC" ? "SC WINDOW" : "VSC WINDOW";
    return isPit
      ? { text: `${window} — ARIS is pitting now for ${compound}.`, kind: "sc_window" }
      : { text: `${window} — ARIS is staying out.`, kind: "sc_window" };
  }
  if (rec.wet_heuristic) {
    const label = ctx.rainfall ? "RAIN DETECTED" : "TRACK DRYING";
    return { text: `${label} — ARIS is pitting for ${compound}.`, kind: "wet_switch" };
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
    return `Stay out — your lap ${planned} stop is still the call.`;
  }
  return recommendNarration(rec);
}

export async function fetchRecommendation(opts: {
  year: number;
  round: number;
  sessionType: string;
  driver: string;
  lap: number;
  mode: "live" | "replay";
  force?: boolean;
}): Promise<ARISRecommendation> {
  const live = await postRecommend(
    {
      year: opts.year,
      round_number: opts.round,
      session_type: opts.sessionType,
      driver_code: opts.driver,
      current_lap: opts.lap,
      mode: opts.mode,
    },
    { force: opts.force },
  );
  if (live) return mapRecommendResponse(live, opts.lap);
  return mockRecommendation(opts.lap);
}
