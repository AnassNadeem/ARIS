/** Header / playback label. Omits a fake denominator when total laps are unknown. */
export function formatLapHeader(currentLap: number, totalLaps: number): string {
  if (totalLaps > 0) return `Lap ${currentLap} / ${totalLaps}`;
  return `Lap ${currentLap}`;
}

/** Compact mobile header: `5/57`. Uses live race progress, not a fixed label. */
export function formatLapCompact(currentLap: number, totalLaps: number): string {
  const lap = Math.max(0, currentLap);
  if (totalLaps > 0) return `${lap}/${totalLaps}`;
  return `${lap}`;
}
