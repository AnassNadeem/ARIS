import { normalizeCompound, msToSeconds } from "@/lib/compounds";
import type { CarState, DriverListing, LivePosition, LiveTimingRow, SectorColour } from "@/lib/types";

function driverMeta(code: string, drivers: DriverListing[]): DriverListing | undefined {
  return drivers.find((d) => d.driver_code === code);
}

function colour(raw: string | null | undefined): SectorColour {
  const u = (raw ?? "").toLowerCase();
  if (u === "purple" || u === "green" || u === "yellow" || u === "grey") return u;
  return "grey";
}

export function mapTimingAndPositions(
  timing: LiveTimingRow[],
  positions: LivePosition[],
  drivers: DriverListing[],
  totalLaps: number,
  currentLap: number,
): Record<string, CarState> {
  const posBy = new Map(positions.map((p) => [p.driver_code, p]));
  const cars: Record<string, CarState> = {};
  const rows: LiveTimingRow[] = timing.length
    ? timing
    : positions.map((p, i) => ({
        position: i + 1,
        driver_code: p.driver_code,
        gap_to_leader_s: null,
        gap_to_ahead_s: null,
        last_lap_ms: null,
        compound: null,
        tyre_life: null,
        pit_count: 0,
        team_colour: p.team_colour,
        in_pit: p.is_pitted,
        lap_number: currentLap,
        speed_kph: p.speed_ms != null ? p.speed_ms * 3.6 : null,
        status: p.is_dnf ? "DNF" : "RUNNING",
      }));

  for (const row of rows) {
    const meta = driverMeta(row.driver_code, drivers);
    const gps = posBy.get(row.driver_code);
    const speedKph = row.speed_kph ?? (gps?.speed_ms != null ? gps.speed_ms * 3.6 : 0);
    const status = row.status ?? (row.eliminated ? "DNF" : gps?.is_dnf ? "DNF" : "RUNNING");
    cars[row.driver_code] = {
      driver_code: row.driver_code,
      driver_number: meta?.driver_number ?? 0,
      full_name: meta?.full_name ?? row.driver_code,
      team: meta?.team ?? "",
      team_colour: row.team_colour ?? gps?.team_colour ?? meta?.team_colour ?? "#888888",
      position: row.position,
      lap_number: row.lap_number ?? currentLap,
      compound: normalizeCompound(row.compound),
      tyre_life: row.tyre_life ?? 0,
      gap_to_leader_s: row.gap_to_leader_s,
      gap_ahead_s: row.gap_to_ahead_s,
      gap_ahead_history: [],
      last_lap_s: msToSeconds(row.last_lap_ms),
      best_lap_s: msToSeconds(row.best_lap_ms ?? null),
      pit_stops: row.pit_count ?? 0,
      is_pitted: row.in_pit || Boolean(gps?.is_pitted),
      is_dnf: status === "DNF" || status === "DNS" || Boolean(gps?.is_dnf),
      status,
      fastest_lap: Boolean(row.fastest_lap),
      sector1_s: msToSeconds(row.sector1_ms ?? null),
      sector2_s: msToSeconds(row.sector2_ms ?? null),
      sector3_s: msToSeconds(row.sector3_ms ?? null),
      s1_colour: colour(row.s1_colour),
      s2_colour: colour(row.s2_colour),
      s3_colour: colour(row.s3_colour),
      laps_completed: row.laps_completed ?? row.lap_number,
      laps_down: row.laps_down ?? null,
      path_frac: gps?.path_frac,
      x: gps?.x ?? 0,
      y: gps?.y ?? 0,
      speed_kph: speedKph ?? 0,
      heading_rad: 0,
      laps_remaining: Math.max(0, totalLaps - (row.lap_number ?? currentLap)),
      total_laps: totalLaps,
    };
  }
  return cars;
}

export function sessionFlagToPhase(flag: string | null | undefined): "GREEN" | "VSC" | "SC" | "RED_FLAG" {
  const u = (flag ?? "").toUpperCase();
  if (u === "SC") return "SC";
  if (u === "VSC") return "VSC";
  if (u === "RED") return "RED_FLAG";
  return "GREEN";
}

export function timingFingerprint(rows: LiveTimingRow[], positions: LivePosition[]): string {
  const t = rows
    .map(
      (r) =>
        `${r.driver_code}:${r.position}:${r.last_lap_ms}:${r.sector1_ms}:${r.sector2_ms}:${r.sector3_ms}:${r.lap_number}:${r.status}:${r.fastest_lap}:${r.speed_kph}`,
    )
    .join("|");
  const p = positions
    .map((x) => `${x.driver_code}:${(x.x ?? 0).toFixed(1)}:${(x.y ?? 0).toFixed(1)}:${(x.path_frac ?? 0).toFixed(4)}`)
    .join("|");
  return `${t}#${p}`;
}

function carSig(c: CarState): string {
  return `${c.position}|${c.lap_number}|${c.last_lap_s}|${c.best_lap_s}|${c.sector1_s}|${c.sector2_s}|${c.sector3_s}|${c.s1_colour}|${c.s2_colour}|${c.s3_colour}|${c.status}|${c.compound}|${c.tyre_life}|${c.gap_to_leader_s}|${c.fastest_lap}|${c.is_pitted}|${c.is_dnf}|${c.path_frac?.toFixed(4)}|${c.x.toFixed(1)}|${c.y.toFixed(1)}|${Math.round(c.speed_kph)}`;
}

export function mergeByDriverCode<T extends { driver_code: string }>(prev: T[], patch: T[]): T[] {
  if (!patch.length) return prev;
  if (!prev.length) return patch;
  const by = new Map(prev.map((row) => [row.driver_code, row]));
  for (const row of patch) {
    const existing = by.get(row.driver_code);
    by.set(row.driver_code, existing ? { ...existing, ...row } : row);
  }
  const seen = new Set<string>();
  const out: T[] = [];
  for (const row of prev) {
    out.push(by.get(row.driver_code)!);
    seen.add(row.driver_code);
  }
  for (const row of patch) {
    if (seen.has(row.driver_code)) continue;
    out.push(by.get(row.driver_code)!);
    seen.add(row.driver_code);
  }
  return out;
}

/** Shallow-merge SSE cars, preserving previous object identity when a row is unchanged. */
export function mergeCars(
  prev: Record<string, CarState>,
  next: Record<string, CarState>,
): Record<string, CarState> {
  const nextKeys = Object.keys(next);
  const prevKeys = Object.keys(prev);
  if (prevKeys.length === nextKeys.length && nextKeys.length === 0) return prev;
  let changed = prevKeys.length !== nextKeys.length;
  const out: Record<string, CarState> = {};
  for (const k of nextKeys) {
    const a = prev[k];
    let b = next[k];
    if (
      a &&
      (b.path_frac == null || !Number.isFinite(b.path_frac)) &&
      a.path_frac != null &&
      Number.isFinite(a.path_frac)
    ) {
      b = { ...b, path_frac: a.path_frac, x: a.x, y: a.y };
    }
    if (a && carSig(a) === carSig(b)) {
      out[k] = a;
    } else {
      out[k] = b;
      changed = true;
    }
  }
  if (!changed) {
    for (const k of prevKeys) {
      if (!(k in next)) {
        changed = true;
        break;
      }
    }
  }
  return changed ? out : prev;
}

/** Timing-tower equality — ignore GPS so map ticks do not rebuild rows. */
export function timingEqual(a: CarState, b: CarState): boolean {
  return (
    a.position === b.position &&
    a.lap_number === b.lap_number &&
    a.last_lap_s === b.last_lap_s &&
    a.best_lap_s === b.best_lap_s &&
    a.sector1_s === b.sector1_s &&
    a.sector2_s === b.sector2_s &&
    a.sector3_s === b.sector3_s &&
    a.s1_colour === b.s1_colour &&
    a.s2_colour === b.s2_colour &&
    a.s3_colour === b.s3_colour &&
    a.status === b.status &&
    a.compound === b.compound &&
    a.tyre_life === b.tyre_life &&
    a.gap_to_leader_s === b.gap_to_leader_s &&
    a.gap_ahead_s === b.gap_ahead_s &&
    a.laps_down === b.laps_down &&
    a.fastest_lap === b.fastest_lap &&
    a.is_pitted === b.is_pitted &&
    a.is_dnf === b.is_dnf &&
    a.is_ghost === b.is_ghost &&
    a.team_colour === b.team_colour &&
    a.ghost_cumulative_delta === b.ghost_cumulative_delta &&
    a.ghost_delta_s === b.ghost_delta_s &&
    a.ghost_delta_vs === b.ghost_delta_vs &&
    a.laps_completed === b.laps_completed &&
    a.ghost_in_pits === b.ghost_in_pits &&
    a.ghost_pit_compound === b.ghost_pit_compound
  );
}

export function isGhostRow(car: Pick<CarState, "driver_code" | "is_ghost">): boolean {
  return car.is_ghost === true || car.driver_code.startsWith("A_");
}

/** Classified real cars only — ghost never counts toward grid/results. */
export function realClassifiedCars(cars: CarState[]): CarState[] {
  return cars.filter((c) => !isGhostRow(c) && !c.is_dnf && c.status !== "DNS");
}

export function onTrackCarCodes(cars: Record<string, CarState>, ghostCode?: string | null): string {
  const ids = Object.values(cars)
    .filter((c) => !c.is_pitted && !c.is_dnf && !isGhostRow(c))
    .map((c) => c.driver_code);
  if (ghostCode) ids.push(ghostCode);
  return ids.sort().join(",");
}

function towerPosition(car: CarState): number {
  const p = car.position;
  return p != null && p > 0 ? p : 99;
}

function towerLastLap(car: CarState): number {
  return car.laps_completed ?? car.lap_number ?? 0;
}

/**
 * Ghost gap-to-leader from the focus driver's classified gap minus
 * ghost_*.json cumulative_delta_s. Same identity as panelData fillGaps:
 * gap_to_leader is a cumulative-time diff vs the leader, not GPS.
 */
export function ghostClassifiedGap(
  realGapToLeader: number | null | undefined,
  cumulativeDeltaS: number,
): number | null {
  if (realGapToLeader == null || !Number.isFinite(realGapToLeader)) return null;
  return realGapToLeader - cumulativeDeltaS;
}

/**
 * Rank the ghost among real classified cars by gap-to-leader.
 * Mirrors `aris.ghost.rank_ghost_by_gap`: position = 1 + how many real cars
 * have a strictly smaller gap. When cumulative_delta is 0 this equals the
 * focus driver's own classified position.
 */
export function rankGhostByGap(
  ghostGapS: number | null,
  fieldGaps: Iterable<number>,
  fallbackPos: number,
): number {
  const gaps = [...fieldGaps];
  if (ghostGapS == null || !Number.isFinite(ghostGapS) || gaps.length === 0) {
    return Math.max(1, fallbackPos);
  }
  let ahead = 0;
  for (const g of gaps) {
    if (g < ghostGapS) ahead++;
  }
  return Math.max(1, ahead + 1);
}

/**
 * Place the ghost in classified order using the field's existing
 * gap_to_leader_s / gap_ahead_s (from r2FrameAt lap-table cumulatives).
 * Does not read path_frac or pos_samples.
 */
export function annotateGhostTower(
  ghost: CarState,
  realCars: Record<string, CarState> | CarState[],
  focus: CarState | null,
): CarState {
  const field = (Array.isArray(realCars) ? realCars : Object.values(realCars)).filter(
    (c) => !isGhostRow(c) && !c.is_dnf && c.status !== "DNS",
  );
  const fieldGaps = field
    .map((c) => c.gap_to_leader_s)
    .filter((g): g is number => g != null && Number.isFinite(g));
  const delta = ghost.ghost_cumulative_delta ?? 0;
  const ghostGap = ghostClassifiedGap(focus?.gap_to_leader_s, delta);
  const fallback = ghost.position && ghost.position > 0 ? ghost.position : (focus?.position ?? 1);
  const position = rankGhostByGap(ghostGap, fieldGaps, fallback);
  const ordered = [...field].sort((a, b) => towerPosition(a) - towerPosition(b));
  const ahead = [...ordered].reverse().find((c) => towerPosition(c) < position);
  const behind = ordered.find((c) => towerPosition(c) >= position);
  const adjacent = ahead ?? behind;
  const gapAhead =
    ahead && ahead.gap_to_leader_s != null && ghostGap != null
      ? ghostGap - ahead.gap_to_leader_s
      : ahead
        ? null
        : 0;
  let ghostDeltaS: number | null = null;
  let ghostDeltaVs: string | undefined;
  if (adjacent && adjacent.gap_to_leader_s != null && ghostGap != null) {
    ghostDeltaS = adjacent.gap_to_leader_s - ghostGap;
    ghostDeltaVs = adjacent.driver_code;
  }
  return {
    ...ghost,
    is_ghost: true,
    position,
    gap_to_leader_s: ghostGap,
    gap_ahead_s: gapAhead,
    ghost_delta_s: ghostDeltaS,
    ghost_delta_vs: ghostDeltaVs,
  };
}

/**
 * Timing tower order: classified (by position) including a virtual ghost
 * row, then DNF/retired (by last classified lap descending).
 *
 * Pass the ghost in `cars` (tagged is_ghost) so it sorts like any other
 * classified car. The optional second arg is still accepted and inserted
 * into that array if missing. Split uses only is_dnf; ghost is never DNF.
 */
export function orderTimingTower(cars: CarState[], ghost: CarState | null = null): CarState[] {
  const tagged = ghost && !ghost.is_ghost ? { ...ghost, is_ghost: true } : ghost;
  const fromList = cars.find(isGhostRow) ?? null;
  const g = tagged ?? fromList;
  const rest = cars.filter((c) => !isGhostRow(c));
  const classified = rest.filter((c) => !c.is_dnf);
  const dnf = rest.filter((c) => c.is_dnf);
  if (g && !g.is_dnf) classified.push(g);
  classified.sort((a, b) => {
    const dp = towerPosition(a) - towerPosition(b);
    if (dp !== 0) return dp;
    // Same classified slot: ghost occupies the visual row first ("would be P8").
    return Number(isGhostRow(b)) - Number(isGhostRow(a));
  });
  dnf.sort((a, b) => towerLastLap(b) - towerLastLap(a));
  return classified.concat(dnf);
}
