import { describe, expect, it } from "vitest";
import {
  STANDINGS_YEAR_LIMIT_MSG,
  defaultSeasonYear,
  isSeasonYear,
  parseSeasonYear,
} from "./seasonYears";

describe("isSeasonYear", () => {
  it("allows 2024–2026 only", () => {
    expect(isSeasonYear(2024)).toBe(true);
    expect(isSeasonYear(2025)).toBe(true);
    expect(isSeasonYear(2026)).toBe(true);
    expect(isSeasonYear(2023)).toBe(false);
    expect(isSeasonYear(2027)).toBe(false);
  });
});

describe("defaultSeasonYear", () => {
  it("clamps to the 2024–2026 window", () => {
    expect(defaultSeasonYear(new Date("2023-01-01T00:00:00Z"))).toBe(2024);
    expect(defaultSeasonYear(new Date("2025-06-01T00:00:00Z"))).toBe(2025);
    expect(defaultSeasonYear(new Date("2026-08-27T00:00:00Z"))).toBe(2026);
  });
});

describe("parseSeasonYear", () => {
  it("defaults when the param is missing", () => {
    const parsed = parseSeasonYear(undefined, STANDINGS_YEAR_LIMIT_MSG);
    expect("year" in parsed).toBe(true);
  });

  it("rejects years outside 2024–2026", () => {
    expect(parseSeasonYear("2023", STANDINGS_YEAR_LIMIT_MSG)).toEqual({
      error: STANDINGS_YEAR_LIMIT_MSG,
    });
  });

  it("accepts allowed years", () => {
    expect(parseSeasonYear("2024", STANDINGS_YEAR_LIMIT_MSG)).toEqual({ year: 2024 });
    expect(parseSeasonYear("2026", STANDINGS_YEAR_LIMIT_MSG)).toEqual({ year: 2026 });
  });
});
