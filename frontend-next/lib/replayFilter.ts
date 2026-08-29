import type { CircuitMarker, RoundCard } from "@/lib/types";

/** Replay FastF1 window — keep in sync with backend.calendar.ALLOWED_REPLAY_YEARS. */
export const ALLOWED_REPLAY_YEARS = [2024, 2025, 2026] as const;
export const REPLAY_FROM_YEAR = 2024;
export const REPLAY_YEAR_TOOLTIP = "Replay limited to 2024–2026 for faster loading.";
export const REPLAY_YEAR_BLOCKED_MSG = "Replay is only available for 2024, 2025, and 2026.";

export function isAllowedReplayYear(year: number): boolean {
  return (ALLOWED_REPLAY_YEARS as readonly number[]).includes(year);
}

export function replayYears(_now: Date = new Date()): number[] {
  return [...ALLOWED_REPLAY_YEARS].sort((a, b) => b - a);
}

export function defaultReplayYear(now: Date = new Date()): number {
  const y = now.getUTCFullYear();
  const latestCompleted = now.getUTCMonth() >= 11 ? y : y - 1;
  const allowed = replayYears(now);
  return allowed.find((x) => x <= latestCompleted) ?? allowed[allowed.length - 1] ?? 2025;
}

export function isReplayableRound(round: Pick<RoundCard, "status" | "cancelledReason">): boolean {
  const status = (round.status ?? "COMPLETED").toUpperCase();
  if (status === "CANCELLED" || status === "UPCOMING") return false;
  if (round.cancelledReason) return false;
  return true;
}

export function filterReplayRounds(rounds: RoundCard[]): RoundCard[] {
  return rounds.filter(isReplayableRound);
}

export function startFinishMarker(markers: CircuitMarker[] | undefined, xs: number[], ys: number[]): CircuitMarker {
  const hit = (markers ?? []).find((m) => m.kind === "sf" || m.label.toUpperCase().includes("S/F"));
  if (hit) return hit;
  return { kind: "sf", x: xs[0] ?? 0, y: ys[0] ?? 0, label: "S/F" };
}

export function sfTick(xs: number[], ys: number[], i = 0): { x1: number; y1: number; x2: number; y2: number } {
  const x = xs[i] ?? 0;
  const y = ys[i] ?? 0;
  const nx = xs[i + 1] ?? xs[0] ?? x + 1;
  const ny = ys[i + 1] ?? ys[0] ?? y;
  const dx = nx - x;
  const dy = ny - y;
  const len = Math.hypot(dx, dy) || 1;
  const px = (-dy / len) * 10;
  const py = (dx / len) * 10;
  return { x1: x - px, y1: y - py, x2: x + px, y2: y + py };
}

export function chequeredSfFlag(
  xs: number[],
  ys: number[],
  at?: { x: number; y: number },
): { cx: number; cy: number; angle: number; cell: number; cols: number; rows: number } {
  let i = 0;
  if (at && xs.length) {
    let best = 0;
    let bestD = Infinity;
    for (let k = 0; k < Math.min(xs.length, ys.length); k++) {
      const d = (xs[k] - at.x) ** 2 + (ys[k] - at.y) ** 2;
      if (d < bestD) {
        bestD = d;
        best = k;
      }
    }
    i = best;
  }
  const x = at?.x ?? xs[i] ?? 0;
  const y = at?.y ?? ys[i] ?? 0;
  const nx = xs[i + 1] ?? xs[0] ?? x + 1;
  const ny = ys[i + 1] ?? ys[0] ?? y;
  const angle = (Math.atan2(ny - y, nx - x) * 180) / Math.PI;
  return { cx: x, cy: y, angle, cell: 3.2, cols: 8, rows: 2 };
}
