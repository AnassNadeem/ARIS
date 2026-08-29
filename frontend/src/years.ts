export const REPLAY_FROM_YEAR = 2018;

export function currentSeasonYear(): number {
  return Math.max(new Date().getUTCFullYear(), 2026);
}

export function replayYears(): number[] {
  const end = currentSeasonYear();
  const years: number[] = [];
  for (let y = end; y >= REPLAY_FROM_YEAR; y--) years.push(y);
  return years;
}

export function clampReplayYear(year: number): number {
  const end = currentSeasonYear();
  if (year < REPLAY_FROM_YEAR) return REPLAY_FROM_YEAR;
  if (year > end) return end;
  return year;
}
