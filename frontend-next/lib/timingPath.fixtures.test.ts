import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { elapsedToLap, replayDisplayFrac, r2FrameAt } from "./r2Replay";
import { GRID_START_LAP_FRAC } from "./timingPath";
import type { RaceField } from "./types";

const ROOT = resolve(__dirname, "../..");

function loadField(year: number, round: number): RaceField | null {
  const p = resolve(ROOT, `data/replay_r2/replay/${year}/${round}/race_field.json`);
  if (!existsSync(p)) return null;
  return JSON.parse(readFileSync(p, "utf8")) as RaceField;
}

function sampleElapsed(field: RaceField): number[] {
  const total = Math.max(1, field.meta.total_laps);
  return [0, 0.01 * 90, 5, 45, 90 + 10].filter((t) => elapsedToLap(field, t).lap <= total);
}

describe("timing path_frac vs tower on real packs", () => {
  const packs: { label: string; year: number; round: number }[] = [
    { label: "Melbourne 2025", year: 2025, round: 1 },
    { label: "Montreal 2025", year: 2025, round: 10 },
    { label: "Bahrain 2024", year: 2024, round: 1 },
  ];

  for (const pack of packs) {
    it(`${pack.label}: grid at t=0 and no GPS hairpin on the map frac`, () => {
      const field = loadField(pack.year, pack.round);
      if (!field) return;
      const frame0 = r2FrameAt(field, 0);
      expect(elapsedToLap(field, 0).lapFrac).toBeLessThan(GRID_START_LAP_FRAC);
      const pole = field.drivers.find((d) => d.grid_position === 1);
      if (pole) {
        const frac = replayDisplayFrac(field, pole.code, 0);
        const err = Math.min(Math.abs(frac), Math.abs(frac - 1));
        expect(err, `${pole.code} pole frac ${frac}`).toBeLessThan(0.02);
      }
      for (const elapsed of sampleElapsed(field)) {
        const { lapFrac } = elapsedToLap(field, elapsed);
        const frame = r2FrameAt(field, elapsed);
        const byPos = [...frame.timing].filter((r) => r.status !== "DNS").sort((a, b) => (a.position || 99) - (b.position || 99));
        if (lapFrac < GRID_START_LAP_FRAC) {
          expect(byPos[0]?.position).toBe(1);
          continue;
        }
        for (const row of byPos) {
          const frac = replayDisplayFrac(field, row.driver_code, elapsed);
          expect(Number.isFinite(frac)).toBe(true);
          expect(frac).toBeGreaterThanOrEqual(0);
          expect(frac).toBeLessThan(1);
        }
      }
    });
  }
});
