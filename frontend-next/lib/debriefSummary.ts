import { rankGhostByGap } from "@/lib/mapCars";
import { ghostTickAtOrBefore } from "@/lib/r2Replay";
import type { CarState, GhostR2Tick, GhostTickData, GhostVsRealResponse, RaceField, RaceFieldLap } from "@/lib/types";

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
      pit_laps: realRows
        .filter((row, i) => {
          const tick = ghostTickAtOrBefore(ticks, row.lap);
          if (!tick) return false;
          if ((tick.aris_action || "").toUpperCase().includes("PIT")) return true;
          if (i === 0) return false;
          const prev = ghostTickAtOrBefore(ticks, realRows[i - 1]!.lap);
          return Boolean(prev && tick.stint !== prev.stint);
        })
        .map((row) => row.lap),
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

function driverAtPosition(field: RaceField, lap: number, position: number, except: string): string | null {
  const want = except.toUpperCase();
  for (const row of field.laps) {
    if (row.lap !== lap || row.position !== position) continue;
    if (row.driver.toUpperCase() === want) continue;
    return row.driver.toUpperCase();
  }
  return null;
}

function flyingLapTime(row: RaceFieldLap): number | null {
  if (row.pit_this_lap || row.is_dnf || row.is_dsq) return null;
  if (row.lap_time_s == null || !Number.isFinite(row.lap_time_s) || row.lap_time_s < 40 || row.lap_time_s > 200) {
    return null;
  }
  if ((row.tyre_life ?? 0) <= 1) return null;
  return row.lap_time_s;
}

/**
 * Plain-language race summary for the chosen driver vs ARIS: pits, overtakes,
 * and the stint where tyre degradation hurt most.
 */
export function buildRaceStory(opts: {
  driver: string;
  field: RaceField | null;
  compare: GhostVsRealResponse | null;
  ghostData?: GhostTickData | null;
  finish?: RaceFinishSummary | null;
}): { headline: string; lines: string[] } {
  const code = opts.driver.toUpperCase();
  const lines: string[] = [];
  const realPos = opts.finish?.realPos ?? opts.compare?.real.position.at(-1) ?? null;
  const ghostPos = opts.finish?.ghostPos ?? opts.compare?.ghost.position.at(-1) ?? null;
  const headline =
    realPos != null && ghostPos != null
      ? `${code} finished P${realPos}. ARIS ghost finished P${ghostPos}.`
      : realPos != null
        ? `${code} finished P${realPos}.`
        : `${code} race summary.`;

  const pack = opts.field;
  const rows = pack
    ? pack.laps.filter((r) => r.driver.toUpperCase() === code).sort((a, b) => a.lap - b.lap)
    : [];

  for (let i = 1; i < rows.length; i++) {
    const prev = rows[i - 1]!;
    const cur = rows[i]!;
    const from = prev.position;
    const to = cur.position;
    if (cur.pit_this_lap) {
      const tyre = `${prev.compound} → ${cur.compound}`;
      const posBit =
        from != null && to != null && from !== to
          ? ` and dropped P${from} → P${to}`
          : from != null && to != null
            ? ` (held P${to})`
            : "";
      lines.push(`Lap ${cur.lap}: ${code} pitted (${tyre})${posBit}.`);
      continue;
    }
    if (from == null || to == null || from === to) continue;
    if (to > from) {
      const passer = driverAtPosition(pack!, cur.lap, from, code);
      const lost = to - from;
      const who = passer ? `${passer} ` : "";
      lines.push(
        `Lap ${cur.lap}: ${who}passed ${code} — lost ${lost} place${lost === 1 ? "" : "s"} (P${from} → P${to}).`,
      );
    } else {
      const victim = driverAtPosition(pack!, cur.lap, to, code);
      const gained = from - to;
      const who = victim ? ` on ${victim}` : "";
      lines.push(
        `Lap ${cur.lap}: ${code} gained ${gained} place${gained === 1 ? "" : "s"}${who} (P${from} → P${to}).`,
      );
    }
  }

  const byStint = new Map<number, RaceFieldLap[]>();
  for (const row of rows) {
    const stint = row.stint_number || 1;
    const list = byStint.get(stint) ?? [];
    list.push(row);
    byStint.set(stint, list);
  }
  let worst: { compound: string; slope: number; start: number; end: number } | null = null;
  for (const stintRows of byStint.values()) {
    const flying = stintRows
      .map((r) => ({ lap: r.lap, t: flyingLapTime(r), compound: r.compound, age: r.tyre_life ?? 0 }))
      .filter((r): r is { lap: number; t: number; compound: string; age: number } => r.t != null);
    if (flying.length < 4) continue;
    const first = flying[0]!;
    const last = flying[flying.length - 1]!;
    const span = Math.max(1, last.age - first.age);
    const slope = (last.t - first.t) / span;
    if (!worst || slope > worst.slope) {
      worst = { compound: last.compound, slope, start: first.lap, end: last.lap };
    }
  }
  if (worst && worst.slope > 0.02) {
    lines.push(
      `Tyre degradation was worst on ${worst.compound} (laps ${worst.start}–${worst.end}), about +${worst.slope.toFixed(2)}s per lap of rubber age.`,
    );
  }

  const realPits = opts.compare?.real.pit_laps ?? rows.filter((r) => r.pit_this_lap).map((r) => r.lap);
  const ghostPits = opts.compare?.ghost.pit_laps ?? [];
  if (realPits.length || ghostPits.length) {
    const realTxt = realPits.length ? realPits.map((l) => `L${l}`).join(", ") : "no stop";
    const ghostTxt = ghostPits.length ? ghostPits.map((l) => `L${l}`).join(", ") : "no stop";
    if (realTxt !== ghostTxt) {
      lines.push(`${code} boxed ${realTxt}; ARIS boxed ${ghostTxt}.`);
    }
  }

  if (opts.ghostData?.divergence_lap) {
    lines.push(
      `Strategies split on lap ${opts.ghostData.divergence_lap}: ARIS ${opts.ghostData.aris_action.replaceAll("_", " ")} vs ${code} ${opts.ghostData.real_action.replaceAll("_", " ")}.`,
    );
  }

  if (!lines.length) {
    lines.push("No pit or position swings were logged for this driver in the pack.");
  }
  return { headline, lines };
}
