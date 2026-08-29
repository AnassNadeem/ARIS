import { normalizeCompound } from "@/lib/compounds";
import type { ARISRecommendation, CarState, Compound, GhostDeltaPoint, GhostTickData } from "@/lib/types";

const GHOST_PREFIX = "A_";
const TYPICAL_LAP_S = 90;
const MIN_VISIBLE_OFFSET = 0.012;

export function ghostCodeFor(driver: string): string {
  const code = driver.replace(/^A_/, "").toUpperCase();
  return `${GHOST_PREFIX}${code}`;
}

export function asGhostTick(raw: unknown): GhostTickData | null {
  if (!raw || typeof raw !== "object") return null;
  const g = raw as Record<string, unknown>;
  const driver = String(g.driver_code || "").toUpperCase();
  if (!driver) return null;
  const history = Array.isArray(g.delta_history)
    ? g.delta_history.map((pt) => {
        const row = (pt ?? {}) as Record<string, unknown>;
        return {
          lap: Number(row.lap) || 0,
          delta: Number(row.delta) || 0,
          ghost_pos: Number(row.ghost_pos) || 0,
          real_pos: Number(row.real_pos) || 0,
        };
      })
    : [];
  const outcome = g.outcome;
  const tyre = normalizeCompound(String(g.ghost_compound || g.ghost_tyre || "HARD"));
  const typical = Number(g.typical_lap_s);
  const onTrack = Number(g.ghost_position_on_track);
  return {
    driver_code: driver,
    divergence_lap: Number(g.divergence_lap) || 1,
    aris_action: String(g.aris_action || ""),
    real_action: String(g.real_action || ""),
    ghost_tyre: tyre,
    ghost_tyre_age: Number(g.ghost_tyre_age) || 0,
    ghost_position: Number(g.ghost_position) || 0,
    ghost_cumulative_delta: Number(g.ghost_cumulative_delta) || 0,
    gap_to_leader_s: Number.isFinite(Number(g.gap_to_leader_s)) ? Number(g.gap_to_leader_s) : undefined,
    active: g.active !== false,
    outcome:
      outcome === "ARIS_CORRECT" || outcome === "ARIS_INCORRECT" || outcome === "INCONCLUSIVE"
        ? outcome
        : null,
    delta_history: history,
    ghost_compound: tyre,
    typical_lap_s: Number.isFinite(typical) && typical > 1 ? typical : TYPICAL_LAP_S,
    from_lap_one: g.from_lap_one !== false,
    ghost_position_on_track: Number.isFinite(onTrack) ? ((onTrack % 1) + 1) % 1 : undefined,
    plan_pit_laps: Array.isArray(g.plan_pit_laps) ? g.plan_pit_laps.map((n) => Number(n) || 0) : undefined,
    plan_pit_compounds: Array.isArray(g.plan_pit_compounds)
      ? (g.plan_pit_compounds.map((c) => normalizeCompound(String(c))) as Compound[])
      : undefined,
  };
}

function wrapFrac(frac: number): number {
  if (!Number.isFinite(frac)) return 0;
  return ((frac % 1) + 1) % 1;
}

function ghostFrac(baseFrac: number, deltaS: number, typicalLapS = TYPICAL_LAP_S): number {
  const typical = typicalLapS > 1 ? typicalLapS : TYPICAL_LAP_S;
  const offset = deltaS / typical;
  let frac = wrapFrac(baseFrac + offset);
  if (Math.abs(wrapFrac(frac - wrapFrac(baseFrac))) < 0.008) {
    frac = wrapFrac(baseFrac + MIN_VISIBLE_OFFSET);
  }
  return frac;
}

/** Place the ghost a delta-seconds offset along the lap from the real car. */
export function ghostCarFromTick(
  ghost: GhostTickData,
  real: CarState | null,
  lap: number,
  totalLaps: number,
): CarState {
  const delta = ghost.ghost_cumulative_delta;
  const baseFrac = real?.path_frac ?? 0;
  const typical = ghost.typical_lap_s && ghost.typical_lap_s > 1 ? ghost.typical_lap_s : TYPICAL_LAP_S;
  const frac =
    ghost.ghost_position_on_track != null
      ? wrapFrac(ghost.ghost_position_on_track)
      : ghostFrac(baseFrac, delta, typical);
  const visibleFrac =
    real && Math.abs(wrapFrac(frac - wrapFrac(baseFrac))) < 0.008
      ? wrapFrac(baseFrac + MIN_VISIBLE_OFFSET)
      : frac;
  const compound = (ghost.ghost_compound ?? ghost.ghost_tyre) as Compound;
  return {
    driver_code: ghostCodeFor(ghost.driver_code),
    driver_number: real?.driver_number ?? 0,
    full_name: `[A] ${ghost.driver_code}`,
    team: real?.team ?? "",
    team_colour: real?.team_colour ?? "#e8002d",
    position: ghost.ghost_position || real?.position || null,
    lap_number: lap,
    compound,
    tyre_life: ghost.ghost_tyre_age,
    gap_to_leader_s:
      ghost.gap_to_leader_s != null
        ? ghost.gap_to_leader_s
        : real?.gap_to_leader_s != null
          ? real.gap_to_leader_s - delta
          : null,
    gap_ahead_s: null,
    gap_ahead_history: [],
    last_lap_s: null,
    best_lap_s: null,
    pit_stops: ghost.plan_pit_laps?.filter((p) => p > 0 && p <= lap).length ?? 0,
    is_pitted: false,
    is_dnf: false,
    status: "RUNNING",
    path_frac: visibleFrac,
    x: real?.x ?? 0,
    y: real?.y ?? 0,
    speed_kph: real?.speed_kph ?? 0,
    heading_rad: real?.heading_rad ?? 0,
    laps_remaining: Math.max(0, totalLaps - lap),
    total_laps: totalLaps,
    is_aris_driver: false,
    ghost_cumulative_delta: delta,
    divergence_lap: ghost.divergence_lap,
    aris_action: ghost.aris_action,
    real_action: ghost.real_action,
  };
}

/** Fallback ghost so the map/tower still show ARIS vs real before DB precompute lands. */
export function syntheticGhostCar(
  rec: ARISRecommendation,
  real: CarState,
  lap: number,
  totalLaps: number,
): CarState {
  const delta = rec.delta_vs_stay_out_s;
  const frac = ghostFrac(real.path_frac ?? 0, rec.delta_vs_stay_out_s);
  const compound = rec.action.pit_compound ?? real.compound;
  return {
    ...real,
    driver_code: ghostCodeFor(real.driver_code),
    full_name: `[A] ${real.driver_code}`,
    compound,
    tyre_life: rec.action.kind === "stay_out" ? real.tyre_life : 0,
    last_lap_s: null,
    best_lap_s: null,
    path_frac: frac,
    ghost_cumulative_delta: -delta,
    divergence_lap: rec.lap,
    aris_action: rec.label,
    real_action: "LIVE",
  };
}

/**
 * Minimal GhostDelta-panel data derived from a live recommendation, so the
 * chart agrees with the synthetic map dot from `syntheticGhostCar` instead of
 * showing "No active ghost driver" while a ghost car is visible on the map
 * (fix-pass item 8). Real delta history isn't available yet — only the
 * current point — so the chart will just show a single point until the DB
 * precompute lands and replaces this with the real `GhostTickData`.
 */
export function syntheticGhostTick(
  rec: ARISRecommendation,
  driverCode: string,
  lap: number,
): GhostTickData {
  const delta = -rec.delta_vs_stay_out_s;
  const history: GhostDeltaPoint[] = [
    { lap, delta, ghost_pos: 0, real_pos: 0 },
  ];
  return {
    driver_code: driverCode.toUpperCase(),
    divergence_lap: rec.lap,
    aris_action: rec.label,
    real_action: "LIVE",
    ghost_tyre: normalizeCompound(rec.action.pit_compound ?? "HARD"),
    ghost_tyre_age: 0,
    ghost_position: 0,
    ghost_cumulative_delta: delta,
    active: true,
    outcome: null,
    delta_history: history,
    from_lap_one: false,
  };
}
