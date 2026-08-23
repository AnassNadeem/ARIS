import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import type { Compound } from "@/lib/types";

export interface LapRecord {
  lap: number;
  driverCode: string;
  lapTimeS: number;
  compound: Compound;
  tyreAge: number;
  position: number;
  gapToLeaderS: number;
  gapAheadS: number | null;
  gapBehindS: number | null;
  s1: number;
  s2: number;
  s3: number;
  isSC: boolean;
}

export interface StintRecord {
  driverCode: string;
  stintNumber: number;
  compound: Compound;
  startLap: number;
  endLap: number;
  avgLapTimeS: number;
}

export interface PitStopRecord {
  driverCode: string;
  lap: number;
  durationS: number;
}

const TOTAL_LAPS = 72;
const BASE_LAP_S = 71.5;
const SC_LAPS = new Set([12, 13, 14, 15]);
const SLOPE: Record<Compound, number> = {
  SOFT: 0.08,
  MEDIUM: 0.05,
  HARD: 0.03,
  INTERMEDIATE: 0.02,
  WET: 0.02,
};

// Deterministic pseudo-random in [0, 1) so mock data is stable across renders/SSR.
function prand(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

interface DriverPlan {
  code: string;
  paceOffset: number;
  stints: { compound: Compound; startLap: number; endLap: number }[];
  pitStops: PitStopRecord[];
}

function buildPlan(index: number, code: string): DriverPlan {
  const paceOffset = index * 0.05 + prand(index * 7.1) * 0.2;
  const isOneStop = index % 3 !== 1;
  const pit1 = 22 + Math.floor(prand(index * 3.3) * 8);
  const pit2 = 46 + Math.floor(prand(index * 5.7) * 8);
  const compounds: Compound[] = ["MEDIUM", "HARD", "SOFT"];
  const c1 = compounds[index % 3];
  const c2 = compounds[(index + 1) % 3];
  const c3 = compounds[(index + 2) % 3];

  const stints = isOneStop
    ? [
        { compound: c1, startLap: 1, endLap: pit1 },
        { compound: c2, startLap: pit1 + 1, endLap: TOTAL_LAPS },
      ]
    : [
        { compound: c1, startLap: 1, endLap: pit1 },
        { compound: c2, startLap: pit1 + 1, endLap: pit2 },
        { compound: c3, startLap: pit2 + 1, endLap: TOTAL_LAPS },
      ];

  const pitStops: PitStopRecord[] = stints.slice(0, -1).map((s) => ({
    driverCode: code,
    lap: s.endLap,
    durationS: 2.1 + prand(index * 11 + s.endLap) * 1.4,
  }));

  return { code, paceOffset, stints, pitStops };
}

const PLANS: DriverPlan[] = MOCK_DRIVERS_2025.map((d, i) => buildPlan(i, d.driver_code));

function compoundAt(plan: DriverPlan, lap: number): { compound: Compound; tyreAge: number } {
  const stint = plan.stints.find((s) => lap >= s.startLap && lap <= s.endLap) ?? plan.stints[plan.stints.length - 1];
  return { compound: stint.compound, tyreAge: lap - stint.startLap + 1 };
}

function buildAll(): { laps: LapRecord[]; stints: StintRecord[]; pitStops: PitStopRecord[] } {
  const laps: LapRecord[] = [];
  const stints: StintRecord[] = [];
  const pitStops: PitStopRecord[] = [];

  for (const plan of PLANS) {
    plan.stints.forEach((s, i) => {
      let sum = 0;
      let n = 0;
      for (let lap = s.startLap; lap <= s.endLap; lap++) {
        const age = lap - s.startLap + 1;
        const t = BASE_LAP_S + plan.paceOffset + SLOPE[s.compound] * age + (SC_LAPS.has(lap) ? 25 : 0);
        sum += t;
        n += 1;
      }
      stints.push({
        driverCode: plan.code,
        stintNumber: i + 1,
        compound: s.compound,
        startLap: s.startLap,
        endLap: s.endLap,
        avgLapTimeS: n ? sum / n : 0,
      });
    });
    pitStops.push(...plan.pitStops);
  }

  for (let lap = 1; lap <= TOTAL_LAPS; lap++) {
    const rows = PLANS.map((plan) => {
      const { compound, tyreAge } = compoundAt(plan, lap);
      const jitter = (prand(plan.code.length * 13 + lap * 0.7) - 0.5) * 0.4;
      const lapTimeS =
        BASE_LAP_S + plan.paceOffset + SLOPE[compound] * tyreAge + jitter + (SC_LAPS.has(lap) ? 25 : 0);
      return { plan, compound, tyreAge, lapTimeS };
    });

    // cumulative race time up to this lap approximates gaps well enough for a mock.
    const totals = rows.map((r) => {
      let total = 0;
      for (let l = 1; l <= lap; l++) {
        const { compound, tyreAge } = compoundAt(r.plan, l);
        total += BASE_LAP_S + r.plan.paceOffset + SLOPE[compound] * tyreAge + (SC_LAPS.has(l) ? 25 : 0);
      }
      return { code: r.plan.code, total, row: r };
    });
    totals.sort((a, b) => a.total - b.total);

    totals.forEach((t, idx) => {
      const ahead = totals[idx - 1];
      const behind = totals[idx + 1];
      const s1 = t.row.lapTimeS * 0.28;
      const s2 = t.row.lapTimeS * 0.4;
      const s3 = t.row.lapTimeS - s1 - s2;
      laps.push({
        lap,
        driverCode: t.code,
        lapTimeS: t.row.lapTimeS,
        compound: t.row.compound,
        tyreAge: t.row.tyreAge,
        position: idx + 1,
        gapToLeaderS: t.total - totals[0].total,
        gapAheadS: ahead ? t.total - ahead.total : null,
        gapBehindS: behind ? behind.total - t.total : null,
        s1,
        s2,
        s3,
        isSC: SC_LAPS.has(lap),
      });
    });
  }

  return { laps, stints, pitStops };
}

let cache: ReturnType<typeof buildAll> | null = null;

export function getRaceHistoryMock() {
  if (!cache) cache = buildAll();
  return cache;
}

export function driverLaps(driverCode: string): LapRecord[] {
  return getRaceHistoryMock().laps.filter((l) => l.driverCode === driverCode);
}

export function scLapRanges(): { startLap: number; endLap: number }[] {
  return [{ startLap: 12, endLap: 15 }];
}

export const TOTAL_LAPS_MOCK = TOTAL_LAPS;
