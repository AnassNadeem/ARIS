import type { CircuitCoords } from "@/lib/types";

const PREFIX = "aris.circuit.v2.";
export const FULL_OUTLINE_MIN_POINTS = 60;
/** R2 field.outline is a fallback only; never replace a loaded circuit map. */
export const R2_OUTLINE_FALLBACK_MAX_POINTS = 50;

export function isFullCircuitOutline(coords: { x?: number[]; y?: number[] } | null | undefined): boolean {
  const n = coords?.x?.length ?? 0;
  const m = coords?.y?.length ?? 0;
  return n >= FULL_OUTLINE_MIN_POINTS && n === m;
}

export function shouldApplyFallbackOutline(existing: { x?: number[] } | null | undefined): boolean {
  return (existing?.x?.length ?? 0) < R2_OUTLINE_FALLBACK_MAX_POINTS;
}

function lsGet(key: string): string | null {
  try {
    return globalThis.localStorage?.getItem(key) ?? null;
  } catch {
    return null;
  }
}

function lsSet(key: string, value: string): void {
  try {
    globalThis.localStorage?.setItem(key, value);
  } catch {
    /* quota / private mode */
  }
}

export function circuitCacheKey(year: number, round: number): string {
  return `${PREFIX}${year}.${round}`;
}

export function readCircuitCache(year: number, round: number): CircuitCoords | null {
  const raw = lsGet(circuitCacheKey(year, round));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as CircuitCoords;
    if (isFullCircuitOutline(parsed)) return parsed;
  } catch {
    /* ignore */
  }
  return null;
}

export function writeCircuitCache(year: number, round: number, coords: CircuitCoords): void {
  if (!isFullCircuitOutline(coords)) return;
  lsSet(circuitCacheKey(year, round), JSON.stringify(coords));
}
