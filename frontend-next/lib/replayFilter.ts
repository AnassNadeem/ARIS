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

/**
 * Rounds/venues dropped from the FIA calendar. Hide leftover FastF1 packs
 * (Imola, Sakhir, Jeddah) even if an API still marks them COMPLETED.
 */
export const CANCELLED_REPLAY_CIRCUITS: ReadonlySet<string> = new Set([
  "imola",
  "sakhir",
  "jeddah",
]);

export const CANCELLED_REPLAY_ROUNDS: ReadonlySet<string> = new Set();

export function replayRoundKey(year: number, round: number): string {
  return `${year}-${round}`;
}

function circuitSlug(name: string | null | undefined): string {
  return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
}

/** Format a race ISO date as "8 Mar" using the calendar day, not local TZ. */
export function formatRaceDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (m) {
    const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", timeZone: "UTC" });
}

function utcDayMs(d: Date): number {
  return Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate());
}

/** True when the race's calendar date is after `now` (UTC day). Same-day races stay visible. */
export function isFutureRaceDate(iso: string | null | undefined, now: Date = new Date()): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return false;
  return utcDayMs(d) > utcDayMs(now);
}

export type ReplayRoundFilterOpts = {
  year?: number;
  now?: Date;
};

export function isReplayableRound(
  round: Pick<RoundCard, "status" | "cancelledReason" | "date" | "round"> &
    Partial<Pick<RoundCard, "circuitName">>,
  opts?: ReplayRoundFilterOpts,
): boolean {
  const status = (round.status ?? "COMPLETED").toUpperCase();
  if (status === "CANCELLED" || status === "UPCOMING") return false;
  if (round.cancelledReason) return false;
  const year = opts?.year;
  if (year != null && CANCELLED_REPLAY_ROUNDS.has(replayRoundKey(year, round.round))) return false;
  if (year === 2026) {
    const slug = circuitSlug(round.circuitName);
    if ([...CANCELLED_REPLAY_CIRCUITS].some((c) => slug.includes(c))) return false;
  }
  if (isFutureRaceDate(round.date, opts?.now ?? new Date())) return false;
  return true;
}

export function filterReplayRounds(rounds: RoundCard[], opts?: ReplayRoundFilterOpts): RoundCard[] {
  return rounds.filter((r) => isReplayableRound(r, opts));
}

/** Drop rounds whose race_field.json is confirmed missing. `null` (unknown) keeps the row. */
export function keepRoundsWithPack(
  rounds: RoundCard[],
  existsByRound: ReadonlyMap<number, boolean | null>,
): RoundCard[] {
  return rounds.filter((r) => existsByRound.get(r.round) !== false);
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
