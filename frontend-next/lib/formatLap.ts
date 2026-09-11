/** Header / playback label. Omits a fake denominator when total laps are unknown. */
export function formatLapHeader(currentLap: number, totalLaps: number): string {
  const lap = Math.max(0, currentLap);
  if (totalLaps > 0) return `Lap ${lap} / ${totalLaps}`;
  return `Lap ${lap}`;
}

/** Compact mobile header: `5/57`. Uses live race progress, not a fixed label. */
export function formatLapCompact(currentLap: number, totalLaps: number): string {
  const lap = Math.max(0, currentLap);
  if (totalLaps > 0) return `${lap}/${totalLaps}`;
  return `${lap}`;
}

/** Remaining practice/quali time. Before lights-out the clock sits at the full hour. */
export function sessionRemainingMs(
  startIso: string | null | undefined,
  durationMs: number,
  now = Date.now(),
): number {
  const dur = Math.max(0, durationMs);
  if (!startIso) return dur;
  const start = new Date(startIso).getTime();
  if (!Number.isFinite(start)) return dur;
  if (now < start) return dur;
  return Math.max(0, start + dur - now);
}

/** `1:00:00` while ≥ 1h, otherwise `MM:SS`. */
export function formatSessionClock(remainingMs: number): string {
  const total = Math.max(0, Math.floor(remainingMs / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}
