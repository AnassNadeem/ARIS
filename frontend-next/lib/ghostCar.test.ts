import { describe, expect, it } from "vitest";
import { ghostCarFromTick, ghostPlaybackAt, PIT_ENTRY_FRAC, SEEK_JUMP_GRACE_S } from "./ghostCar";
import { PathCarAnimator } from "./deadReckoning";
import { buildPath } from "./trackGeometry";
import type { GhostTickData } from "./types";

function tick(over: Partial<GhostTickData> = {}): GhostTickData {
  return {
    driver_code: "VER",
    divergence_lap: 1,
    aris_action: "STAY_OUT",
    real_action: "STAY_OUT",
    ghost_tyre: "SOFT",
    ghost_tyre_age: 1,
    ghost_position: 1,
    ghost_cumulative_delta: 0,
    active: true,
    outcome: null,
    delta_history: [],
    ghost_compound: "SOFT",
    from_lap_one: true,
    plan_pit_laps: [9],
    plan_pit_compounds: ["HARD"],
    ...over,
  };
}

describe("ghostPlaybackAt", () => {
  const laps = [NaN, 90, 90, 90, 90, 90, 90, 90, 90, 112];
  const cum = [0];
  for (let i = 1; i < laps.length; i++) cum.push(cum[i - 1] + (Number.isFinite(laps[i]) ? laps[i] : 0));

  it("places the ghost from its own clock, not a real-car offset", () => {
    const pb = ghostPlaybackAt({
      elapsedS: 45,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [9],
      pitLossS: 21.8,
    });
    expect(pb.lap).toBe(1);
    expect(pb.progress_within_lap).toBeCloseTo(0.5, 5);
    expect(pb.path_frac).toBeCloseTo(0.5, 5);
    expect(pb.inPits).toBe(false);
  });

  it("hides the ghost for pit_loss_s from ghost_cumulative_s[pit_lap-1] + 0.84 × ghost_lap_s[pit_lap]", () => {
    const entry = cum[8] + PIT_ENTRY_FRAC * laps[9];
    const stillVisible = ghostPlaybackAt({
      elapsedS: cum[8] + 5,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [9],
      pitLossS: 21.8,
      pitCompounds: ["HARD"],
    });
    expect(stillVisible.inPits).toBe(false);

    const inPit = ghostPlaybackAt({
      elapsedS: entry + 5,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [9],
      pitLossS: 21.8,
      pitCompounds: ["HARD"],
    });
    expect(inPit.lap).toBe(9);
    expect(inPit.inPits).toBe(true);
    expect(inPit.pitCompound).toBe("HARD");
    expect(inPit.towerLap).toBe(8);

    const after = ghostPlaybackAt({
      elapsedS: entry + 21.8 + 0.5,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [9],
      pitLossS: 21.8,
      pitCompounds: ["HARD"],
    });
    expect(after.inPits).toBe(false);
    expect(after.skipSeekJump).toBe(true);
    expect(after.towerLap).toBe(9);
  });

  it("skips SEEK_JUMP for the first 3 replay seconds", () => {
    const pb = ghostPlaybackAt({
      elapsedS: 1.5,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [9],
      pitLossS: 21.8,
    });
    expect(pb.skipSeekJump).toBe(true);
    expect(SEEK_JUMP_GRACE_S).toBe(3);
    const later = ghostPlaybackAt({
      elapsedS: 4,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [9],
      pitLossS: 21.8,
    });
    expect(later.skipSeekJump).toBe(false);
  });

  it("offsets lap-1 path_frac by ghostStartFrac at lights-out", () => {
    const pb = ghostPlaybackAt({
      elapsedS: 0,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [],
      pitLossS: 22,
      ghostStartFrac: 0.97487,
    });
    expect(pb.lap).toBe(1);
    expect(pb.progress_within_lap).toBe(0);
    expect(pb.path_frac).toBeCloseTo(0.97487, 5);
  });

  it("matches the real car's first pos_sample at elapsedS=0", () => {
    const samples = [
      { lap_frac: 0, path_frac: 0.97487 },
      { lap_frac: 0.5, path_frac: 0.4 },
    ];
    const pb = ghostPlaybackAt({
      elapsedS: 0,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [],
      pitLossS: 22,
      posSamples: samples,
      ghostStartFrac: 0.97487,
    });
    expect(pb.path_frac).toBeCloseTo(0.97487, 5);
  });

  it("maps circuit progress 0→1 per lap even when pos_samples exist", () => {
    const samples = [
      { lap_frac: 0, path_frac: 0.1 },
      { lap_frac: 0.5, path_frac: 0.6 },
      { lap_frac: 1.0, path_frac: 0.1 },
    ];
    const pb = ghostPlaybackAt({
      elapsedS: 45,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [],
      pitLossS: 22,
      posSamples: samples,
    });
    // startFrac 0.1 + progress 0.5 — independent clock, not GPS at lap_frac 0.5
    expect(pb.path_frac).toBeCloseTo(0.6, 5);
  });

  it("does not use real-car GPS when it would disagree with the ghost clock", () => {
    const samples = [
      { lap_frac: 0, path_frac: 0.97487 },
      { lap_frac: 0.5, path_frac: 0.05 },
      { lap_frac: 56.9, path_frac: 0.9 },
    ];
    const pb = ghostPlaybackAt({
      elapsedS: 45,
      ghostLapS: laps,
      ghostCumulativeS: cum,
      totalLaps: 57,
      pitLaps: [],
      pitLossS: 22,
      posSamples: samples,
      ghostStartFrac: 0.97487,
    });
    expect(pb.lap).toBe(1);
    expect(pb.progress_within_lap).toBeCloseTo(0.5, 5);
    expect(pb.path_frac).toBeCloseTo(0.47487, 5);
    expect(pb.path_frac).not.toBeCloseTo(0.05, 2);
    expect(pb.path_frac).not.toBeCloseTo(0.9, 2);
  });

  it("at elapsedS=30 with a Bahrain-like lap, path_frac is mid-first-sector", () => {
    const bahrainLaps = [NaN, 98.665, 95.978, 96.434];
    const bahrainCum = [0, 98.665, 194.643, 291.077];
    const pb = ghostPlaybackAt({
      elapsedS: 30,
      ghostLapS: bahrainLaps,
      ghostCumulativeS: bahrainCum,
      totalLaps: 57,
      pitLaps: [9],
      pitLossS: 21.8,
      ghostStartFrac: 0.97487,
    });
    expect(pb.lap).toBe(1);
    expect(pb.path_frac).toBeGreaterThanOrEqual(0.2);
    expect(pb.path_frac).toBeLessThanOrEqual(0.5);
  });

  it("does not jump to the last classified lap when early cumulative is flat", () => {
    const holeLaps = [NaN, 90, 90, 90, NaN, NaN];
    const holeCum = [0, 90, 180, 270, 270, 270];
    const pb = ghostPlaybackAt({
      elapsedS: 400,
      ghostLapS: holeLaps,
      ghostCumulativeS: holeCum,
      totalLaps: 57,
      pitLaps: [],
      pitLossS: 22,
    });
    expect(pb.lap).toBe(3);
    expect(pb.progress_within_lap).toBe(1);
    expect(pb.path_frac).toBeCloseTo(0, 5);
  });

  it("keeps moving on lap 5 after a filled NaN hole", () => {
    const filled = [NaN, 90, 90, 90, 90, 90];
    const filledCum = [0, 90, 180, 270, 360, 450];
    const pb = ghostPlaybackAt({
      elapsedS: 400,
      ghostLapS: filled,
      ghostCumulativeS: filledCum,
      totalLaps: 57,
      pitLaps: [],
      pitLossS: 22,
    });
    expect(pb.lap).toBe(5);
    expect(pb.progress_within_lap).toBeCloseTo(40 / 90, 5);
    expect(pb.path_frac).toBeCloseTo(40 / 90, 5);
  });
});

describe("ghostCarFromTick playback", () => {
  it("sets pit flags from playback and a blank race number", () => {
    const pb = ghostPlaybackAt({
      elapsedS: 2,
      ghostLapS: [NaN, 2],
      ghostCumulativeS: [0, 2],
      totalLaps: 57,
      pitLaps: [1],
      pitLossS: 22,
      pitCompounds: ["HARD"],
    });
    const car = ghostCarFromTick(tick(), null, 1, 57, pb);
    expect(car.driver_number).toBe(0);
    expect(car.full_name).toBe("ARIS");
    expect(car.ghost_in_pits).toBe(true);
    expect(car.is_pitted).toBe(true);
    expect(car.ghost_pit_compound).toBe("HARD");
    expect(car.ghost_skip_seek_jump).toBe(true);
  });
});

describe("PathCarAnimator SEEK_JUMP grace", () => {
  it("does not snap a >0.22 jump when skipSeekJump is set", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const anim = new PathCarAnimator(path, 0, 140);
    anim.onTick(0.01, 0);
    anim.onTick(0.4, 16, { skipSeekJump: true });
    const frac = anim.currentFrac(32);
    expect(frac).toBeGreaterThan(0.01);
    expect(frac).toBeLessThan(0.4);
  });

  it("still snaps a >0.22 jump without skipSeekJump", () => {
    const path = buildPath([0, 10, 10, 0], [0, 0, 10, 10]);
    const anim = new PathCarAnimator(path, 0, 140);
    anim.onTick(0.01, 0);
    anim.onTick(0.4, 16);
    const frac = anim.currentFrac(32);
    expect(frac).toBeGreaterThan(0.3);
  });
});
