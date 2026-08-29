import { describe, expect, it } from "vitest";
import { formatLapHeader } from "@/lib/formatLap";
import { isPersistedLayout } from "@/lib/layoutPersist";

describe("formatLapHeader", () => {
  it("omits the denominator when total laps are unknown", () => {
    expect(formatLapHeader(3, 0)).toBe("Lap 3");
  });

  it("shows current / total when the session distance is known", () => {
    expect(formatLapHeader(12, 72)).toBe("Lap 12 / 72");
  });
});

describe("isPersistedLayout", () => {
  it("accepts a flexlayout row root", () => {
    expect(isPersistedLayout({ layout: { type: "row", children: [] } })).toBe(true);
  });

  it("rejects junk", () => {
    expect(isPersistedLayout(null)).toBe(false);
    expect(isPersistedLayout({ layout: { type: "tabset" } })).toBe(false);
  });
});
