import { normalizeCompound } from "@/lib/compounds";
import { DEFAULT_PIT_LOSS_S, pathFracAtLap } from "@/lib/r2Replay";
import type { ARISRecommendation, CarState, Compound, GhostDeltaPoint, GhostTickData } from "@/lib/types";

const GHOST_PREFIX = "A_";
export const PIT_ENTRY_FRAC = 0.84;
export const SEEK_JUMP_GRACE_S = 3;

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
    typical_lap_s: Number.isFinite(typical) && typical > 1 ? typical : undefined,
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

/** Grid slot from the chosen driver's first pos_sample (Bahrain 2024 VER = 0.97487). */
export function ghostStartFracFromSamples(
  samples?: { path_frac: number }[] | null,
): number {
  if (!samples?.length) return 0;
  const v = Number(samples[0].path_frac);
  return Number.isFinite(v) ? wrapFrac(v) : 0;
}

export interface GhostPlaybackInput {
  elapsedS: number;
  ghostLapS: number[];
  ghostCumulativeS: number[];
  totalLaps: number;
  pitLaps: number[];
  pitLossS: number;
  posSamples?: { lap_frac: number; path_frac: number }[];
  pitCompounds?: string[];
  /** Real car's t=0 path_frac (grid slot). Applied as a lap-1 offset. */
  ghostStartFrac?: number;
}

export interface GhostPlayback {
  lap: number;
  T: number;
  progress_within_lap: number;
  /** Circuit path fraction 0–1, mapped the same way real cars are. */
  path_frac: number;
  inPits: boolean;
  pitCompound: Compound | null;
  /** Lap whose tick drives tower compound/tyre (previous lap while hidden in pits). */
  towerLap: number;
  skipSeekJump: boolean;
  lastCompletedLap: number;
}

function lastFiniteLap(arr: number[]): number {
  for (let i = arr.length - 1; i >= 1; i--) {
    if (Number.isFinite(arr[i])) return i;
  }
  return 0;
}

/**
 * Absolute ghost map state from the replay clock and derived ghost_lap_s.
 * Independent of the real car's path_frac / position.
 */
export function ghostPlaybackAt(input: GhostPlaybackInput): GhostPlayback {
  const totalLaps = Math.max(1, input.totalLaps);
  const cum = input.ghostCumulativeS;
  const laps = input.ghostLapS;
  const maxLap = Math.max(lastFiniteLap(cum), lastFiniteLap(laps), 1);
  const elapsed = Number.isFinite(input.elapsedS) ? Math.max(0, input.elapsedS) : 0;
  const pitLoss = input.pitLossS > 0 ? input.pitLossS : DEFAULT_PIT_LOSS_S;
  const pitLaps = input.pitLaps.filter((n) => n > 0);

  let L = 1;
  if (cum.length > 1) {
    L = maxLap;
    for (let lap = 1; lap <= maxLap; lap++) {
      const end = cum[lap];
      if (!Number.isFinite(end)) continue;
      if (elapsed < end) {
        L = lap;
        break;
      }
      L = lap;
    }
  }
  L = Math.max(1, Math.min(totalLaps, L));

  const prevCum = L > 1 && Number.isFinite(cum[L - 1]) ? cum[L - 1] : 0;
  const T = elapsed - prevCum;
  const lapS = laps[L];
  let progress = 0;
  if (Number.isFinite(lapS) && lapS > 0) {
    progress = Math.max(0, Math.min(1, T / lapS));
  } else if (Number.isFinite(lapS) && lapS <= 0) {
    progress = 1;
  }

  const ghostLapFrac = L - 1 + progress;
  let pathFrac = wrapFrac(ghostLapFrac);
  if (input.posSamples && input.posSamples.length) {
    pathFrac = pathFracAtLap(input.posSamples, ghostLapFrac, totalLaps);
  }
  const startFrac = input.ghostStartFrac ?? ghostStartFracFromSamples(input.posSamples);
  // Independent clock maps progress 0 → S/F (0). The real car's first sample is
  // the grid slot, which is often non-zero. Offset lap 1 only so both cars
  // share the same lights-out spot; do not add again when pos_samples already
  // returned that slot (typical at progress=0).
  if (L === 1 && progress < 1 && startFrac) {
    if (!(input.posSamples && input.posSamples.length)) {
      pathFrac = wrapFrac(progress + startFrac);
    } else if (progress <= 1e-9) {
      pathFrac = startFrac;
    }
  }

  let inPits = false;
  let pitCompound: Compound | null = null;
  let skipSeekJump = elapsed < SEEK_JUMP_GRACE_S;
  for (let i = 0; i < pitLaps.length; i++) {
    const pitLap = pitLaps[i];
    const sf = pitLap > 1 && Number.isFinite(cum[pitLap - 1]) ? cum[pitLap - 1] : pitLap === 1 ? 0 : NaN;
    if (!Number.isFinite(sf)) continue;
    const pitLapS = laps[pitLap];
    const entryOffset = Number.isFinite(pitLapS) && pitLapS > 0 ? PIT_ENTRY_FRAC * pitLapS : 0;
    const entry = sf + entryOffset;
    const end = entry + pitLoss;
    if (elapsed >= entry && elapsed < end) {
      inPits = true;
      const raw = input.pitCompounds?.[i];
      pitCompound = raw ? normalizeCompound(raw) : null;
    }
    if (elapsed >= end && elapsed < end + SEEK_JUMP_GRACE_S) {
      skipSeekJump = true;
    }
  }

  const towerLap = inPits ? Math.max(1, L - 1) : L;
  return {
    lap: L,
    T,
    progress_within_lap: progress,
    path_frac: pathFrac,
    inPits,
    pitCompound,
    towerLap,
    skipSeekJump,
    lastCompletedLap: Math.max(0, L - (progress < 1 ? 1 : 0)),
  };
}

function carFromGhost(
  ghost: GhostTickData,
  real: CarState | null,
  lap: number,
  totalLaps: number,
  pathFrac: number,
  extras: Partial<CarState>,
): CarState {
  const delta = ghost.ghost_cumulative_delta;
  const compound = (ghost.ghost_compound ?? ghost.ghost_tyre) as Compound;
  return {
    driver_code: ghostCodeFor(ghost.driver_code),
    driver_number: 0,
    full_name: "ARIS",
    team: real?.team ?? "",
    team_colour: "#e8eef4",
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
    last_lap_s: extras.last_lap_s ?? null,
    best_lap_s: null,
    pit_stops: ghost.plan_pit_laps?.filter((p) => p > 0 && p <= lap).length ?? 0,
    is_pitted: Boolean(extras.is_pitted),
    is_dnf: false,
    status: extras.is_pitted ? "RUNNING" : "RUNNING",
    path_frac: pathFrac,
    x: extras.x ?? 0,
    y: extras.y ?? 0,
    speed_kph: extras.speed_kph ?? 0,
    heading_rad: extras.heading_rad ?? 0,
    laps_remaining: Math.max(0, totalLaps - lap),
    total_laps: totalLaps,
    is_aris_driver: false,
    ghost_cumulative_delta: delta,
    divergence_lap: ghost.divergence_lap,
    aris_action: ghost.aris_action,
    real_action: ghost.real_action,
    ghost_in_pits: extras.ghost_in_pits,
    ghost_pit_compound: extras.ghost_pit_compound,
    ghost_skip_seek_jump: extras.ghost_skip_seek_jump,
    laps_completed: lap,
  };
}

/** Place the ghost from its own simulated lap times (playback) — never from the real car. */
export function ghostCarFromTick(
  ghost: GhostTickData,
  real: CarState | null,
  lap: number,
  totalLaps: number,
  playback?: GhostPlayback | null,
): CarState {
  const pb = playback;
  const ghostLap = pb?.lap ?? lap;
  const pathFrac = pb?.path_frac ?? 0;
  const lapS = pb && Number.isFinite(pb.T) && pb.progress_within_lap > 0
    ? pb.T / Math.max(1e-6, pb.progress_within_lap)
    : NaN;
  const speed = Number.isFinite(lapS) && lapS > 1 ? Math.min(360, (5000 / lapS) * 3.6) : 0;
  return carFromGhost(ghost, real, ghostLap, totalLaps, pathFrac, {
    is_pitted: Boolean(pb?.inPits),
    ghost_in_pits: Boolean(pb?.inPits),
    ghost_pit_compound: pb?.pitCompound ?? null,
    ghost_skip_seek_jump: Boolean(pb?.skipSeekJump),
    last_lap_s: null,
    speed_kph: speed,
    x: 0,
    y: 0,
  });
}

/** Fallback ghost so the map/tower still show ARIS vs real before DB precompute lands. */
export function syntheticGhostCar(
  rec: ARISRecommendation,
  real: CarState,
  lap: number,
  totalLaps: number,
  playback?: GhostPlayback | null,
): CarState {
  const delta = rec.delta_vs_stay_out_s;
  const compound = rec.action.pit_compound ?? real.compound;
  const pathFrac = playback?.path_frac ?? 0;
  return {
    ...real,
    driver_code: ghostCodeFor(real.driver_code),
    driver_number: 0,
    full_name: "ARIS",
    team_colour: "#e8eef4",
    compound,
    tyre_life: rec.action.kind === "stay_out" ? real.tyre_life : 0,
    last_lap_s: null,
    best_lap_s: null,
    path_frac: pathFrac,
    x: 0,
    y: 0,
    ghost_cumulative_delta: -delta,
    divergence_lap: rec.lap,
    aris_action: rec.label,
    real_action: "LIVE",
    is_pitted: Boolean(playback?.inPits),
    ghost_in_pits: Boolean(playback?.inPits),
    ghost_pit_compound: playback?.pitCompound ?? null,
    ghost_skip_seek_jump: Boolean(playback?.skipSeekJump),
  };
}

/**
 * Minimal GhostDelta-panel data derived from a live recommendation, so the
 * chart agrees with the synthetic map-dot from `syntheticGhostCar` instead of
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

export function ghostLastLapS(ghostLapS: number[], lastCompletedLap: number): number | null {
  const v = ghostLapS[lastCompletedLap];
  return Number.isFinite(v) && v > 0 ? v : null;
}
