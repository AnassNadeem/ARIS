import type { CarState, RacePhase, SessionMeta } from "@/lib/types";

export type CopilotIntent = "factual_live" | "factual_history" | "strategic";

export interface FactualRaceSnapshot {
  cars: Record<string, CarState>;
  currentLap: number;
  totalLaps: number;
  racePhase: RacePhase;
  rainfall: boolean;
  focusDriver: string | null;
  session: SessionMeta | null;
}

const DRIVER_RE = /\b([A-Za-z]{3})\b/g;
const KNOWN = new Set([
  "VER", "PER", "SAI", "LEC", "RUS", "NOR", "HAM", "PIA", "ALO", "GAS",
  "STR", "RIC", "TSU", "ALB", "ZHO", "BOT", "OCO", "MAG", "HUL", "SAR",
  "COL", "BEA", "ANT", "HAD", "LAW", "DOO", "DEV", "MSC", "BOR", "BEA",
]);

const STRATEGIC_RE =
  /\b(should we|recommend|best strategy|pit now|box now|extend|undercut window|overcut|cover|from here|what if|monte carlo|p\(best\))\b/i;

const HISTORY_RE =
  /\b(who won|winner|last year|podium|classified|finished p\d|who won last)\b/i;

const LIVE_FACT_RE =
  /\b(gap to|who's leading|who is leading|who'?s the leader|who is the leader|who'?s in p|who is in p|p\d\b|position|tyre life|tire life|what(?:'s| is) the gap|raining|safety car|red flag|vsc|who'?s ahead|laps remaining|current lap)\b/i;

export function driversInText(question: string): string[] {
  const out: string[] = [];
  const re = new RegExp(DRIVER_RE.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(question))) {
    const code = m[1].toUpperCase();
    if (KNOWN.has(code) && !out.includes(code)) out.push(code);
  }
  return out;
}

export function classifyIntent(question: string): CopilotIntent {
  const q = question.trim();
  if (!q) return "strategic";
  if (STRATEGIC_RE.test(q)) return "strategic";
  if (HISTORY_RE.test(q)) return "factual_history";
  if (LIVE_FACT_RE.test(q)) return "factual_live";
  return "strategic";
}

function classifiedCars(cars: Record<string, CarState>): CarState[] {
  return Object.values(cars)
    .filter((c) => !c.is_ghost && !c.driver_code.startsWith("A_") && !c.is_dnf && c.status !== "DNS")
    .sort((a, b) => (a.position ?? 99) - (b.position ?? 99));
}

function fmtGap(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return "n/a";
  if (v === 0) return "the lead";
  return `+${v.toFixed(1)}s`;
}

/** Deterministic answer from the live timing store. Null = not a live factual query. */
export function answerFactualLive(question: string, snap: FactualRaceSnapshot): string | null {
  if (classifyIntent(question) !== "factual_live") return null;
  const q = question.toLowerCase();
  const field = classifiedCars(snap.cars);
  const leader = field.find((c) => c.position === 1) ?? field[0] ?? null;
  const focusCode = snap.focusDriver?.toUpperCase() ?? null;
  const named = driversInText(question);
  const focus = (named[0] && snap.cars[named[0]]) || (focusCode ? snap.cars[focusCode] : null) || null;

  if (/\b(rain|raining|wet)\b/.test(q) && !/two compound/.test(q)) {
    return snap.rainfall
      ? `Rain is flagged on track (lap ${snap.currentLap}).`
      : `No rainfall flagged at lap ${snap.currentLap}.`;
  }
  if (/\b(safety car|red flag|vsc)\b/.test(q) && !/risk/.test(q)) {
    if (snap.racePhase === "SC") return `Safety car is deployed (lap ${snap.currentLap}).`;
    if (snap.racePhase === "VSC") return `Virtual safety car is deployed (lap ${snap.currentLap}).`;
    if (snap.racePhase === "RED_FLAG") return `Red flag (lap ${snap.currentLap}).`;
    return `Green flag — no SC/VSC/red at lap ${snap.currentLap}.`;
  }
  if (/\bwho(?:'s| is) (?:the )?lead/.test(q) || /\bwho(?:'s| is) leading\b/.test(q)) {
    if (!leader) return "No leader in the current timing frame.";
    return `${leader.driver_code} is leading (P1) on ${leader.compound}, tyre life ${leader.tyre_life}.`;
  }
  const pMatch = q.match(/\bp(\d{1,2})\b/);
  if (pMatch && (q.includes("who") || q.includes("in p"))) {
    const pos = Number(pMatch[1]);
    const car = field.find((c) => c.position === pos);
    if (!car) return `No car is classified P${pos} in the current frame.`;
    return `P${pos} is ${car.driver_code} on ${car.compound}, tyre life ${car.tyre_life}, gap ${fmtGap(car.gap_to_leader_s)}.`;
  }
  if (/\bgap\b/.test(q)) {
    if (/\bleader\b/.test(q)) {
      if (!focus) return leader ? `${leader.driver_code} is the leader.` : "Gap to leader is unavailable.";
      if (focus.position === 1) return `${focus.driver_code} is the leader.`;
      return `${focus.driver_code} is P${focus.position}, ${fmtGap(focus.gap_to_leader_s)} to the leader.`;
    }
    const vs = named.find((c) => c !== (focus?.driver_code ?? focusCode));
    if (vs && focus && snap.cars[vs]) {
      const a = focus.gap_to_leader_s;
      const b = snap.cars[vs].gap_to_leader_s;
      if (a == null || b == null) return `Gap between ${focus.driver_code} and ${vs} is unavailable.`;
      const d = a - b;
      const mag = Math.abs(d).toFixed(1);
      if (Math.abs(d) < 0.05) return `${focus.driver_code} and ${vs} are effectively side by side.`;
      return d > 0
        ? `Gap from ${focus.driver_code} to ${vs} is ${mag}s (${focus.driver_code} behind).`
        : `Gap from ${focus.driver_code} to ${vs} is ${mag}s (${focus.driver_code} ahead).`;
    }
    if (focus) {
      const ahead = fmtGap(focus.gap_ahead_s);
      const lead = fmtGap(focus.gap_to_leader_s);
      return `${focus.driver_code} is P${focus.position}: ${ahead === "the lead" ? "leader" : `${ahead} to the car ahead`}, ${lead} to the leader.`;
    }
    if (leader) return `${leader.driver_code} leads. Gap data for a focus driver is unavailable.`;
  }
  if (/\b(tyre|tire) life\b/.test(q) || (/\b(tyre|tire|compound)\b/.test(q) && named.length)) {
    const car = named[0] ? snap.cars[named[0]] : focus;
    if (!car) return "Tyre data is unavailable for that driver in the current frame.";
    return `${car.driver_code} is on ${car.compound}, tyre life ${car.tyre_life}.`;
  }
  if (/\b(current lap|laps remaining|laps left)\b/.test(q)) {
    const left = Math.max(0, (snap.totalLaps || 0) - (snap.currentLap || 0));
    return snap.totalLaps
      ? `Lap ${snap.currentLap} of ${snap.totalLaps}. ${left} laps remaining.`
      : `Lap ${snap.currentLap}.`;
  }
  if (/\bposition\b/.test(q) && focus) {
    return `${focus.driver_code} is P${focus.position}, ${fmtGap(focus.gap_to_leader_s)} to the leader.`;
  }
  return null;
}

export function historyLookupHint(question: string, session: SessionMeta | null): {
  year: number;
  round: number;
  lastYear: boolean;
} | null {
  if (classifyIntent(question) !== "factual_history") return null;
  if (!session) return null;
  const yearMatch = question.match(/\b(20\d{2})\b/);
  const lastYear = /last year/i.test(question);
  const year = yearMatch ? Number(yearMatch[1]) : lastYear ? session.year - 1 : session.year;
  return { year, round: session.round, lastYear };
}
