import { buildPath, pointAtFraction, wrap01 } from "@/lib/trackGeometry";
import {
  DEFAULT_EXPECTED_LAP_S,
  GPS_CORR_EPSILON,
  GRID_BLEND_LAPS,
  GRID_SLOT_FRAC,
  GRID_START_LAP_FRAC,
  blendedPathFrac,
  computeTimingPathFrac,
  displayPathFrac,
  expectedLapTimeS,
  gridPathFrac,
  rollingAverageLapS,
} from "@/lib/timingPath";
import type {
  ApiLapRow,
  ApiStintRow,
  DriverListing,
  GhostData,
  GhostR2Tick,
  GhostTickData,
  LivePosition,
  LiveTimingRow,
  RaceField,
  RaceFieldPosSample,
  StratPlan,
} from "@/lib/types";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";

export {
  GPS_CORR_EPSILON,
  GRID_BLEND_LAPS,
  GRID_SLOT_FRAC,
  GRID_START_LAP_FRAC,
  blendedPathFrac,
  computeTimingPathFrac,
  displayPathFrac,
  gridPathFrac,
};

export const R2_LOAD_ERROR = "Failed to load race data — check R2 connection";
export const R2_RACE_UNAVAILABLE = "Race data unavailable — check back soon";
const FETCH_TIMEOUT_MS = 30_000;

/** Thrown when race_field.json (or another R2 pack file) returns HTTP 404. */
export class RaceFieldNotFoundError extends Error {
  readonly status = 404 as const;
  constructor() {
    super(R2_RACE_UNAVAILABLE);
    this.name = "RaceFieldNotFoundError";
  }
}

export function r2FetchErrorMessage(err: unknown): string {
  if (err instanceof RaceFieldNotFoundError) return R2_RACE_UNAVAILABLE;
  if (err instanceof Error && (/\b404\b/.test(err.message) || err.message === R2_RACE_UNAVAILABLE)) {
    return R2_RACE_UNAVAILABLE;
  }
  return R2_LOAD_ERROR;
}

/**
 * Keep same-origin relative paths as-is. Turbopack may inline
 * NEXT_PUBLIC_R2_BASE_URL=/r2replay as http://127.0.0.1:3000/r2replay, which
 * CORS-fails when the tab is on http://localhost:3000.
 */
export function normalizeR2Base(raw: string | undefined | null): string {
  const trimmed = (raw || "").trim().replace(/\/$/, "");
  if (!trimmed) return "";
  if (trimmed.startsWith("/")) return trimmed;
  try {
    const u = new URL(trimmed);
    if (u.hostname === "localhost" || u.hostname === "127.0.0.1") {
      return u.pathname.replace(/\/$/, "") || "/r2replay";
    }
    return `${u.origin}${u.pathname === "/" ? "" : u.pathname}`.replace(/\/$/, "");
  } catch {
    return trimmed;
  }
}

const R2_BASE = normalizeR2Base(
  process.env.NEXT_PUBLIC_R2_BASE_URL ||
    // next dev rewrites /r2replay → the public R2 bucket. Without this,
    // `npm run dev` never fetches ghost_*.json and the tower/Ghost Delta stay empty.
    (process.env.NODE_ENV === "development" ? "/r2replay" : ""),
);
/** Bump when race_field.json shape changes so CDN/browser caches cannot serve stale packs. */
const R2_ASSET_V = "4";
const DEFAULT_TRACK_M = 5000;
const SPEED_DT_LAP = 0.04;

const driverCumCache = new WeakMap<RaceField, Map<string, number[]>>();
const driverLapTimesCache = new WeakMap<RaceField, Map<string, number[]>>();

function driverLapTimes(field: RaceField): Map<string, number[]> {
  const hit = driverLapTimesCache.get(field);
  if (hit) return hit;
  const maxLap = field.meta.total_laps;
  const by = new Map<string, number[]>();
  for (const d of field.drivers) by.set(d.code, new Array(maxLap + 1).fill(NaN));
  for (const row of field.laps) {
    if (row.lap < 1 || row.lap > maxLap) continue;
    let arr = by.get(row.driver);
    if (!arr) {
      arr = new Array(maxLap + 1).fill(NaN);
      by.set(row.driver, arr);
    }
    if (row.lap_time_s != null && Number.isFinite(row.lap_time_s)) arr[row.lap] = row.lap_time_s;
  }
  driverLapTimesCache.set(field, by);
  return by;
}

function driverCumulatives(field: RaceField): Map<string, number[]> {
  const hit = driverCumCache.get(field);
  if (hit) return hit;
  const maxLap = field.meta.total_laps;
  const times = driverLapTimes(field);
  const cums = new Map<string, number[]>();
  for (const [code, laps] of times) {
    const cum = new Array(maxLap + 1).fill(0);
    for (let lap = 1; lap <= maxLap; lap++) {
      const t = laps[lap];
      const step = Number.isFinite(t) && t > 0 ? t : DEFAULT_EXPECTED_LAP_S;
      cum[lap] = cum[lap - 1] + step;
    }
    cums.set(code, cum);
  }
  driverCumCache.set(field, cums);
  return cums;
}

/** Classified timing path_frac for one driver at a replay clock instant. */
export function timingFracFromField(field: RaceField, code: string, elapsedS: number): number {
  const maxLap = Math.max(1, field.meta.total_laps);
  const cum = driverCumulatives(field).get(code);
  const laps = driverLapTimes(field).get(code) ?? [];
  const t = Number.isFinite(elapsedS) ? Math.max(0, elapsedS) : 0;
  let lapNumber = 1;
  if (cum && cum.length > 1) {
    lapNumber = maxLap + 1;
    for (let lap = 1; lap <= maxLap; lap++) {
      if (t < cum[lap]) {
        lapNumber = lap;
        break;
      }
    }
  }
  const prevCum = cum ? cum[Math.max(0, Math.min(maxLap, lapNumber - 1))] ?? 0 : (lapNumber - 1) * DEFAULT_EXPECTED_LAP_S;
  const timeSince = Math.max(0, t - prevCum);
  const completed = laps.filter((v, i) => i > 0 && i < lapNumber && Number.isFinite(v));
  const expected =
    lapNumber <= 1 ? rollingAverageLapS(completed) : expectedLapTimeS(completed, rollingAverageLapS(completed));
  return computeTimingPathFrac({
    lapNumber,
    timeSinceLapStartS: timeSince,
    expectedLapTimeS: expected,
  });
}

/** Along-track fraction for a driver at a replay clock instant (rAF display path). */
export function replayDisplayFrac(field: RaceField, code: string, elapsedS: number): number {
  const { lapFrac } = elapsedToLap(field, elapsedS);
  const timing = timingFracFromField(field, code, elapsedS);
  const samples = posSamplesFor(field, code);
  const gps = pathFracAtLap(samples, lapFrac, field.meta.total_laps);
  const drv = field.drivers.find((d) => d.code === code);
  return displayPathFrac({
    timingFrac: timing,
    gpsFrac: Number.isFinite(gps) ? gps : null,
    gridPosition: drv?.grid_position,
    raceLapFrac: lapFrac,
  });
}

export function r2BaseUrl(): string {
  return R2_BASE;
}

export function r2Configured(): boolean {
  return Boolean(R2_BASE);
}

const raceFieldPromises = new Map<string, Promise<RaceField>>();

function raceFieldCacheKey(year: number, round: number): string {
  return `${year}/${round}`;
}

/** HEAD race_field.json. `false` = confirmed 404; `null` = unknown (keep the race). */
export async function raceFieldExists(year: number, round: number): Promise<boolean | null> {
  if (!R2_BASE) return null;
  try {
    const res = await fetch(r2Url(year, round, "race_field.json"), {
      method: "HEAD",
      signal: AbortSignal.timeout(8000),
    });
    if (res.status === 404) return false;
    if (res.ok) return true;
    return null;
  } catch {
    return null;
  }
}

/** Prefer this race's race_field.json drivers; never a global mock grid. */
export function driversFromRaceOrGrid(
  grid: DriverListing[],
  field: RaceField | null | undefined,
): DriverListing[] {
  if (field?.drivers?.length) return fieldToDrivers(field);
  return grid;
}

function r2Url(year: number, round: number, file: string): string {
  return `${R2_BASE}/replay/${year}/${round}/${file}?v=${R2_ASSET_V}`;
}

export async function fetchWithProgress(
  url: string,
  onProgress?: (loaded: number, total: number | null) => void,
): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (res.status === 404) throw new RaceFieldNotFoundError();
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    if (!onProgress || !res.body) return res;
    const total = Number(res.headers.get("content-length") || 0) || null;
    const reader = res.body.getReader();
    const chunks: Uint8Array[] = [];
    let loaded = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      if (value) {
        chunks.push(value);
        loaded += value.byteLength;
        onProgress(loaded, total);
      }
    }
    const body = new Blob(chunks as BlobPart[]);
    return new Response(body, { headers: res.headers, status: res.status });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`Timed out after ${FETCH_TIMEOUT_MS / 1000}s`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchRaceField(
  year: number,
  round: number,
  onProgress?: (loaded: number, total: number | null) => void,
): Promise<RaceField> {
  if (!R2_BASE) throw new Error("R2 base URL unset");
  const key = raceFieldCacheKey(year, round);
  const cached = raceFieldPromises.get(key);
  if (cached) {
    const field = await cached;
    onProgress?.(1, 1);
    return field;
  }
  const pending = (async () => {
    try {
      const res = await fetchWithProgress(r2Url(year, round, "race_field.json"), onProgress);
      return (await res.json()) as RaceField;
    } catch (err) {
      raceFieldPromises.delete(key);
      throw err;
    }
  })();
  raceFieldPromises.set(key, pending);
  return pending;
}

export async function fetchGhost(
  year: number,
  round: number,
  driver: string,
  onProgress?: (loaded: number, total: number | null) => void,
): Promise<GhostData | null> {
  if (!R2_BASE) return null;
  const code = driver.toUpperCase();
  try {
    const res = await fetchWithProgress(r2Url(year, round, `ghost_${code}.json`), onProgress);
    if (!res.ok) return null;
    return (await res.json()) as GhostData;
  } catch {
    return null;
  }
}

export function plansMatch(a: StratPlan | null | undefined, b: GhostData | null | undefined): boolean {
  if (!a || !b) return false;
  const ap = [...(a.pit_laps || [])].sort((x, y) => x - y);
  const bp = [...(b.strategy.pit_laps || [])].sort((x, y) => x - y);
  if (ap.length !== bp.length) return false;
  return ap.every((v, i) => v === bp[i]);
}

export function ghostTicksMap(ghost: GhostData | null): Record<number, GhostR2Tick> {
  const out: Record<number, GhostR2Tick> = {};
  for (const t of ghost?.ticks || []) out[t.lap] = t;
  return out;
}

export function r2TickToGhostTick(tick: GhostR2Tick, driver: string, ghost: GhostData | null): GhostTickData {
  const history = (ghost?.ticks || [])
    .filter((t) => t.lap > 0 && t.lap <= tick.lap)
    .sort((a, b) => a.lap - b.lap)
    .map((t) => ({
      lap: t.lap,
      delta: t.cumulative_delta_s,
      ghost_pos: t.position,
      real_pos: 0,
    }));
  return {
    driver_code: driver,
    divergence_lap: 1,
    aris_action: tick.aris_action,
    real_action: ghost?.outcome.real_action || "STAY_OUT",
    ghost_tyre: (tick.compound as GhostTickData["ghost_tyre"]) || "HARD",
    ghost_tyre_age: tick.tyre_life,
    ghost_position: tick.position,
    ghost_cumulative_delta: tick.cumulative_delta_s,
    gap_to_leader_s: tick.gap_to_leader_s,
    active: true,
    outcome: (ghost?.outcome.verdict as GhostTickData["outcome"]) ?? null,
    delta_history: history,
    ghost_compound: (tick.compound as GhostTickData["ghost_compound"]) || "HARD",
    from_lap_one: true,
    plan_pit_laps: ghost?.strategy.pit_laps,
    plan_pit_compounds: ghost?.strategy.compounds as GhostTickData["plan_pit_compounds"],
  };
}

export function ghostDeltaChartPoints(
  ghostData: GhostTickData | null,
  ghostTicks: Record<number, GhostR2Tick>,
  currentLap: number,
): { lap: number; delta: number }[] {
  const cap = Math.max(1, currentLap);
  if (ghostData?.delta_history?.length) {
    return ghostData.delta_history
      .filter((pt) => pt.lap <= cap)
      .map((pt) => ({ lap: pt.lap, delta: pt.delta }));
  }
  return Object.values(ghostTicks)
    .filter((t) => t.lap <= cap)
    .sort((a, b) => a.lap - b.lap)
    .map((t) => ({ lap: t.lap, delta: t.cumulative_delta_s }));
}

/** Fallback when a circuit YAML pit_loss_s is not in the lookup. */
export const DEFAULT_PIT_LOSS_S = 22;

/**
 * pit_loss_s copied from data/tracks/*.yaml (name + round_aliases).
 * Used for the ghost pit-hide window — not re-added into ghost_lap_s
 * (pit loss is already inside the cumulative_delta_s step on pit laps).
 */
const PIT_LOSS_BY_CIRCUIT: Record<string, number> = {
  bahrain: 21.8,
  sakhir: 21.8,
  "saudi arabia": 17.7,
  jeddah: 17.7,
  australia: 14.3,
  melbourne: 14.3,
  "albert park": 14.3,
  japan: 21.6,
  suzuka: 21.6,
  china: 17.4,
  shanghai: 17.4,
  miami: 13.3,
  "emilia romagna": 21.4,
  imola: 21.4,
  monaco: 19.2,
  "monte carlo": 19.2,
  canada: 16.1,
  montreal: 16.1,
  "circuit gilles villeneuve": 16.1,
  spain: 19.0,
  barcelona: 19.0,
  catalunya: 19.0,
  austria: 17.5,
  spielberg: 17.5,
  "red bull ring": 17.5,
  britain: 18.7,
  silverstone: 18.7,
  hungary: 18.5,
  hungaroring: 18.5,
  budapest: 18.5,
  belgium: 14.6,
  spa: 14.6,
  "spa francorchamps": 14.6,
  netherlands: 18.5,
  zandvoort: 18.5,
  "circuit zandvoort": 18.5,
  italy: 21.3,
  monza: 21.3,
  azerbaijan: 17.7,
  baku: 17.7,
  singapore: 15.8,
  marina: 15.8,
  "marina bay": 15.8,
  "united states": 20.1,
  austin: 20.1,
  cota: 20.1,
  mexico: 19.1,
  "mexico city": 19.1,
  brazil: 18.5,
  "sao paulo": 18.5,
  interlagos: 18.5,
  "las vegas": 15.8,
  vegas: 15.8,
  qatar: 23.0,
  losail: 23.0,
  "abu dhabi": 21.8,
  yas: 21.8,
  france: 13.8,
  "paul ricard": 13.8,
  portugal: 22.2,
  portimao: 22.2,
  turkey: 20.3,
  istanbul: 20.3,
  russia: 20.5,
  sochi: 20.5,
  hockenheim: 19.3,
  mugello: 16.6,
  nurburgring: 20.8,
  "nürburgring": 20.8,
};

function normCircuitKey(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

/** Circuit YAML pit_loss_s, or 22s if the name is unknown. */
export function pitLossForCircuit(circuitName: string | null | undefined): number {
  if (!circuitName) return DEFAULT_PIT_LOSS_S;
  const key = normCircuitKey(circuitName);
  if (PIT_LOSS_BY_CIRCUIT[key] != null) return PIT_LOSS_BY_CIRCUIT[key];
  for (const [alias, loss] of Object.entries(PIT_LOSS_BY_CIRCUIT)) {
    if (key.includes(alias) || alias.includes(key)) return loss;
  }
  return DEFAULT_PIT_LOSS_S;
}

/** real_lap_s[L] from race_field.json for one driver. Index 0 unused. */
export function realLapTimesByDriver(field: RaceField, driver: string): number[] {
  const code = driver.toUpperCase();
  const maxLap = field.meta.total_laps;
  const out: number[] = new Array(maxLap + 1).fill(NaN);
  for (const row of field.laps) {
    if (row.driver.toUpperCase() !== code) continue;
    if (row.lap < 1 || row.lap > maxLap) continue;
    if (row.lap_time_s != null && Number.isFinite(row.lap_time_s)) out[row.lap] = row.lap_time_s;
  }
  return out;
}

/** Red-flag / formation laps above this are clamped for path_frac and cumulative. */
export const GHOST_LAP_CLAMP_S = 300;

export interface GhostLapDerived {
  /** ghost_lap_s[L] = real_lap_s[L] - (delta[L] - delta[L-1]). Index 0 unused. Capped at GHOST_LAP_CLAMP_S. */
  ghost_lap_s: number[];
  /** ghost_cumulative_s[L] = sum of (clamped) ghost_lap_s[1..L]. [0] = 0. */
  ghost_cumulative_s: number[];
  implausible_laps: { lap: number; ghost_lap_s: number; real_lap_s: number; delta_step_s: number }[];
}

/** Median of finite numbers. Empty → NaN. */
export function medianFinite(values: number[]): number {
  const xs = values.filter((v) => Number.isFinite(v)).sort((a, b) => a - b);
  if (!xs.length) return NaN;
  const mid = Math.floor(xs.length / 2);
  return xs.length % 2 ? xs[mid] : (xs[mid - 1] + xs[mid]) / 2;
}

/**
 * Derive per-lap ghost times from R2 ticks + race_field real lap times.
 * Pit loss is already inside delta steps on pit laps — do not add it again.
 * Values above GHOST_LAP_CLAMP_S are clamped (red flag / formation) before path_frac
 * and cumulative use. Negatives are stored as-is and listed in implausible_laps.
 * NaN laps (null real lap_time_s) are filled with the median of finite ghost_lap_s
 * so cumulative time stays monotonic and playback never freezes.
 */
export function deriveGhostLapTimes(ticks: GhostR2Tick[], realLapS: number[]): GhostLapDerived {
  const byLap = new Map<number, GhostR2Tick>();
  let maxTickLap = 0;
  for (const t of ticks) {
    if (t.lap < 1) continue;
    byLap.set(t.lap, t);
    if (t.lap > maxTickLap) maxTickLap = t.lap;
  }
  const maxLap = Math.max(maxTickLap, Math.max(0, realLapS.length - 1));
  const ghost_lap_s: number[] = new Array(maxLap + 1).fill(NaN);
  const ghost_cumulative_s: number[] = new Array(maxLap + 1).fill(0);
  const implausible_laps: GhostLapDerived["implausible_laps"] = [];
  let prevDelta = 0;
  for (let L = 1; L <= maxLap; L++) {
    const tick = byLap.get(L);
    const delta = tick != null && Number.isFinite(tick.cumulative_delta_s) ? tick.cumulative_delta_s : prevDelta;
    const step = delta - prevDelta;
    const real = realLapS[L];
    let ghostLap = Number.isFinite(real) ? real - step : NaN;
    if (Number.isFinite(ghostLap) && ghostLap > GHOST_LAP_CLAMP_S) {
      console.warn(
        `[ARIS ghost] clamped ghost_lap_s lap ${L} from ${ghostLap}s to ${GHOST_LAP_CLAMP_S}s (red flag / abnormal lap)`,
      );
      implausible_laps.push({ lap: L, ghost_lap_s: ghostLap, real_lap_s: real, delta_step_s: step });
      ghostLap = GHOST_LAP_CLAMP_S;
    }
    ghost_lap_s[L] = ghostLap;
    if (Number.isFinite(ghostLap) && ghostLap <= 0) {
      implausible_laps.push({ lap: L, ghost_lap_s: ghostLap, real_lap_s: real, delta_step_s: step });
    }
    prevDelta = delta;
  }

  const finitePositive = ghost_lap_s.filter((v, i) => i > 0 && Number.isFinite(v) && v > 0);
  let fill = medianFinite(finitePositive);
  if (!(fill > 0)) {
    fill = medianFinite(realLapS.filter((v) => Number.isFinite(v) && v > 0));
  }
  if (!(fill > 0)) fill = 90;
  for (let L = 1; L <= maxLap; L++) {
    if (!Number.isFinite(ghost_lap_s[L])) {
      ghost_lap_s[L] = fill;
    }
  }

  let cum = 0;
  for (let L = 1; L <= maxLap; L++) {
    const g = ghost_lap_s[L];
    const step = Number.isFinite(g) ? g : fill;
    const next = cum + step;
    if (!(next > cum)) {
      console.warn(
        `[ARIS ghost] non-monotonic ghost_cumulative_s at lap ${L}: ${next} ≰ ${cum}; clamping`,
      );
      cum += fill > 0 ? fill : 1e-3;
    } else {
      cum = next;
    }
    ghost_cumulative_s[L] = cum;
  }
  return { ghost_lap_s, ghost_cumulative_s, implausible_laps };
}

function msFromSec(v: number | null | undefined): number | null {
  return v != null && Number.isFinite(v) ? Math.round(v * 1000) : null;
}

export function fieldToLapRows(field: RaceField): ApiLapRow[] {
  return field.laps.map((r) => {
    let s1 = r.sector_1_s;
    let s2 = r.sector_2_s;
    let s3 = r.sector_3_s;
    if (s1 == null || s2 == null || s3 == null) {
      const derived = sectorSecondsForLap(
        posSamplesFor(field, r.driver),
        r.lap,
        r.lap_time_s ?? 0,
        field.meta.total_laps,
      );
      s1 = s1 ?? derived.s1;
      s2 = s2 ?? derived.s2;
      s3 = s3 ?? derived.s3;
    }
    return {
      driver_code: r.driver,
      lap_number: r.lap,
      lap_time_ms: r.lap_time_s != null ? Math.round(r.lap_time_s * 1000) : null,
      sector1_ms: msFromSec(s1),
      sector2_ms: msFromSec(s2),
      sector3_ms: msFromSec(s3),
      compound: r.compound,
      tyre_life: r.tyre_life,
      pit_in_lap: r.pit_this_lap,
      pit_out_lap: false,
      position: r.position,
      track_status: r.track_status,
    };
  });
}

export function fieldToStintRows(field: RaceField): ApiStintRow[] {
  return field.stints.map((s) => ({
    driver_code: s.driver,
    stint_number: s.stint,
    compound: s.compound,
    lap_start: s.lap_start,
    lap_end: s.lap_end,
    total_laps: Math.max(0, s.lap_end - s.lap_start + 1),
    average_lap_ms: null,
  }));
}

export function fieldToDrivers(field: RaceField): DriverListing[] {
  return field.drivers.map((d, i) => ({
    driver_number: d.number ?? i + 1,
    driver_code: d.code,
    full_name: d.name,
    team: d.team,
    team_colour: d.colour,
  }));
}

function leaderCum(field: RaceField): number[] {
  const total = field.meta.total_laps;
  const cum: number[] = [0];
  for (let lap = 1; lap <= total; lap++) {
    const rows = field.laps.filter((r) => r.lap === lap && r.lap_time_s);
    const leader = rows.reduce<number | null>((best, r) => {
      const t = r.lap_time_s;
      if (t == null) return best;
      return best == null || t < best ? t : best;
    }, null);
    cum.push((cum[lap - 1] || 0) + (leader ?? 90));
  }
  return cum;
}

export function raceDurationS(field: RaceField): number {
  const cum = leaderCum(field);
  return cum[field.meta.total_laps] ?? field.meta.total_laps * 90;
}

export function lapToElapsed(field: RaceField, lap: number): number {
  const cum = leaderCum(field);
  if (lap > field.meta.total_laps) return raceDurationS(field);
  const idx = Math.max(1, Math.min(field.meta.total_laps, Math.floor(lap)));
  return cum[idx - 1] ?? (idx - 1) * 90;
}

export function elapsedToLap(field: RaceField, elapsedS: number): { lap: number; lapFrac: number } {
  const cum = leaderCum(field);
  const total = Math.max(1, field.meta.total_laps);
  if (elapsedS <= 0) return { lap: 1, lapFrac: 0 };
  for (let lap = 1; lap <= total; lap++) {
    if (elapsedS < cum[lap]) {
      const dur = Math.max(1, cum[lap] - cum[lap - 1]);
      const into = elapsedS - cum[lap - 1];
      return { lap, lapFrac: lap - 1 + Math.min(0.999, into / dur) };
    }
  }
  return { lap: total, lapFrac: total };
}

/** Nearest-neighbour pos_sample by lap_frac. Tie → earlier sample. */
export function nearestPosSample<T extends { lap_frac: number; path_frac: number }>(
  samples: T[],
  lapFrac: number,
): T | null {
  if (!samples.length) return null;
  let lo = 0;
  let hi = samples.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (samples[mid].lap_frac < lapFrac) lo = mid + 1;
    else hi = mid;
  }
  let best = lo;
  if (lo > 0) {
    const dPrev = Math.abs(samples[lo - 1].lap_frac - lapFrac);
    const dCur = Math.abs(samples[lo].lap_frac - lapFrac);
    if (dPrev <= dCur) best = lo - 1;
  }
  return samples[best];
}

/**
 * Linear interpolation of path_frac between the two pos_samples that
 * bracket `lapFrac`. Clamps to first/last sample outside the range.
 * S/F wrap (negative jump > 0.5) stays forward; the old ">0.5 = reverse"
 * heuristic is gone — direction comes from the monotonic timing term.
 */
export function interpolatedPosFrac(
  samples: { lap_frac: number; path_frac: number }[],
  lapFrac: number,
): number {
  if (!samples.length) return 0;
  const last = samples[samples.length - 1];
  if (!Number.isFinite(lapFrac) || lapFrac >= last.lap_frac) return last.path_frac;
  if (lapFrac <= samples[0].lap_frac) return samples[0].path_frac;
  let lo = 0;
  let hi = samples.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (samples[mid].lap_frac <= lapFrac) lo = mid + 1;
    else hi = mid;
  }
  const next = samples[lo];
  const prev = samples[lo - 1];
  if (!prev || !next) return last.path_frac;
  const span = next.lap_frac - prev.lap_frac;
  if (span <= 0) return prev.path_frac;
  const t = (lapFrac - prev.lap_frac) / span;
  let dp = next.path_frac - prev.path_frac;
  if (dp < -0.5) dp += 1;
  const mixed = wrap01(prev.path_frac + t * dp);
  return Number.isFinite(mixed) ? mixed : last.path_frac;
}

export function pathFracAtLap(
  samples: { lap_frac: number; path_frac: number }[],
  lapFrac: number,
  totalLaps = 0,
): number {
  if (!samples.length) return 0;
  const span = samples[samples.length - 1].lap_frac - samples[0].lap_frac;
  // Broken R2 builds stored every sample at lap_frac=0. Index by race progress.
  if (Math.abs(span) < 1e-9 && totalLaps > 0 && samples.length > 1) {
    const u = Math.max(0, Math.min(1, lapFrac / totalLaps));
    return samples[Math.round(u * (samples.length - 1))].path_frac;
  }
  return interpolatedPosFrac(samples, lapFrac);
}

function wrappedPathDelta(from: number, to: number): number {
  let d = to - from;
  if (d > 0.5) d -= 1;
  if (d < -0.5) d += 1;
  return d;
}

export function speedKphFromPath(
  samples: { lap_frac: number; path_frac: number; speed_kph?: number | null }[],
  lapFrac: number,
  lapDurS: number,
  totalLaps = 0,
  trackLengthM = DEFAULT_TRACK_M,
): number {
  const hit = nearestPosSample(samples, lapFrac);
  if (hit && hit.speed_kph != null && hit.speed_kph > 1) {
    return Math.min(360, hit.speed_kph);
  }
  if (samples.length < 2 || !(lapDurS > 0) || !(trackLengthM > 0)) return 0;
  const a = pathFracAtLap(samples, lapFrac, totalLaps);
  let dtLap = SPEED_DT_LAP;
  let b = pathFracAtLap(samples, lapFrac + dtLap, totalLaps);
  if (a === b) {
    dtLap = 0.12;
    b = pathFracAtLap(samples, lapFrac + dtLap, totalLaps);
  }
  const dp = wrappedPathDelta(a, b);
  const dtS = dtLap * lapDurS;
  if (dtS >= 1e-4 && dp > 0) {
    const kph = ((dp * trackLengthM) / dtS) * 3.6;
    if (Number.isFinite(kph) && kph >= 1) return Math.min(360, kph);
  }
  // GPS path can sit still (projection holes). After lights-out, fall back to
  // lap-average so the HUD is not stuck on "—".
  if (lapFrac < GRID_START_LAP_FRAC) return 0;
  return Math.min(360, (trackLengthM / lapDurS) * 3.6);
}

function firstPathCrossing(
  samples: { lap_frac: number; path_frac: number }[],
  fromLapFrac: number,
  toLapFrac: number,
  target: number,
  totalLaps: number,
): number | null {
  const span = toLapFrac - fromLapFrac;
  if (span <= 1e-6 || samples.length < 2) return null;
  const steps = 48;
  let prevU = fromLapFrac;
  let prevP = pathFracAtLap(samples, fromLapFrac, totalLaps);
  for (let i = 1; i <= steps; i++) {
    const u = fromLapFrac + (span * i) / steps;
    const p = pathFracAtLap(samples, u, totalLaps);
    const d = wrappedPathDelta(prevP, p);
    if (d > 1e-6) {
      const toT = (target - prevP + 1) % 1;
      if (toT > 1e-6 && toT <= d + 1e-6) {
        return prevU + (toT / d) * (u - prevU);
      }
    }
    prevU = u;
    prevP = p;
  }
  return null;
}

export function sectorSecondsForLap(
  samples: { lap_frac: number; path_frac: number }[],
  lap: number,
  lapTimeS: number,
  totalLaps: number,
): { s1: number | null; s2: number | null; s3: number | null } {
  if (!(lapTimeS > 0) || lap < 1 || samples.length < 2) {
    return { s1: null, s2: null, s3: null };
  }
  const start = lap - 1;
  const end = start + 0.999;
  const s1u = firstPathCrossing(samples, start, end, 1 / 3, totalLaps);
  const s2u = firstPathCrossing(samples, start, end, 2 / 3, totalLaps);
  const s1 = s1u != null ? (s1u - start) * lapTimeS : null;
  const s2 = s1 != null && s2u != null ? (s2u - start) * lapTimeS - s1 : null;
  let s3: number | null = null;
  if (s1 != null && s2 != null) {
    s3 = lapTimeS - s1 - s2;
    if (!(s3 > 0.2)) s3 = null;
  }
  return { s1, s2, s3 };
}

function sectorMsFromLap(
  row:
    | {
        sector_1_s?: number | null;
        sector_2_s?: number | null;
        sector_3_s?: number | null;
        lap_time_s?: number | null;
        lap?: number;
      }
    | undefined,
  samples: RaceFieldPosSample[],
  fallbackLap: number,
  totalLaps: number,
): { sector1_ms: number | null; sector2_ms: number | null; sector3_ms: number | null } {
  if (row?.sector_1_s != null || row?.sector_2_s != null || row?.sector_3_s != null) {
    return {
      sector1_ms: msFromSec(row.sector_1_s),
      sector2_ms: msFromSec(row.sector_2_s),
      sector3_ms: msFromSec(row.sector_3_s),
    };
  }
  const which = row?.lap ?? fallbackLap;
  const derived = sectorSecondsForLap(samples, which, row?.lap_time_s ?? 0, totalLaps);
  return {
    sector1_ms: msFromSec(derived.s1),
    sector2_ms: msFromSec(derived.s2),
    sector3_ms: msFromSec(derived.s3),
  };
}

export function posSamplesFor(field: RaceField, code: string): RaceFieldPosSample[] {
  const direct = field.pos_samples[code];
  if (direct?.length) return direct;
  const drv = field.drivers.find((d) => d.code === code);
  const nums = [drv?.number, MOCK_DRIVERS_2025.find((d) => d.driver_code === code)?.driver_number];
  for (const num of nums) {
    if (num == null) continue;
    const byNum = field.pos_samples[String(num)];
    if (byNum?.length) return byNum;
  }
  return [];
}

/** Instantaneous HUD speed for a driver at the replay clock. */
export function driverReplaySpeedKph(field: RaceField, code: string, elapsedS: number): number {
  const { lap, lapFrac } = elapsedToLap(field, elapsedS);
  const cum = leaderCum(field);
  const lapDurS = Math.max(1, (cum[lap] ?? 90) - (cum[lap - 1] ?? 0));
  return speedKphFromPath(posSamplesFor(field, code), lapFrac, lapDurS, field.meta.total_laps);
}

export function ghostTickAtOrBefore(
  ticks: Record<number, GhostR2Tick>,
  lap: number,
): GhostR2Tick | undefined {
  const want = Number.isFinite(lap) ? Math.max(1, Math.floor(lap)) : 1;
  if (ticks[want]) return ticks[want];
  let best: GhostR2Tick | undefined;
  for (const t of Object.values(ticks)) {
    if (!t || t.lap > want) continue;
    if (!best || t.lap > best.lap) best = t;
  }
  return best;
}

function flagFromTrackStatus(status: string | null | undefined): string | null {
  const s = String(status || "");
  if (!s || s === "None" || s === "nan") return null;
  if (s.includes("5")) return "RED";
  if (s.includes("4")) return "SC";
  if (s.includes("6") || s.includes("7")) return "VSC";
  if (s.includes("1") || s.includes("2")) return "GREEN";
  return null;
}

export function r2FrameAt(
  field: RaceField,
  elapsedS: number,
  lapFracOverride?: number,
): {
  lap: number;
  rainfall: boolean;
  sessionFlag: string;
  timing: LiveTimingRow[];
  positions: LivePosition[];
} {
  const { lap, lapFrac: fromElapsed } = elapsedToLap(field, elapsedS);
  const lapFrac = lapFracOverride ?? fromElapsed;
  const wx = field.weather.find((w) => w.lap === lap);
  const path = buildPath(field.outline.x || [], field.outline.y || []);
  const cum = leaderCum(field);
  const lapDurS = Math.max(1, (cum[lap] ?? 90) - (cum[lap - 1] ?? 0));
  const byDriver = new Map<string, (typeof field.laps)[0]>();
  for (const row of field.laps) {
    if (row.lap <= lap) byDriver.set(row.driver, row);
  }
  const colour = new Map(field.drivers.map((d) => [d.code, d.colour]));
  const gridByDriver = new Map(field.drivers.map((d) => [d.code, d.grid_position]));
  const useGrid = lapFrac < GRID_START_LAP_FRAC;
  const pitCount = new Map<string, number>();
  const prevByDriver = new Map<string, (typeof field.laps)[0]>();
  const prevLap = lap - 1;
  for (const row of field.laps) {
    if (row.lap <= lap && row.pit_this_lap) pitCount.set(row.driver, (pitCount.get(row.driver) || 0) + 1);
    if (prevLap >= 1 && row.lap === prevLap) prevByDriver.set(row.driver, row);
  }
  const timing: LiveTimingRow[] = [];
  const positions: LivePosition[] = [];
  for (const [code, row] of byDriver) {
    const samples = posSamplesFor(field, code);
    const gpsRaw = pathFracAtLap(samples, lapFrac, field.meta.total_laps);
    const gps = Number.isFinite(gpsRaw) ? gpsRaw : null;
    const grid = gridByDriver.get(code);
    const frac = displayPathFrac({
      timingFrac: timingFracFromField(field, code, elapsedS),
      gpsFrac: gps,
      gridPosition: grid,
      raceLapFrac: lapFrac,
    });
    const xy = pointAtFraction(path, frac);
    const prev = prevByDriver.get(code);
    const kph = useGrid ? 0 : speedKphFromPath(samples, lapFrac, lapDurS, field.meta.total_laps);
    let sectors = sectorMsFromLap(prev, samples, prevLap, field.meta.total_laps);
    if (sectors.sector1_ms == null && sectors.sector2_ms == null && sectors.sector3_ms == null) {
      sectors = sectorMsFromLap(row, samples, row.lap, field.meta.total_laps);
    }
    const towerPos = useGrid && grid != null && grid > 0 ? grid : (row.position ?? 0);
    timing.push({
      position: towerPos,
      driver_code: code,
      gap_to_leader_s: useGrid ? (grid === 1 ? 0 : null) : row.gap_to_leader_s,
      gap_to_ahead_s: useGrid ? null : row.gap_ahead_s,
      last_lap_ms: useGrid ? null : row.lap_time_s != null ? Math.round(row.lap_time_s * 1000) : null,
      compound: row.compound,
      tyre_life: useGrid ? (row.tyre_life ?? 1) : row.tyre_life,
      pit_count: pitCount.get(code) || 0,
      team_colour: colour.get(code) ?? null,
      in_pit: row.pit_this_lap && row.lap === lap,
      lap_number: useGrid ? 0 : row.lap,
      speed_kph: kph > 1 ? Math.round(kph) : null,
      status: row.is_dnf ? "DNF" : "RUNNING",
      sector1_ms: useGrid ? null : sectors.sector1_ms,
      sector2_ms: useGrid ? null : sectors.sector2_ms,
      sector3_ms: useGrid ? null : sectors.sector3_ms,
    });
    positions.push({
      driver_code: code,
      x: xy.x,
      y: xy.y,
      team_colour: colour.get(code) ?? null,
      is_pitted: Boolean(row.pit_this_lap && row.lap === lap),
      is_dnf: row.is_dnf,
      path_frac: frac,
      speed_ms: kph > 1 ? kph / 3.6 : null,
    });
  }
  const seen = new Set(timing.map((t) => t.driver_code));
  for (const drv of field.drivers) {
    if (seen.has(drv.code)) continue;
    const dns = drv.is_dns !== false;
    const grid = drv.grid_position;
    timing.push({
      position: grid != null && grid > 0 ? grid : 99,
      driver_code: drv.code,
      gap_to_leader_s: null,
      gap_to_ahead_s: null,
      last_lap_ms: null,
      compound: null,
      tyre_life: null,
      pit_count: 0,
      team_colour: drv.colour ?? null,
      in_pit: false,
      lap_number: 0,
      speed_kph: null,
      status: "DNS",
    });
    // DNS cars stay off the map (is_dnf hides the dot).
    if (!dns) continue;
  }
  timing.sort((a, b) => (a.position || 99) - (b.position || 99));
  let flag = "GREEN";
  for (const row of field.laps) {
    if (row.lap !== lap) continue;
    const fromTrack = flagFromTrackStatus(row.track_status);
    if (fromTrack && fromTrack !== "GREEN") {
      flag = fromTrack;
      break;
    }
  }
  for (const msg of field.race_control) {
    if (msg.lap != null && msg.lap > lap) continue;
    const blob = `${msg.flag || ""} ${msg.message || ""} ${msg.category || ""}`.toUpperCase();
    if (blob.includes("RED")) flag = "RED";
    else if (blob.includes("SAFETY CAR") && !blob.includes("VIRTUAL")) flag = "SC";
    else if (blob.includes("VSC") || blob.includes("VIRTUAL")) flag = "VSC";
    else if (blob.includes("GREEN") || blob.includes("CLEAR")) flag = "GREEN";
    else if (blob.includes("CHEQUERED") || blob.includes("CHECKERED")) flag = "FINISHED";
  }
  return { lap, rainfall: Boolean(wx?.rainfall), sessionFlag: flag, timing, positions };
}

