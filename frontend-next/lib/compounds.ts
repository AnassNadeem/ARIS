import type { Compound } from "@/lib/types";

export function normalizeCompound(raw: string | null | undefined): Compound {
  const u = (raw ?? "").toUpperCase();
  if (u === "S" || u.startsWith("SOFT")) return "SOFT";
  if (u === "M" || u.startsWith("MEDIUM")) return "MEDIUM";
  if (u === "H" || u.startsWith("HARD")) return "HARD";
  if (u === "I" || u.startsWith("INTER")) return "INTERMEDIATE";
  if (u === "W" || u.startsWith("WET")) return "WET";
  return "HARD";
}

export function msToSeconds(ms: number | null | undefined): number | null {
  if (ms == null || Number.isNaN(ms)) return null;
  return ms / 1000;
}
