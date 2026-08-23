import {
  MOCK_DRIVERS_2025,
  mockRoundsForYear,
  zandvoortOvalCoords,
} from "@/lib/mockData";
import type {
  ARISRecommendation,
  CircuitCoords,
  DriverListing,
  NextRaceInfo,
  RaceHistoryRow,
  RoundCard,
  SessionMeta,
  StatusResponse,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Last-known-good status, matching docs/model-status.md (T4 CQL, 2026-08-23).
// Shown whenever /api/status is unreachable so the home page never looks broken.
export const LAST_KNOWN_STATUS: StatusResponse = {
  version: "v0.3",
  match_rate: 0.345,
  match_rate_fraction: "30/87 dry",
  last_gate: "T4-final",
  timestamp: "2026-08-23T00:00:00Z",
};

async function tryFetch<T>(path: string, init?: RequestInit, timeoutMs = 1500): Promise<T | null> {
  try {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
    clearTimeout(id);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getStatus(): Promise<StatusResponse> {
  const live = await tryFetch<StatusResponse>("/api/status");
  return live ?? LAST_KNOWN_STATUS;
}

export async function getCalendar(year: number): Promise<RoundCard[]> {
  const live = await tryFetch<RoundCard[]>(`/api/calendar?year=${year}`);
  return live ?? mockRoundsForYear(year);
}

export async function getSession(
  year: number,
  round: number,
  type: string,
): Promise<SessionMeta> {
  const live = await tryFetch<SessionMeta>(`/api/session?year=${year}&round=${round}&type=${type}`);
  if (live) return live;
  const rounds = mockRoundsForYear(year);
  const r = rounds.find((x) => x.round === round) ?? rounds[14];
  return {
    year,
    round,
    sessionType: type as SessionMeta["sessionType"],
    circuitName: r.circuitName,
    countryFlag: r.countryFlag,
    totalLaps: 72,
    date: r.date,
    driverCode: "VER",
  };
}

export async function getCircuitCoords(year: number, round: number): Promise<CircuitCoords> {
  const live = await tryFetch<CircuitCoords>(`/api/circuit-coords?year=${year}&round=${round}`);
  return live ?? zandvoortOvalCoords();
}

export async function getDrivers(year: number): Promise<DriverListing[]> {
  const live = await tryFetch<DriverListing[]>(`/api/drivers?year=${year}`);
  return live ?? MOCK_DRIVERS_2025;
}

export async function getRaceHistory(circuit: string): Promise<RaceHistoryRow[]> {
  const live = await tryFetch<RaceHistoryRow[]>(`/api/race-history?circuit=${encodeURIComponent(circuit)}`);
  if (live) return live;
  return [
    { year: 2025, winner: "Max Verstappen", pole: "Lando Norris", fastestLapDriver: "Oscar Piastri", fastestLapTime: "1:11.083", raceRecord: "1:08.885 (2021)" },
    { year: 2024, winner: "Lando Norris", pole: "Max Verstappen", fastestLapDriver: "Max Verstappen", fastestLapTime: "1:13.202", raceRecord: "1:08.885 (2021)" },
    { year: 2023, winner: "Max Verstappen", pole: "Max Verstappen", fastestLapDriver: "Max Verstappen", fastestLapTime: "1:11.678", raceRecord: "1:08.885 (2021)" },
    { year: 2022, winner: "Max Verstappen", pole: "Max Verstappen", fastestLapDriver: "Lewis Hamilton", fastestLapTime: "1:11.097", raceRecord: "1:08.885 (2021)" },
    { year: 2021, winner: "Max Verstappen", pole: "Max Verstappen", fastestLapDriver: "Max Verstappen", fastestLapTime: "1:08.885", raceRecord: "1:08.885 (2021)" },
  ];
}

export async function getNextRace(): Promise<NextRaceInfo> {
  const live = await tryFetch<NextRaceInfo>("/api/next-race");
  if (live) return live;
  const target = new Date();
  target.setDate(target.getDate() + 3);
  target.setHours(target.getHours() + 14);
  return {
    raceName: "Dutch Grand Prix",
    circuitName: "Circuit Zandvoort",
    countryFlag: "🇳🇱",
    date: target.toISOString(),
    countdownTargetIso: target.toISOString(),
    sessions: [
      { name: "FP1", localTime: "Fri 12:30" },
      { name: "FP2", localTime: "Fri 16:00" },
      { name: "FP3", localTime: "Sat 11:30" },
      { name: "Qualifying", localTime: "Sat 15:00" },
      { name: "Race", localTime: "Sun 15:00" },
    ],
    circuitLengthKm: 4.259,
    lapRecord: { driver: "Lewis Hamilton", time: "1:08.885", year: 2021 },
    numLaps: 72,
    strategyPatterns: [
      { label: "1-Stop: Medium → Hard (pit lap ~28)", note: "Used by 60% of race winners" },
      { label: "2-Stop: Soft → Medium → Hard", note: "Used when degradation is high" },
      { label: "Alternative: Soft → Hard (long first stint)", note: "Aggressive undercut position" },
    ],
    raceHistory: await getRaceHistory("Zandvoort"),
    priorSessionReplay: {
      sessionName: "Q3 — Dutch GP Qualifying",
      dateLabel: "Yesterday",
      circuitName: "Zandvoort",
      poleDriver: "Norris",
      poleTime: "1:09.673",
      year: 2026,
      round: 15,
    },
  };
}

export async function askARIS(question: string, raceState?: unknown): Promise<{ answer: string }> {
  const live = await tryFetch<{ answer: string }>("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, race_state: raceState }),
  });
  if (live) return live;
  return { answer: mockAskAnswer(question) };
}

function mockAskAnswer(question: string): string {
  const q = question.toLowerCase();
  if (q.includes("gap") && q.includes("lando")) {
    return "Gap to NOR (car ahead): +1.8s and closing at ~0.1s/lap over the last 3 laps. Inside the 22s undercut window.";
  }
  if (q.includes("extend")) {
    return "Extending is worth about −0.4s vs the base plan at current tyre life, but the model discounts confidence beyond lap 34 on this compound (extrapolation_weight 0.7). Marginal call.";
  }
  if (q.includes("undercut")) {
    return "Undercut window open: gap ahead 1.8s, cliff estimate for the car ahead is lap 31 ± 2. Dynamic undercut bonus currently −0.5s.";
  }
  return "Based on the current race state: physics-default scoring has HARD at lap 33 ranked #1, delta −3.4s vs stay-out, confidence std 1.1s. Ask a more specific question (gap, undercut, tyre) for detail.";
}

export async function sendARISAction(payload: {
  action: "approve" | "deny" | "alter";
  lap: number;
  tyre?: string;
  note?: string;
}): Promise<{ result: string }> {
  const live = await tryFetch<{ result: string }>("/api/aris/action", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return live ?? { result: "ok (mock)" };
}

export function mockRecommendation(lap: number): ARISRecommendation {
  return {
    id: `rec-${lap}`,
    lap,
    rank: 1,
    label: "Box this lap → HARD",
    action: { kind: "pit_lap", pit_lap: lap, pit_compound: "HARD" },
    delta_vs_stay_out_s: -3.4,
    mean_race_time_s: 5820.4,
    confidence_std_s: 1.1,
    p10_delta_s: -5.1,
    p90_delta_s: -1.7,
    evidence: "G1.5 tyre slopes (HARD 0.03 s/lap) + SC pit cost + dynamic undercut bonus (−0.5s, gap ahead 1.8s)",
    narration_context: { gap_ahead_s: 1.8, cliff_lap_estimate: 31 },
    tactical: "Undercut window open on car ahead",
    extrapolation_beyond_laps: 0,
    extrapolation_weight: 1,
    wet_heuristic: false,
    cql_q_delta: 0,
    rank_score: 0.82,
  };
}
