/** Header / playback label. Omits a fake denominator when total laps are unknown. */
export function formatLapHeader(currentLap: number, totalLaps: number): string {
  if (totalLaps > 0) return `Lap ${currentLap} / ${totalLaps}`;
  return `Lap ${currentLap}`;
}
