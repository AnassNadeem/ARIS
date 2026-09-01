import { explainFeatureEnabled } from "@/lib/api";

export const ANALYTICS_SLOTS_KEY = "aris_analytics_slots_v1";

export const DEFAULT_ANALYTICS_IDS = ["tyredeg", "sectortimes", "gapchart"] as const;

export function defaultAnalyticsIds(): string[] {
  const ids: string[] = [...DEFAULT_ANALYTICS_IDS];
  if (explainFeatureEnabled()) ids.push("explain");
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
