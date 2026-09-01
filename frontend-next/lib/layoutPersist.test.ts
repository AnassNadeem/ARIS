import { describe, expect, it } from "vitest";
import { formatLapCompact, formatLapHeader } from "@/lib/formatLap";
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
