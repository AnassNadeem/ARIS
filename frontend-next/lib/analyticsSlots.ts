export const ANALYTICS_SLOTS_KEY = "aris_analytics_slots_v2";

export const DEFAULT_ANALYTICS_IDS = ["tyredeg", "sectortimes", "gapchart"] as const;

export function defaultAnalyticsIds(opts?: { arisOn?: boolean }): string[] {
  const ids: string[] = [...DEFAULT_ANALYTICS_IDS];
  if (opts?.arisOn && !ids.includes("ghostdelta")) ids.unshift("ghostdelta");
  return ids;
}

export function loadAnalyticsSlots(): string[] | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ANALYTICS_SLOTS_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return null;
    return parsed.filter((id): id is string => typeof id === "string" && id.length > 0);
  } catch {
    return null;
  }
}

export function saveAnalyticsSlots(ids: string[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ANALYTICS_SLOTS_KEY, JSON.stringify(ids));
  } catch {
    // quota / private mode
  }
}

export function clearAnalyticsSlots(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ANALYTICS_SLOTS_KEY);
  } catch {
    // private mode
  }
}

/** Swap a slot one place up (`-1`) or down (`1`). No-op at the ends. */
export function moveAnalyticsSlot(ids: string[], componentId: string, direction: -1 | 1): string[] {
  const i = ids.indexOf(componentId);
  const j = i + direction;
  if (i < 0 || j < 0 || j >= ids.length) return ids;
  const next = [...ids];
  const a = next[i];
  const b = next[j];
  if (a === undefined || b === undefined) return ids;
  next[i] = b;
  next[j] = a;
  return next;
}
