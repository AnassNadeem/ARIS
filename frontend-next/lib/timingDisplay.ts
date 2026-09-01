import type { SectorColour } from "@/lib/types";

export function sectorClass(colour: SectorColour | undefined): string {
  switch (colour) {
    case "purple":
      return "text-[#c44dff] font-semibold";
    case "green":
      return "text-[#39ff14]";
    case "yellow":
      return "text-[#f5a623]";
    default:
      return "text-muted";
  }
}

export function fmtLapTime(v: number | null | undefined): string {
  if (v == null) return "—";
  const m = Math.floor(v / 60);
  const s = (v % 60).toFixed(3);
  return `${m}:${s.padStart(6, "0")}`;
}

export function fmtSectorTime(v: number | null | undefined): string {
  if (v == null) return "—";
  if (v >= 60) return fmtLapTime(v);
  return v.toFixed(3);
}

export function fmtGap(v: number | null | undefined, lapsDown?: number | null): string {
  if (lapsDown && lapsDown > 0) return `+${lapsDown}L`;
  if (v == null) return "—";
  if (!(v > 0)) return "LEADER";
  return `+${v.toFixed(1)}s`;
}

export function driverOutOfRace(status: string | undefined, isDnf: boolean | undefined): boolean {
  return isDnf === true || status === "DNF" || status === "DNS";
}
