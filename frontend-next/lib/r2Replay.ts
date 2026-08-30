import { buildPath, pointAtFraction, wrap01 } from "@/lib/trackGeometry";
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

const R2_BASE = (process.env.NEXT_PUBLIC_R2_BASE_URL || "").replace(/\/$/, "");
/** Bump when race_field.json shape changes so CDN/browser caches cannot serve stale packs. */
const R2_ASSET_V = "4";
const DEFAULT_TRACK_M = 5000;
const SPEED_DT_LAP = 0.04;

export function r2BaseUrl(): string {
  return R2_BASE;
}

export function r2Configured(): boolean {
  return Boolean(R2_BASE);
}

function r2Url(year: number, round: number, file: string): string {
  return `${R2_BASE}/replay/${year}/${round}/${file}?v=${R2_ASSET_V}`;
}

export async function fetchWithProgress(
  url: string,
  onProgress?: (loaded: number, total: number | null) => void,
): Promise<Response> {
  const res = await fetch(url);
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
}

export async function fetchRaceField(
  year: number,
  round: number,
  onProgress?: (loaded: number, total: number | null) => void,
): Promise<RaceField> {
  if (!R2_BASE) throw new Error("R2 base URL unset");
  const res = await fetchWithProgress(r2Url(year, round, "race_field.json"), onProgress);
  return (await res.json()) as RaceField;
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
    delta_history: [],
    ghost_compound: (tick.compound as GhostTickData["ghost_compound"]) || "HARD",
    from_lap_one: true,
    plan_pit_laps: ghost?.strategy.pit_laps,
    plan_pit_compounds: ghost?.strategy.compounds as GhostTickData["plan_pit_compounds"],
  };
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
 * path_frac is wrapped so cars take the short way around start/finish.
 */
export function interpolatedPosFrac(
  samples: { lap_frac: number; path_frac: number }[],
  lapFrac: number,
): number {
  if (!samples.length) return 0;
  if (lapFrac <= samples[0].lap_frac) return samples[0].path_frac;
  const last = samples[samples.length - 1];
  if (lapFrac >= last.lap_frac) return last.path_frac;
  let lo = 0;
  let hi = samples.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (samples[mid].lap_frac <= lapFrac) lo = mid + 1;
    else hi = mid;
  }
  const next = samples[lo];
  const prev = samples[lo - 1];
  const span = next.lap_frac - prev.lap_frac;
  if (span <= 0) return prev.path_frac;
  const t = (lapFrac - prev.lap_frac) / span;
  let dp = next.path_frac - prev.path_frac;
  if (dp > 0.5) dp -= 1;
  if (dp < -0.5) dp += 1;
  return wrap01(prev.path_frac + t * dp);
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
  if (dtS < 1e-4 || dp <= 0) return 0;
  const kph = ((dp * trackLengthM) / dtS) * 3.6;
  if (!Number.isFinite(kph) || kph < 1) return 0;
  return Math.min(360, kph);
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

function posSamplesFor(field: RaceField, code: string): RaceFieldPosSample[] {
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
    const frac = pathFracAtLap(samples, lapFrac, field.meta.total_laps);
    const xy = pointAtFraction(path, frac);
    const prev = prevByDriver.get(code);
    const kph = speedKphFromPath(samples, lapFrac, lapDurS, field.meta.total_laps);
    let sectors = sectorMsFromLap(prev, samples, prevLap, field.meta.total_laps);
    if (sectors.sector1_ms == null && sectors.sector2_ms == null && sectors.sector3_ms == null) {
      sectors = sectorMsFromLap(row, samples, row.lap, field.meta.total_laps);
    }
    timing.push({
      position: row.position ?? 0,
      driver_code: code,
      gap_to_leader_s: row.gap_to_leader_s,
      gap_to_ahead_s: row.gap_ahead_s,
      last_lap_ms: row.lap_time_s != null ? Math.round(row.lap_time_s * 1000) : null,
      compound: row.compound,
      tyre_life: row.tyre_life,
      pit_count: pitCount.get(code) || 0,
      team_colour: colour.get(code) ?? null,
      in_pit: row.pit_this_lap && row.lap === lap,
      lap_number: row.lap,
      speed_kph: kph > 1 ? Math.round(kph) : null,
      status: row.is_dnf ? "DNF" : "RUNNING",
      sector1_ms: sectors.sector1_ms,
      sector2_ms: sectors.sector2_ms,
      sector3_ms: sectors.sector3_ms,
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
  timing.sort((a, b) => (a.position || 99) - (b.position || 99));
  let flag = "GREEN";
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

