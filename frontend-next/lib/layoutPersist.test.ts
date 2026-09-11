import { describe, expect, it } from "vitest";
import { formatLapCompact, formatLapHeader, formatSessionClock, liveSessionRemainingMs, sessionRemainingMs } from "@/lib/formatLap";
import { componentsFromLayoutJson, isPersistedLayout, stripAnalyticsAddFromLayout } from "@/lib/layoutPersist";

describe("formatLapHeader", () => {
  it("omits the denominator when total laps are unknown", () => {
    expect(formatLapHeader(3, 0)).toBe("Lap 3");
  });

  it("shows current / total when the session distance is known", () => {
    expect(formatLapHeader(12, 72)).toBe("Lap 12 / 72");
  });

  it("formats a compact live fraction for the mobile header", () => {
    expect(formatLapCompact(5, 57)).toBe("5/57");
    expect(formatLapCompact(3, 0)).toBe("3");
  });
});

describe("session clock", () => {
  it("sits at the full hour before lights-out and counts down after", () => {
    const start = "2026-09-11T15:00:00Z";
    const hour = 60 * 60_000;
    expect(sessionRemainingMs(start, hour, Date.parse("2026-09-11T14:59:00Z"))).toBe(hour);
    expect(sessionRemainingMs(start, hour, Date.parse("2026-09-11T15:27:46Z"))).toBe(
      Date.parse("2026-09-11T16:00:00Z") - Date.parse("2026-09-11T15:27:46Z"),
    );
    expect(sessionRemainingMs(start, hour, Date.parse("2026-09-11T16:05:00Z"))).toBe(0);
  });

  it("formats 1:00:00 while a full hour remains, then MM:SS", () => {
    expect(formatSessionClock(60 * 60_000)).toBe("1:00:00");
    expect(formatSessionClock(32 * 60_000 + 14_000)).toBe("32:14");
    expect(formatSessionClock(0)).toBe("0:00");
  });

  it("freezes the live remaining clock under a red flag", () => {
    const remainingAt = Date.parse("2026-09-11T15:20:00Z");
    const later = Date.parse("2026-09-11T15:25:00Z");
    expect(
      liveSessionRemainingMs({
        remainingS: 2400,
        remainingAtMs: remainingAt,
        frozen: true,
        now: later,
      }),
    ).toBe(2400_000);
    expect(
      liveSessionRemainingMs({
        remainingS: 2400,
        remainingAtMs: remainingAt,
        frozen: false,
        now: later,
      }),
    ).toBe(2100_000);
  });
});

describe("isPersistedLayout", () => {
  it("accepts a flexlayout row root", () => {
    expect(isPersistedLayout({ layout: { type: "row", children: [] } })).toBe(true);
  });

  it("lists tab component ids from nested rows", () => {
    expect(
      componentsFromLayoutJson({
        layout: {
          type: "row",
          children: [
            { type: "tabset", children: [{ type: "tab", component: "tyredeg" }] },
            { type: "tabset", children: [{ type: "tab", component: "analytics-add" }] },
          ],
        },
      }),
    ).toEqual(["tyredeg", "analytics-add"]);
  });

  it("rejects junk", () => {
    expect(isPersistedLayout(null)).toBe(false);
    expect(isPersistedLayout({ layout: { type: "tabset" } })).toBe(false);
  });
});

describe("stripAnalyticsAddFromLayout", () => {
  it("removes the analytics-add tab and its empty tabset", () => {
    const cleaned = stripAnalyticsAddFromLayout({
      layout: {
        type: "row",
        children: [
          { type: "tabset", children: [{ type: "tab", component: "tyredeg" }] },
          {
            type: "tabset",
            id: "analytics-add-tabset",
            children: [{ type: "tab", component: "analytics-add" }],
          },
        ],
      },
    });
    expect(componentsFromLayoutJson(cleaned)).toEqual(["tyredeg"]);
  });
});
