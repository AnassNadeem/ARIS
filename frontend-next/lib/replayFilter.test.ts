import { describe, expect, it } from "vitest";
import {
  formatRaceDate,
  hoursSinceRaceEnd,
  isReplayProcessing,
  keepRoundsWithPack,
  overlayOfficial2026Date,
} from "./replayFilter";
import type { RoundCard } from "./types";

describe("overlayOfficial2026Date", () => {
  it("corrects the old 24-round Australia date to 8 Mar", () => {
    const iso = overlayOfficial2026Date(2026, "Albert Park", "2026-03-15T05:00:00Z");
    expect(iso.startsWith("2026-03-08")).toBe(true);
    expect(formatRaceDate(iso)).toBe("8 Mar");
  });

  it("corrects Melbourne circuit naming to 8 Mar", () => {
    const iso = overlayOfficial2026Date(2026, "Melbourne Grand Prix Circuit", "2026-03-15T05:00:00Z");
    expect(formatRaceDate(iso)).toBe("8 Mar");
  });

  it("leaves other years alone", () => {
    expect(overlayOfficial2026Date(2025, "Albert Park", "2025-03-16T04:00:00Z")).toBe("2025-03-16T04:00:00Z");
  });
});

describe("replay processing window", () => {
  const monzaStart = "2026-09-06T13:00:00Z";

  it("is processing a few hours after race end without a pack", () => {
    const now = new Date("2026-09-06T18:00:00Z");
    expect(isReplayProcessing(monzaStart, now)).toBe(true);
    expect(hoursSinceRaceEnd(monzaStart, now)).toBeGreaterThan(2);
  });

  it("stops processing after 48h", () => {
    const now = new Date("2026-09-09T00:00:00Z");
    expect(isReplayProcessing(monzaStart, now)).toBe(false);
  });

  it("keeps missing-pack rounds while processing", () => {
    const rounds = [{ round: 16, date: monzaStart } as RoundCard];
    const exists = new Map<number, boolean | null>([[16, false]]);
    const now = new Date("2026-09-06T18:00:00Z");
    expect(keepRoundsWithPack(rounds, exists, now)).toHaveLength(1);
    expect(keepRoundsWithPack(rounds, exists, new Date("2026-09-10T12:00:00Z"))).toHaveLength(0);
  });
});
