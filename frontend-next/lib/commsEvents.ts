import type { ARISRecommendation, CarState, CommsEntry, RacePhase } from "@/lib/types";

export type CommsSnapshot = {
  lap: number;
  phase: RacePhase;
  rainfall: boolean;
  cars: Record<string, CarState>;
  focus: string | null;
  rec: ARISRecommendation | null;
};

function id(prefix: string, lap: number, extra: string): string {
  return `${prefix}-L${lap}-${extra}`;
}

function isRealDriver(c: CarState): boolean {
  return !c.is_ghost && !c.driver_code.startsWith("A_");
}

function carAhead(cars: Record<string, CarState>, focus: CarState): CarState | null {
  const pos = focus.position;
  if (pos == null) return null;
  return Object.values(cars).find((c) => c.position === pos - 1 && isRealDriver(c)) ?? null;
}

function carBehind(cars: Record<string, CarState>, focus: CarState): CarState | null {
  const pos = focus.position;
  if (pos == null) return null;
  return Object.values(cars).find((c) => c.position === pos + 1 && isRealDriver(c)) ?? null;
}

function fastestLapHolder(cars: Record<string, CarState>): string | null {
  const row = Object.values(cars).find((c) => c.fastest_lap && isRealDriver(c));
  return row?.driver_code ?? null;
}

function dnfCodes(cars: Record<string, CarState>): string[] {
  return Object.values(cars)
    .filter((c) => (c.is_dnf || c.status === "DNF" || c.status === "DNS") && isRealDriver(c))
    .map((c) => c.driver_code)
    .sort();
}

function fmtGap(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return "—";
  const sign = s > 0 ? "+" : "";
  return `${sign}${s.toFixed(1)}s`;
}

/**
 * Diff two race snapshots into short Main Comms lines.
 * Pure: no store, no I/O — unit-tested in commsEvents.test.ts.
 */
export function detectCommsEvents(prev: CommsSnapshot | null, next: CommsSnapshot, now = Date.now()): CommsEntry[] {
  const out: CommsEntry[] = [];
  const focusCode = next.focus;
  const focus = focusCode ? next.cars[focusCode] : null;

  if (prev?.phase !== next.phase) {
    if (next.phase === "SC") {
      out.push({
        id: id("sc", next.lap, next.phase),
        lap: next.lap,
        source: "FIELD",
        text: `Lap ${next.lap}: SC deployed. Pitting now saves ~9 s vs green.`,
        timestamp: now,
      });
    } else if (next.phase === "VSC") {
      out.push({
        id: id("vsc", next.lap, next.phase),
        lap: next.lap,
        source: "FIELD",
        text: `Lap ${next.lap}: VSC deployed. Cheap pit window — delta limited.`,
        timestamp: now,
      });
    } else if (next.phase === "RED_FLAG") {
      out.push({
        id: id("red", next.lap, next.phase),
        lap: next.lap,
        source: "FIELD",
        text: `Lap ${next.lap}: Red flag. Free tyre change. Strategy reset.`,
        timestamp: now,
      });
    } else if (prev && next.phase === "GREEN" && (prev.phase === "SC" || prev.phase === "VSC" || prev.phase === "RED_FLAG")) {
      out.push({
        id: id("green", next.lap, next.phase),
        lap: next.lap,
        source: "FIELD",
        text: `Lap ${next.lap}: Green flag. Racing resumes.`,
        timestamp: now,
      });
    }
  }

  if (prev && prev.rainfall !== next.rainfall) {
    out.push({
      id: id("wx", next.lap, next.rainfall ? "rain" : "dry"),
      lap: next.lap,
      source: "FIELD",
      text: next.rainfall ? `Lap ${next.lap}: Rain started.` : `Lap ${next.lap}: Rain stopped.`,
      timestamp: now,
    });
  }

  const fl = fastestLapHolder(next.cars);
  const prevFl = prev ? fastestLapHolder(prev.cars) : null;
  if (fl && fl !== prevFl) {
    out.push({
      id: id("fl", next.lap, fl),
      lap: next.lap,
      source: "FIELD",
      text: `Lap ${next.lap}: Fastest lap: ${fl}.`,
      timestamp: now,
    });
  }

  const nowDnf = dnfCodes(next.cars);
  const prevDnf = prev ? new Set(dnfCodes(prev.cars)) : new Set<string>();
  for (const code of nowDnf) {
    if (!prevDnf.has(code)) {
      out.push({
        id: id("dnf", next.lap, code),
        lap: next.lap,
        source: "FIELD",
        text: `Lap ${next.lap}: DNF: ${code}.`,
        timestamp: now,
      });
    }
  }

  if (next.rec && next.rec.id !== prev?.rec?.id) {
    const tactical = (next.rec.tactical || "").toLowerCase();
    const evidence = (next.rec.evidence || "").toLowerCase();
    const ahead = focus ? carAhead(next.cars, focus) : null;
    if (tactical.includes("undercut") || evidence.includes("undercut")) {
      const vs = ahead?.driver_code ?? "the car ahead";
      const gain = Math.abs(next.rec.delta_vs_stay_out_s);
      out.push({
        id: id("uc", next.lap, next.rec.id),
        lap: next.lap,
        source: "ARIS",
        text: `Lap ${next.lap}: Undercut opportunity vs ${vs}. Pit now for ${next.rec.action.pit_compound ?? "fresh tyre"} gains ~${gain.toFixed(1)} s.`,
        timestamp: now,
        recommendationId: next.rec.id,
      });
    } else if (tactical.includes("overcut") || evidence.includes("overcut")) {
      const vs = ahead?.driver_code ?? "the car ahead";
      out.push({
        id: id("oc", next.lap, next.rec.id),
        lap: next.lap,
        source: "ARIS",
        text: `Lap ${next.lap}: Overcut window vs ${vs}. Stay out and push.`,
        timestamp: now,
        recommendationId: next.rec.id,
      });
    }
  }

  if (focus && prev?.lap !== next.lap) {
    const ahead = carAhead(next.cars, focus);
    if (ahead) {
      const losses: string[] = [];
      const pairs: Array<["S1" | "S2" | "S3", number | null | undefined, number | null | undefined]> = [
        ["S1", focus.sector1_s, ahead.sector1_s],
        ["S2", focus.sector2_s, ahead.sector2_s],
        ["S3", focus.sector3_s, ahead.sector3_s],
      ];
      for (const [name, ours, theirs] of pairs) {
        if (ours != null && theirs != null && ours - theirs >= 0.15) {
          losses.push(`Lost ${(ours - theirs).toFixed(1)} s in ${name} vs ${ahead.driver_code}`);
        }
      }
      if (losses.length) {
        out.push({
          id: id("sec", next.lap, focus.driver_code),
          lap: next.lap,
          source: "ARIS",
          text: `Lap ${next.lap}: ${losses[0]}. Consider pushing in ${losses[0].includes("S2") ? "S2" : losses[0].includes("S3") ? "S3" : "S1"}.`,
          timestamp: now,
        });
      }
    }

    if (next.lap > 1 && next.lap % 5 === 0) {
      const ahead = carAhead(next.cars, focus);
      const behind = carBehind(next.cars, focus);
      out.push({
        id: id("gap", next.lap, focus.driver_code),
        lap: next.lap,
        source: "ARIS",
        text: `Lap ${next.lap}: Gap to leader ${fmtGap(focus.gap_to_leader_s)}${
          ahead ? ` · ahead ${ahead.driver_code} ${fmtGap(focus.gap_ahead_s)}` : ""
        }${behind ? ` · behind ${behind.driver_code}` : ""}.`,
        timestamp: now,
      });
    }
  }

  return out;
}
