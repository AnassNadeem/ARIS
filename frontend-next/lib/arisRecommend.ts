import { mockRecommendation, postRecommend } from "@/lib/api";
import { normalizeCompound } from "@/lib/compounds";
import type { ARISRecommendation, RecommendApiResponse, StrategyAction } from "@/lib/types";

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
}): boolean {
  if (!opts.isARISOn || opts.playState !== "racing") return false;
  if (opts.lastLap == null && opts.lap <= 2) return true;
  if (opts.lastLap != null && opts.lap === opts.lastLap) {
    return opts.phase !== opts.lastPhase && (opts.phase === "SC" || opts.phase === "VSC" || opts.phase === "RED_FLAG");
  }
  if (opts.lastLap != null && opts.lap - opts.lastLap < 8 && opts.phase === opts.lastPhase) return false;
  if (opts.lap === 1 || opts.lap === 2) return true;
  if (opts.phase !== opts.lastPhase && (opts.phase === "SC" || opts.phase === "VSC" || opts.phase === "RED_FLAG")) {
    return true;
  }
  // Pit windows: first-stop band and a later second-stop band.
  if (opts.tyreLife >= 16 && opts.tyreLife <= 18) return true;
  if (opts.tyreLife >= 28 && opts.tyreLife <= 30) return true;
  if (opts.lap === 18 || opts.lap === 25 || opts.lap === 33) return true;
  return false;
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
