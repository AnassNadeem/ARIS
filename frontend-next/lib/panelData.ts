import { normalizeCompound, msToSeconds } from "@/lib/compounds";
import type { ApiLapRow, ApiStintRow, Compound } from "@/lib/types";
import type { LapRecord, PitStopRecord, StintRecord } from "@/lib/mockRaceHistory";

function isScStatus(status: string | null | undefined): boolean {
  if (!status) return false;
  return /[46]/.test(status);
}

function fillGaps(rows: LapRecord[]): void {
  const byLap = new Map<number, LapRecord[]>();
  for (const row of rows) {
    const list = byLap.get(row.lap) ?? [];
    list.push(row);
    byLap.set(row.lap, list);
  }
  for (const list of byLap.values()) {
    const ordered = [...list].sort((a, b) => {
      if (a.position && b.position && a.position !== b.position) return a.position - b.position;
      return a.gapToLeaderS - b.gapToLeaderS;
    });
    const times = ordered.map((r) => r.gapToLeaderS);
    const origin = times[0] ?? 0;
    for (let i = 0; i < ordered.length; i++) {
      const row = ordered[i];
      row.position = i + 1;
      row.gapToLeaderS = Math.max(0, times[i] - origin);
      row.gapAheadS = i === 0 ? 0 : Math.max(0, times[i] - times[i - 1]);
      row.gapBehindS = i === ordered.length - 1 ? null : Math.max(0, times[i + 1] - times[i]);
    }
  }
}

export function lapRecordsFromApi(rows: ApiLapRow[]): LapRecord[] {
  const byDriver = new Map<string, ApiLapRow[]>();
  for (const row of rows) {
    const list = byDriver.get(row.driver_code) ?? [];
    list.push(row);
    byDriver.set(row.driver_code, list);
  }
  const out: LapRecord[] = [];
  for (const list of byDriver.values()) {
    const sorted = [...list].sort((a, b) => a.lap_number - b.lap_number);
    let raceTimeS = 0;
    for (let i = 0; i < sorted.length; i++) {
      const row = sorted[i];
      const t = msToSeconds(row.lap_time_ms) ?? 0;
      const s1 = msToSeconds(row.sector1_ms) ?? 0;
      const s2 = msToSeconds(row.sector2_ms) ?? 0;
      const s3 = msToSeconds(row.sector3_ms) ?? 0;
      raceTimeS += t;
      const endS = msToSeconds(row.end_time_ms);
      out.push({
        lap: row.lap_number,
        driverCode: row.driver_code,
        lapTimeS: t,
        compound: normalizeCompound(row.compound),
        tyreAge: row.tyre_life ?? i + 1,
        position: row.position ?? i + 1,
        gapToLeaderS: endS ?? raceTimeS,
        gapAheadS: null,
        gapBehindS: null,
        s1,
        s2,
        s3,
        isSC: isScStatus(row.track_status),
      });
    }
  }
  fillGaps(out);
  return out;
}

export function stintRecordsFromApi(rows: ApiStintRow[]): StintRecord[] {
  return rows.map((s) => ({
    driverCode: s.driver_code,
    stintNumber: s.stint_number,
    compound: normalizeCompound(s.compound) as Compound,
    startLap: s.lap_start,
    endLap: s.lap_end,
    avgLapTimeS: msToSeconds(s.average_lap_ms) ?? 0,
  }));
}

export function stintsFromLapRecords(laps: LapRecord[]): StintRecord[] {
  const byDriver = new Map<string, LapRecord[]>();
  for (const lap of laps) {
    const list = byDriver.get(lap.driverCode) ?? [];
    list.push(lap);
    byDriver.set(lap.driverCode, list);
  }
  const out: StintRecord[] = [];
  for (const [code, list] of byDriver) {
    const sorted = [...list].sort((a, b) => a.lap - b.lap);
    let start = 0;
    for (let i = 1; i <= sorted.length; i++) {
      const prev = sorted[i - 1];
      const next = sorted[i];
      const split = !next || next.compound !== prev.compound || next.tyreAge < prev.tyreAge;
      if (!split) continue;
      const chunk = sorted.slice(start, i);
      const times = chunk.map((l) => l.lapTimeS).filter((t) => t > 0);
      out.push({
        driverCode: code,
        stintNumber: out.filter((s) => s.driverCode === code).length + 1,
        compound: prev.compound,
        startLap: chunk[0].lap,
        endLap: chunk[chunk.length - 1].lap,
        avgLapTimeS: times.length ? times.reduce((a, b) => a + b, 0) / times.length : 0,
      });
      start = i;
    }
  }
  return out;
}

export function pitStopsFromLaps(rows: ApiLapRow[]): PitStopRecord[] {
  return rows
    .filter((r) => r.pit_in_lap)
    .map((r) => ({
      driverCode: r.driver_code,
      lap: r.lap_number,
      durationS: 2.4,
    }));
}

export function lapsUpTo(laps: LapRecord[], currentLap: number): LapRecord[] {
  return laps.filter((l) => l.lap <= Math.max(1, currentLap));
}

export function stintsUpTo(stints: StintRecord[], currentLap: number): StintRecord[] {
  const lap = Math.max(1, currentLap);
  return stints
    .filter((s) => s.startLap <= lap)
    .map((s) => ({ ...s, endLap: Math.min(s.endLap, lap) }));
}
