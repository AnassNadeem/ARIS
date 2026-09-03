import { describe, expect, it } from "vitest";
import { formatRaceDate, overlayOfficial2026Date } from "./replayFilter";

describe("overlayOfficial2026Date", () => {
  it("corrects the old 24-round Australia date to 8 Mar", () => {
    const iso = overlayOfficial2026Date(2026, "Albert Park", "2026-03-15T05:00:00Z");
    expect(iso.startsWith("2026-03-08")).toBe(true);
    expect(formatRaceDate(iso)).toBe("8 Mar");
  });

  it("leaves other years alone", () => {
    expect(overlayOfficial2026Date(2025, "Albert Park", "2025-03-16T04:00:00Z")).toBe("2025-03-16T04:00:00Z");
  });
});
