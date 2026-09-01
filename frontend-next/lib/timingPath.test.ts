import { describe, expect, it } from "vitest";
import {
  GPS_CORR_EPSILON,
  TICK_INTERP_CAP_MS,
  blendedPathFrac,
  computeTimingPathFrac,
  correctPathFrac,
  displayPathFrac,
  expectedLapTimeS,
  gridPathFrac,
  replayDisplayElapsed,
  rollingAverageLapS,
} from "./timingPath";

describe("computeTimingPathFrac", () => {
  it("is monotonic in time and wraps once per lap", () => {
    const a = computeTimingPathFrac({ lapNumber: 2, timeSinceLapStartS: 30, expectedLapTimeS: 90 });
    const b = computeTimingPathFrac({ lapNumber: 2, timeSinceLapStartS: 45, expectedLapTimeS: 90 });
    expect(a).toBeCloseTo(30 / 90, 5);
    expect(b).toBeCloseTo(45 / 90, 5);
    expect(b).toBeGreaterThan(a);
  });

  it("clamps within-lap progress to [0, 1]", () => {
    expect(computeTimingPathFrac({ lapNumber: 1, timeSinceLapStartS: -5, expectedLapTimeS: 90 })).toBe(0);
    expect(computeTimingPathFrac({ lapNumber: 3, timeSinceLapStartS: 200, expectedLapTimeS: 90 })).toBe(0);
  });

  it("uses rolling-average fallback for lap 1", () => {
    expect(rollingAverageLapS([])).toBe(90);
    expect(rollingAverageLapS([88, 90, 92])).toBeCloseTo(90, 5);
    expect(expectedLapTimeS([88, 91])).toBe(91);
    const frac = computeTimingPathFrac({
      lapNumber: 1,
      timeSinceLapStartS: 45,
      expectedLapTimeS: rollingAverageLapS([]),
    });
    expect(frac).toBeCloseTo(0.5, 5);
  });
});

describe("correctPathFrac", () => {
  it("applies GPS when it is within EPSILON of timing", () => {
    expect(correctPathFrac(0.5, 0.51, GPS_CORR_EPSILON)).toBeCloseTo(0.51, 5);
  });

  it("discards GPS beyond EPSILON instead of holding a snap", () => {
    expect(correctPathFrac(0.16, 0.4, GPS_CORR_EPSILON)).toBeCloseTo(0.16, 5);
    expect(correctPathFrac(0.02, 0.97, GPS_CORR_EPSILON)).toBeCloseTo(0.02, 5);
  });

  it("does not treat a >0.5 delta as reverse", () => {
    expect(correctPathFrac(0.1, 0.9, GPS_CORR_EPSILON)).toBeCloseTo(0.1, 5);
  });
});

describe("displayPathFrac grid", () => {
  it("uses grid slots before lights-out, not the first GPS sample", () => {
    const pole = displayPathFrac({ timingFrac: 0, gpsFrac: 0.97, gridPosition: 1, raceLapFrac: 0 });
    const p2 = displayPathFrac({ timingFrac: 0, gpsFrac: 0.96, gridPosition: 2, raceLapFrac: 0 });
    expect(pole).toBeCloseTo(gridPathFrac(1), 5);
    expect(p2).toBeGreaterThan(0.98);
    expect(p2).toBeLessThan(1);
  });

  it("blends grid onto the timing target after lights-out", () => {
    const pole = gridPathFrac(1);
    const mid = blendedPathFrac(0.12, 1, 0.02 + 0.0175);
    expect(mid).toBeGreaterThan(pole);
    expect(mid).toBeLessThan(0.12);
    expect(blendedPathFrac(0.12, 1, 0.2)).toBeCloseTo(0.12, 5);
  });
});

describe("replayDisplayElapsed", () => {
  it("lets 1x crawl through a late 250ms tick instead of parking", () => {
    expect(replayDisplayElapsed(10, 1000, 1100, true, 1)).toBeCloseTo(10.1, 5);
    expect(replayDisplayElapsed(10, 1000, 1400, true, 1)).toBeCloseTo(10.4, 5);
    expect(replayDisplayElapsed(10, 1000, 1600, true, 1)).toBeCloseTo(10.5, 5);
    expect(replayDisplayElapsed(10, 1000, 1400, false, 1)).toBe(10);
    expect(TICK_INTERP_CAP_MS).toBe(250);
  });

  it("does not keep a 50x interpolation lead after the tick clock is reset", () => {
    expect(replayDisplayElapsed(100, 1000, 1250, true, 50)).toBeCloseTo(112.5, 5);
    expect(replayDisplayElapsed(100, 1000, 1400, true, 50)).toBeCloseTo(112.5, 5);
    expect(replayDisplayElapsed(100, 1250, 1250, true, 1)).toBe(100);
  });
});
