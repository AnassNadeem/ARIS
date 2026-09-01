import { lerpFrac, wrap01 } from "@/lib/trackGeometry";

/** GPS correction half-width in laps. Outside this, the sample is discarded. */
export const GPS_CORR_EPSILON = 0.015;
/** Live polls are slower; allow a slightly wider GPS nudge. */
export const GPS_CORR_EPSILON_LIVE = 0.02;

/** lapFrac below this is still "on the grid" (matches orderTimingTower lights-out). */
export const GRID_START_LAP_FRAC = 0.02;
/** Grid slot stagger behind the S/F line so cars are not a single stacked blob. */
export const GRID_SLOT_FRAC = 0.0035;
/** Blend grid → timing over this many laps (~3 s of a 90 s lap). */
export const GRID_BLEND_LAPS = 0.035;

export const DEFAULT_EXPECTED_LAP_S = 90;
export const TICK_INTERP_CAP_MS = 250;
/** 1×: tick timer jitter is often >250ms; a matching cap parks the dots. */
export const TICK_INTERP_CAP_1X_MS = 500;

export interface TimingPathInput {
  lapNumber: number;
  timeSinceLapStartS: number;
  expectedLapTimeS: number;
}

/**
 * Along-track fraction from classified timing only. No GPS.
 * frac_within_lap = clamp(time_since_lap_start / expected_lap_time, 0, 1)
 * path_frac = (lap_number - 1 + frac_within_lap) mod 1
 */
export function computeTimingPathFrac(input: TimingPathInput): number {
  const expected =
    Number.isFinite(input.expectedLapTimeS) && input.expectedLapTimeS > 1
      ? input.expectedLapTimeS
      : DEFAULT_EXPECTED_LAP_S;
  const t = Number.isFinite(input.timeSinceLapStartS) ? input.timeSinceLapStartS : 0;
  const fracWithin = Math.max(0, Math.min(1, t / expected));
  const lapN = Number.isFinite(input.lapNumber) ? input.lapNumber : 1;
  return wrap01(lapN - 1 + fracWithin);
}

export function gridPathFrac(gridPosition: number | null | undefined): number {
  const slot = gridPosition != null && gridPosition > 0 ? gridPosition : 1;
  return wrap01(0 - (slot - 1) * GRID_SLOT_FRAC);
}

/** Hold the staggered S/F grid, then lerp onto the timing-derived target. */
export function blendedPathFrac(
  targetFrac: number,
  gridPosition: number | null | undefined,
  lapFrac: number,
): number {
  const gridFrac = gridPathFrac(gridPosition);
  if (!Number.isFinite(lapFrac) || lapFrac < GRID_START_LAP_FRAC) return gridFrac;
  const blendEnd = GRID_START_LAP_FRAC + GRID_BLEND_LAPS;
  if (lapFrac >= blendEnd) return wrap01(targetFrac);
  const t = (lapFrac - GRID_START_LAP_FRAC) / GRID_BLEND_LAPS;
  return lerpFrac(gridFrac, targetFrac, t);
}

/**
 * Bounded GPS correction on a timing term.
 * |gps - timing| > epsilon → discard GPS and use timing alone (do not hold/freeze).
 * Direction always comes from timing; no >0.5-as-reverse wrap.
 */
export function correctPathFrac(
  timingFrac: number,
  gpsFrac: number | null | undefined,
  epsilon: number = GPS_CORR_EPSILON,
): number {
  const timing = wrap01(timingFrac);
  if (gpsFrac == null || !Number.isFinite(gpsFrac)) return timing;
  const gps = wrap01(gpsFrac);
  const d = gps - timing;
  if (Math.abs(d) > epsilon) return timing;
  return wrap01(timing + Math.max(-epsilon, Math.min(epsilon, d)));
}

export function displayPathFrac(opts: {
  timingFrac: number;
  gpsFrac?: number | null;
  gridPosition?: number | null;
  raceLapFrac: number;
  epsilon?: number;
}): number {
  const corrected = correctPathFrac(opts.timingFrac, opts.gpsFrac, opts.epsilon ?? GPS_CORR_EPSILON);
  return blendedPathFrac(corrected, opts.gridPosition, opts.raceLapFrac);
}

/** Shared replay clock: store elapsed + capped interpolation since the last 250ms tick. */
export function replayDisplayElapsed(
  storeElapsedS: number,
  lastTickPerfTime: number,
  nowPerf: number,
  playing: boolean,
  playbackSpeed: number,
): number {
  const base = Number.isFinite(storeElapsedS) ? storeElapsedS : 0;
  if (!playing || !(lastTickPerfTime > 0)) return base;
  const speed = Number.isFinite(playbackSpeed) && playbackSpeed > 0 ? playbackSpeed : 1;
  const cap = speed <= 1 ? TICK_INTERP_CAP_1X_MS : TICK_INTERP_CAP_MS;
  const extraMs = Math.min(Math.max(0, nowPerf - lastTickPerfTime), cap);
  return base + (extraMs / 1000) * speed;
}

export function expectedLapTimeS(lapTimes: Array<number | null | undefined>, fallback = DEFAULT_EXPECTED_LAP_S): number {
  const valid = lapTimes.filter((v): v is number => v != null && Number.isFinite(v) && v > 30 && v < 180);
  if (!valid.length) return fallback;
  return valid[valid.length - 1];
}

export function rollingAverageLapS(lapTimes: Array<number | null | undefined>, fallback = DEFAULT_EXPECTED_LAP_S): number {
  const valid = lapTimes.filter((v): v is number => v != null && Number.isFinite(v) && v > 30 && v < 180);
  if (!valid.length) return fallback;
  const n = Math.min(3, valid.length);
  const slice = valid.slice(-n);
  return slice.reduce((a, b) => a + b, 0) / slice.length;
}
