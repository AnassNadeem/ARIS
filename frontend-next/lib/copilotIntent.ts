import type { ARISRecommendation, CarState, RacePhase, SessionMeta } from "@/lib/types";

export type CopilotIntent = "factual_live" | "factual_history" | "strategic";

export interface FactualRaceSnapshot {
  cars: Record<string, CarState>;
  currentLap: number;
  totalLaps: number;
  racePhase: RacePhase;
  rainfall: boolean;
  focusDriver: string | null;
  session: SessionMeta | null;
  lastRecommendation?: ARISRecommendation | null;
  ghostPosition?: number | null;
}

const DRIVER_RE = /\b([A-Za-z]{3})\b/g;
const KNOWN = new Set([
  "VER", "PER", "SAI", "LEC", "RUS", "NOR", "HAM", "PIA", "ALO", "GAS",
  "STR", "RIC", "TSU", "ALB", "ZHO", "BOT", "OCO", "MAG", "HUL", "SAR",
  "COL", "BEA", "ANT", "HAD", "LAW", "DOO", "DEV", "MSC", "BOR", "BEA",
]);

/** Surnames and common first names → code. Only used when that code is on the field. */
const NAME_ALIASES: Record<string, string> = {
  verstappen: "VER",
  max: "VER",
  norris: "NOR",
  lando: "NOR",
  hamilton: "HAM",
  lewis: "HAM",
  leclerc: "LEC",
  charles: "LEC",
  russell: "RUS",
  george: "RUS",
  piastri: "PIA",
  oscar: "PIA",
  alonso: "ALO",
  fernando: "ALO",
  sainz: "SAI",
  carlos: "SAI",
  antonelli: "ANT",
  kimi: "ANT",
  hulkenberg: "HUL",
  nico: "HUL",
  gasly: "GAS",
  pierre: "GAS",
  albon: "ALB",
  hadjar: "HAD",
  lawson: "LAW",
  bearman: "BEA",
  ocon: "OCO",
  esteban: "OCO",
  stroll: "STR",
  lance: "STR",
  tsunoda: "TSU",
  yuki: "TSU",
  colapinto: "COL",
  bottas: "BOT",
  valtteri: "BOT",
};

const STRATEGIC_RE =
  /\b(should we|recommend|best strategy|pit now|box now|extend|undercut window|overcut|cover|from here|what if|monte carlo|p\(best\))\b/i;

const HISTORY_RE =
  /\b(who won|winner|last year|podium|classified|finished p\d|who won last)\b/i;

const LIVE_FACT_RE =
  /\b(gap to|who's leading|who is leading|who'?s the leader|who is the leader|who is in the lead|who'?s in the lead|who leads|who'?s in p|who is in p|p\d\b|position|tyres?|tires?|compound|rubber|tyre life|tire life|what(?:'s| is) the gap|raining|safety car|red flag|vsc|who'?s ahead|laps remaining|laps left|how many laps|what lap is it|current lap|is there a safety car)\b/i;

const PIT_NOW_RE =
  /\b(should i pit|should we pit|pit now|box now|pit window)\b/i;

const ARIS_THINK_RE =
  /\b(what does aris think|aris recommendation|aris suggest|aris suggests|aris recommended|aris recommend)\b/i;

const WHY_STRATEGY_RE =
  /\bwhy\b.*\b(pit|recommend|strategy|suggest|box)\b|\bwhy\b.*\blap\s+\d+|\bwhat lap\b.*\b(pit|recommend|box)/i;

const NO_REC =
  "ARIS has not made a recommendation yet. Start ARIS and begin the race to see strategy cards.";

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

function fmtDelta(v: number): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(1)}`;
}

function confidencePct(rec: ARISRecommendation): string {
  const raw = rec.rank_score;
  if (raw > 0 && raw <= 1) return `${Math.round(raw * 100)}%`;
  if (raw > 1) return `${Math.round(raw)}%`;
  return "n/a";
}

function appendGhost(text: string, snap: FactualRaceSnapshot): string {
  const pos = snap.ghostPosition;
  if (pos == null || !Number.isFinite(pos) || pos <= 0) return text;
  return `${text} ARIS ghost is currently P${pos}.`;
}

/**
 * Resolve a driver mentioned in the question. `missingNamed` is true when the
 * user named someone who is not in the current timing frame — callers should
 * fall through to the API instead of answering from the focus car.
 */
function resolveMentionedDriver(
  question: string,
  snap: FactualRaceSnapshot,
): { car: CarState | null; missingNamed: boolean } {
  const q = question.toLowerCase();
  const field = classifiedCars(snap.cars);

  const codes = driversInText(question);
  for (const code of codes) {
    const car = field.find((c) => c.driver_code === code) ?? snap.cars[code] ?? null;
    if (car && !car.is_ghost && !car.driver_code.startsWith("A_")) return { car, missingNamed: false };
    if (KNOWN.has(code)) return { car: null, missingNamed: true };
  }

  for (const [alias, code] of Object.entries(NAME_ALIASES)) {
    if (!new RegExp(`\\b${alias}\\b`, "i").test(q)) continue;
    const car = field.find((c) => c.driver_code === code) ?? snap.cars[code] ?? null;
    if (car && !car.is_ghost) return { car, missingNamed: false };
    return { car: null, missingNamed: true };
  }

  for (const car of field) {
    const parts = (car.full_name || "").toLowerCase().split(/\s+/).filter((p) => p.length >= 3);
    if (parts.some((p) => new RegExp(`\\b${p.replace(/[^a-z]/g, "")}\\b`, "i").test(q))) {
      return { car, missingNamed: false };
    }
  }

  return { car: null, missingNamed: false };
}

function focusCar(snap: FactualRaceSnapshot): CarState | null {
  const code = snap.focusDriver?.toUpperCase() ?? null;
  if (!code) return null;
  const car = snap.cars[code];
  if (!car || car.is_ghost || car.driver_code.startsWith("A_")) return null;
  return car;
}

function answerRecommendation(question: string, snap: FactualRaceSnapshot): string | null {
  // Only Ask ARIS passes lastRecommendation (including null). Copilot omits it
  // so "pit now" still reaches the tool-calling API.
  if (snap.lastRecommendation === undefined) return null;
  const rec = snap.lastRecommendation;
  const wantsPit = PIT_NOW_RE.test(question);
  const wantsThink = ARIS_THINK_RE.test(question);
  const wantsWhy = WHY_STRATEGY_RE.test(question);
  if (!wantsPit && !wantsThink && !wantsWhy) return null;
  if (!rec) return NO_REC;

  if (wantsWhy) {
    const reasoning = (rec.evidence || "").trim();
    const action = rec.label;
    if (reasoning && reasoning.toLowerCase() !== action.toLowerCase()) {
      return appendGhost(`ARIS recommended ${action} because: ${reasoning}.`, snap);
    }
    const focus = focusCar(snap);
    const tyreBit =
      focus != null
        ? ` Tyre life was ${focus.tyre_life} laps on ${focus.compound}.`
        : "";
    return appendGhost(
      `ARIS ranked ${action} best at ${fmtDelta(rec.delta_vs_stay_out_s)}s vs stay-out on lap ${rec.lap}.${tyreBit}`,
      snap,
    );
  }

  return appendGhost(
    `ARIS ranks ${rec.label} as best: ${fmtDelta(rec.delta_vs_stay_out_s)}s vs stay-out. Confidence: ${confidencePct(rec)}.`,
    snap,
  );
}

function inPits(car: CarState): boolean {
  return Boolean(car.is_pitted || car.ghost_in_pits);
}

/** Deterministic answer from the live timing store. Null = not a live factual query. */
export function answerFactualLive(question: string, snap: FactualRaceSnapshot): string | null {
  const recAnswer = answerRecommendation(question, snap);
  if (recAnswer) return recAnswer;

  if (classifyIntent(question) !== "factual_live") return null;
  const q = question.toLowerCase();
  const field = classifiedCars(snap.cars);
  const leader = field.find((c) => c.position === 1) ?? field[0] ?? null;
  const named = resolveMentionedDriver(question, snap);
  const focus = named.car || focusCar(snap);

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
  if (
    /\bwho(?:'s| is)(?: in)? (?:the )?lead/.test(q) ||
    /\bwho(?:'s| is) leading\b/.test(q) ||
    /\bwho leads\b/.test(q)
  ) {
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
    const vsCodes = driversInText(question).filter((c) => c !== (focus?.driver_code ?? snap.focusDriver?.toUpperCase()));
    const vs = vsCodes[0];
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
  if (
    !/two compound/.test(q) &&
    (/\b(tyre|tire)s?\b/.test(q) || /\b(compound|rubber)\b/.test(q))
  ) {
    if (named.missingNamed) return null;
    const car = named.car || focusCar(snap);
    if (!car) return null;
    if (inPits(car)) return `${car.driver_code} is currently in the pit lane.`;
    return `${car.driver_code} is on ${car.compound}, tyre life ${car.tyre_life} laps.`;
  }
  if (
    /\b(current lap|laps remaining|laps left|how many laps|what lap is it)\b/.test(q) &&
    !/\b(why|recommend|pit|strategy|suggest)\b/.test(q)
  ) {
    const left = Math.max(0, (snap.totalLaps || 0) - (snap.currentLap || 0));
    return snap.totalLaps
      ? `Lap ${snap.currentLap} of ${snap.totalLaps}. ${left} laps remaining.`
      : `Lap ${snap.currentLap}.`;
  }
  if (/\bposition\b/.test(q)) {
    if (named.missingNamed) return null;
    const car = named.car || focus;
    if (!car) return null;
    return `${car.driver_code} is P${car.position}, ${fmtGap(car.gap_to_leader_s)} to the leader.`;
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
