import { rankGhostByGap } from "@/lib/mapCars";
import { ghostTickAtOrBefore } from "@/lib/r2Replay";
import type { CarState, GhostR2Tick, GhostVsRealResponse, RaceField, RaceFieldLap } from "@/lib/types";

export type RaceFinishSummary = {
  realCode: string;
  realPos: number | null;
  realGap: number | null;
  ghostPos: number | null;
  ghostGap: number | null;
};

/** Last lap row posted for a driver (finishing classification, including DNF). */
export function lastClassifiedLap(field: RaceField, code: string): RaceFieldLap | null {
  const want = code.toUpperCase();
  let best: RaceFieldLap | null = null;
  for (const row of field.laps) {
    if (row.driver.toUpperCase() !== want) continue;
    if (!best || row.lap > best.lap) best = row;
  }
  return best;
}

function classifiedGapsAtLap(field: RaceField, lap: number): number[] {
  const gaps: number[] = [];
  for (const row of field.laps) {
    if (row.lap !== lap || row.is_dnf || row.is_dsq) continue;
    if (row.gap_to_leader_s != null && Number.isFinite(row.gap_to_leader_s)) {
      gaps.push(row.gap_to_leader_s);
    }
  }
  return gaps;
}

/**
 * Post-race P / gap: real = classified finishing row from the pack;
 * ghost = timing-tower ARIS car (same rank as the live tower).
 */
export function raceFinishSummary(opts: {
  driver: string;
  field: RaceField | null;
  cars: Record<string, CarState>;
  ghostCar: CarState | null;
  ghostTicks?: Record<number, GhostR2Tick>;
}): RaceFinishSummary {
  const code = opts.driver.toUpperCase();
  const last = opts.field ? lastClassifiedLap(opts.field, code) : null;
  const real = opts.cars[code];
  const realPos = last?.position ?? real?.position ?? null;
  const realGap = last?.gap_to_leader_s ?? real?.gap_to_leader_s ?? null;

  if (opts.ghostCar) {
    return {
      realCode: code,
      realPos,
      realGap,
      ghostPos: opts.ghostCar.position,
      ghostGap: opts.ghostCar.gap_to_leader_s,
    };
  }

  const tickLap = last?.lap ?? 1;
  const tick = opts.ghostTicks ? ghostTickAtOrBefore(opts.ghostTicks, tickLap) : undefined;
  if (!tick || realGap == null) {
    return { realCode: code, realPos, realGap, ghostPos: null, ghostGap: null };
  }
  const ghostGap = realGap - (tick.cumulative_delta_s || 0);
  const fallback = realPos && realPos > 0 ? realPos : 1;
  const ghostPos = opts.field
    ? rankGhostByGap(ghostGap, classifiedGapsAtLap(opts.field, tickLap), fallback)
    : fallback;
  return { realCode: code, realPos, realGap, ghostPos, ghostGap };
}

/** Per-lap ghost vs real series using the same gap-rank as the timing tower. */
export function ghostVsRealFromField(
  field: RaceField,
  driver: string,
  ticks: Record<number, GhostR2Tick>,
): GhostVsRealResponse | null {
  const code = driver.toUpperCase();
  const realRows = field.laps.filter((r) => r.driver.toUpperCase() === code).sort((a, b) => a.lap - b.lap);
  if (!realRows.length) return null;
  const laps = realRows.map((r) => r.lap);
  const realPos = realRows.map((r) => r.position ?? 0);
  const realGap = realRows.map((r) => r.gap_to_leader_s ?? 0);
  const realCompound = realRows.map((r) => r.compound || "HARD");
  const ghostPos: number[] = [];
  const ghostGap: number[] = [];
  const ghostCompound: string[] = [];
  for (let i = 0; i < realRows.length; i++) {
    const row = realRows[i];
    const tick = ghostTickAtOrBefore(ticks, row.lap);
    const delta = tick?.cumulative_delta_s ?? 0;
    const gGap = (row.gap_to_leader_s ?? 0) - delta;
    const fallback = row.position && row.position > 0 ? row.position : 1;
    ghostPos.push(rankGhostByGap(gGap, classifiedGapsAtLap(field, row.lap), fallback));
    ghostGap.push(gGap);
    ghostCompound.push(tick?.compound || row.compound || "HARD");
  }
  return {
    session_id: `${field.meta.year}-${field.meta.round}-R`,
    driver: code,
    circuit: field.meta.circuit_name,
    ghost: {
      laps,
      position: ghostPos,
      gap_to_leader: ghostGap.map((v) => Math.round(v * 1000) / 1000),
      compound: ghostCompound,
      pit_laps: [],
    },
    real: {
      laps,
      position: realPos,
      gap_to_leader: realGap,
      compound: realCompound,
      pit_laps: realRows.filter((r) => r.pit_this_lap).map((r) => r.lap),
    },
    delta: {
      laps,
      position_delta: laps.map((_, i) => (ghostPos[i] ?? 0) - (realPos[i] ?? 0)),
      gap_delta: laps.map((_, i) => Math.round(((realGap[i] ?? 0) - (ghostGap[i] ?? 0)) * 1000) / 1000),
    },
  };
}
