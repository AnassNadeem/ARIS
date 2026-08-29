export const SEASON_YEARS = [2024, 2025, 2026] as const;
export type SeasonYear = (typeof SEASON_YEARS)[number];

export const STANDINGS_YEAR_LIMIT_MSG = "Standings only available for 2024, 2025, and 2026.";
export const STANDINGS_2026_UNAVAILABLE = "2026 standings not yet available.";

export function isSeasonYear(year: number): year is SeasonYear {
  return (SEASON_YEARS as readonly number[]).includes(year);
}

export function defaultSeasonYear(now: Date = new Date()): SeasonYear {
  const y = now.getUTCFullYear();
  if (y <= 2024) return 2024;
  if (y >= 2026) return 2026;
  return 2025;
}

export function parseSeasonYear(
  raw: string | string[] | undefined | null,
  limitMessage: string,
): { year: SeasonYear } | { error: string } {
  if (raw == null || raw === "" || (Array.isArray(raw) && raw.length === 0)) {
    return { year: defaultSeasonYear() };
  }
  const s = Array.isArray(raw) ? raw[0] : raw;
  const n = Number(s);
  if (!Number.isInteger(n) || !isSeasonYear(n)) {
    return { error: limitMessage };
  }
  return { year: n };
}
