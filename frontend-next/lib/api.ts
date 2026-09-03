import { isFullCircuitOutline, readCircuitCache, writeCircuitCache } from "@/lib/circuitCache";
import { TTL_MS, dedupe, withCache } from "@/lib/httpCache";
import {
  MOCK_DRIVERS_2025,
  mockRecentRaces,
  mockRoundsForYear,
} from "@/lib/mockData";
import { countryFlag } from "@/lib/flags";
import { overlayOfficial2026Date } from "@/lib/replayFilter";
import type {
  ARISRecommendation,
  CircuitCoords,
  CopilotChatResponse,
  DegradationCurveResponse,
  DriverListing,
  GhostVsRealResponse,
  LiveHub,
  NextRaceInfo,
  QuickAnalysisResponse,
  RaceDebriefResponse,
  ConstructorStandingsResponse,
  DriverStandingsResponse,
  RaceHistoryRow,
  RecentRaceCard,
  RecommendApiResponse,
  RoundCard,
  RoundStatus,
  SessionMeta,
  SessionType,
  StatusResponse,
} from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

// Last-known-good status, matching docs/model-status.md (T4 CQL, 2026-08-23).
// Shown whenever /api/status is unreachable so the home page never looks broken.
export const LAST_KNOWN_STATUS: StatusResponse = {
  version: "v0.3",
  match_rate: 0.345,
  match_rate_fraction: "30/87 dry",
  last_gate: "T4-final",
  timestamp: "2026-08-23T00:00:00Z",
};

/** Dev-only Copilot tab unless NEXT_PUBLIC_ARIS_COPILOT=1 in production. */
export function copilotFeatureEnabled(): boolean {
  if (process.env.NEXT_PUBLIC_ARIS_COPILOT === "0") return false;
  if (process.env.NEXT_PUBLIC_ARIS_COPILOT === "1") return true;
  return process.env.NODE_ENV !== "production";
}

/** Explain tab on unless production; force with NEXT_PUBLIC_ARIS_EXPLAIN=1. */
export function explainFeatureEnabled(): boolean {
  if (process.env.NEXT_PUBLIC_ARIS_EXPLAIN === "0") return false;
  if (process.env.NEXT_PUBLIC_ARIS_EXPLAIN === "1") return true;
  return process.env.NODE_ENV !== "production";
}

/** Ghost dot on the track map — hidden by default (backend GPS-projection
 * bug can misplace the dot; see docs/GHOST_CAR_REMEDIATION_PLAN.md).
 * Force on with NEXT_PUBLIC_ARIS_GHOST_MAP=1 once the backend fix lands. */
export function ghostMapFeatureEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ARIS_GHOST_MAP === "1";
}

export function explainSessionId(session: SessionMeta | null | undefined): string {
  if (!session) return "2025-15-R";
  const stype = session.sessionType === "S" ? "S" : "R";
  return `${session.year}-${session.round}-${stype}`;
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; status: number; message: string };

async function fetchApi<T>(path: string, timeoutMs = 20000): Promise<ApiResult<T>> {
  try {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(`${API_BASE}${path}`, { signal: controller.signal });
    clearTimeout(id);
    if (!res.ok) {
      let message = res.statusText || `HTTP ${res.status}`;
      try {
        const body = (await res.json()) as { detail?: unknown };
        if (typeof body.detail === "string") message = body.detail;
        else if (Array.isArray(body.detail)) {
          message = body.detail
            .map((row) => (typeof row === "object" && row && "msg" in row ? String((row as { msg: string }).msg) : String(row)))
            .join("; ");
        }
      } catch {
        /* ignore parse errors */
      }
      return { ok: false, status: res.status, message };
    }
    return { ok: true, data: (await res.json()) as T };
  } catch (err) {
    const message = err instanceof Error ? err.message : "Network error";
    return { ok: false, status: 0, message };
  }
}

export async function getDriverStandings(year: number): Promise<ApiResult<DriverStandingsResponse>> {
  return fetchApi<DriverStandingsResponse>(`/api/standings/drivers/${year}`, 60000);
}

export async function getConstructorStandings(year: number): Promise<ApiResult<ConstructorStandingsResponse>> {
  return fetchApi<ConstructorStandingsResponse>(`/api/standings/constructors/${year}`, 60000);
}

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

export async function getCalendar(year: number, opts?: { replay?: boolean }): Promise<RoundCard[]> {
  const suffix = opts?.replay ? "?replay=1" : "";
  const mapped = await withCache(
    `GET:/api/calendar/${year}${suffix}:v2026-23b`,
    TTL_MS.calendar,
    async () => {
      const live = await tryFetch<{ rounds?: BackendRound[] }>(`/api/calendar/${year}${suffix}`, undefined, 20000);
      if (!live?.rounds?.length) return null;
      return live.rounds.map((r) => {
        const card = mapBackendRound(r);
        return {
          ...card,
          date: overlayOfficial2026Date(year, card.circuitName, card.date),
        };
      });
    },
    true,
  );
  return (mapped ?? mockRoundsForYear(year)).map((r) => ({
    ...r,
    date: overlayOfficial2026Date(year, r.circuitName, r.date),
  }));
}

interface BackendRound {
  round_number: number;
  name: string;
  circuit_name: string;
  circuit_key: string;
  country: string;
  date_race: string | null;
  status: RoundStatus;
  is_sprint_weekend: boolean;
  cancelled_reason?: string | null;
  total_laps?: number | null;
}

function mapBackendRound(r: BackendRound): RoundCard {
  return {
    round: r.round_number,
    circuitName: r.circuit_name || r.name,
    countryFlag: countryFlag(r.country, r.circuit_key),
    date: r.date_race ?? new Date().toISOString(),
    sessionType: "R",
    isSprint: Boolean(r.is_sprint_weekend),
    arisEligible: r.status !== "CANCELLED" && r.status !== "UPCOMING",
    status: r.status,
    circuitKey: r.circuit_key,
    totalLaps: r.total_laps ?? undefined,
    cancelledReason: r.cancelled_reason,
  };
}

export async function getRoundSessions(year: number, round: number) {
  return withCache(
    `GET:/api/calendar/${year}/${round}/sessions?replay=1`,
    TTL_MS.roundSessions,
    () =>
      tryFetch<{
        sessions: { session_type: string; session_name: string; status: string; datetime_utc: string | null }[];
        is_sprint_weekend: boolean;
      }>(`/api/calendar/${year}/${round}/sessions?replay=1`, undefined, 15000),
    true,
  );
}

export async function getSession(
  year: number,
  round: number,
  type: string,
): Promise<SessionMeta> {
  const rounds = await getCalendar(year);
  const r = rounds.find((x) => x.round === round) ?? rounds[0];
  const summary = await withCache(
    `GET:/api/session/${year}/${round}/${type}/summary`,
    TTL_MS.sessionCompleted,
    () =>
      tryFetch<{ weather?: { rainfall?: boolean | null }; total_laps?: number | null }>(
        `/api/session/${year}/${round}/${type}/summary`,
        undefined,
        20000,
      ),
    true,
  );
  const sprint = type === "S" || type === "SQ";
  const yaml = r?.totalLaps;
  const fromSummary = summary?.total_laps;
  const total = sprint ? fromSummary || 24 : yaml || fromSummary || 72;
  return {
    year,
    round,
    sessionType: type as SessionType,
    circuitName: r?.circuitName ?? "Unknown",
    countryFlag: r?.countryFlag ?? "🏁",
    totalLaps: total && total > 0 ? total : sprint ? 24 : 72,
    date: r?.date ?? new Date().toISOString(),
    driverCode: "VER",
  };
}

type CircuitMapPayload = {
  x?: number[];
  y?: number[];
  markers?: { kind: string; x: number; y: number; label: string }[];
  pit_lane_x?: number[];
  pit_lane_y?: number[];
  sector_paths?: { kind: string; label: string; x: number[]; y: number[] }[];
  available?: boolean;
};

function coordsFromMapPayload(live: CircuitMapPayload | null): CircuitCoords | null {
  if (!live?.x?.length || !live?.y?.length) return null;
  return {
    x: live.x,
    y: live.y,
    markers: live.markers,
    pitLaneX: live.pit_lane_x,
    pitLaneY: live.pit_lane_y,
    sectorPaths: live.sector_paths,
    available: live.available !== false,
  };
}

export type ReplayOutlinePayload = {
  circuit_path?: { x: number[]; y: number[] } | null;
  markers?: CircuitCoords["markers"];
  pit_lane_x?: number[];
  pit_lane_y?: number[];
};

export function circuitCoordsFromReplayOutline(src: ReplayOutlinePayload | null | undefined): CircuitCoords | null {
  return coordsFromMapPayload(
    src?.circuit_path
      ? {
          x: src.circuit_path.x,
          y: src.circuit_path.y,
          markers: src.markers,
          pit_lane_x: src.pit_lane_x,
          pit_lane_y: src.pit_lane_y,
        }
      : null,
  );
}

export async function getCircuitCoords(year: number, round: number): Promise<CircuitCoords> {
  const cached = readCircuitCache(year, round);
  if (cached && isFullCircuitOutline(cached)) return cached;

  return (
    (await dedupe(`GET:/api/circuit/${year}/${round}/map`, async () => {
      const years = year >= 2026 ? [year, year - 1, year - 2] : [year, year - 1];
      let preview: CircuitCoords | null = null;
      for (const y of years) {
        if (y < 2018) continue;
        const full = coordsFromMapPayload(
          await tryFetch<CircuitMapPayload>(`/api/circuit/${y}/${round}/map`, undefined, 45000),
        );
        if (full && isFullCircuitOutline(full)) {
          writeCircuitCache(year, round, full);
          return full;
        }
        if (full?.x?.length && !preview) preview = full;
      }
      return preview;
    })) ?? { x: [], y: [], available: false }
  );
}

export async function getDrivers(year: number): Promise<DriverListing[]> {
  const mapped = await withCache(
    `GET:/api/drivers/${year}`,
    TTL_MS.drivers,
    async () => {
      const live = await tryFetch<{
        drivers?: {
          driver_code: string;
          full_name: string;
          team_name: string;
          team_colour?: string | null;
          driver_number?: number | null;
          headshot_url?: string | null;
        }[];
      }>(`/api/drivers/${year}`, undefined, 8000);
      if (!live?.drivers?.length) return null;
      return live.drivers.map((d) => ({
        driver_code: d.driver_code,
        full_name: d.full_name,
        team: d.team_name,
        team_colour: d.team_colour ?? "#888888",
        driver_number: d.driver_number ?? 0,
        headshot_url: d.headshot_url ?? null,
      }));
    },
    true,
  );
  return mapped ?? MOCK_DRIVERS_2025;
}

export async function getLiveHub(): Promise<LiveHub | null> {
  const hub = await tryFetch<LiveHub>("/api/live/hub", undefined, 8000);
  if (hub) {
    const date = hub.next.date_race
      ? overlayOfficial2026Date(hub.next.year, hub.next.circuit_name, hub.next.date_race)
      : hub.next.date_race;
    return { ...hub, next: { ...hub.next, date_race: date } };
  }
  const nxt = await tryFetch<LiveHub["next"]>("/api/live/next", undefined, 6000);
  if (!nxt) return null;
  return {
    mode: nxt.is_this_weekend ? "waiting_for_session" : "next_weekend",
    waiting_reason: nxt.is_this_weekend ? "Waiting for session data." : null,
    countdown_seconds: nxt.countdown_seconds,
    countdown_target: nxt.next_session_datetime,
    live: {
      is_live: false,
      year: nxt.year,
      round_number: nxt.round_number,
      session_type: null,
      session_name: nxt.next_session_name,
      gp_name: nxt.name,
      current_lap: null,
      total_laps: null,
      session_flag: null,
      session_ended: false,
    },
    next: nxt,
    weekend_sessions: [],
    circuit: {
      circuit_key: nxt.circuit_key,
      circuit_name: nxt.circuit_name,
      country: nxt.country,
      country_flag: countryFlag(nxt.country, nxt.circuit_key),
      length_km: null,
      total_laps: null,
      turns: null,
      pit_loss_seconds: null,
      tyre_stress_rating: null,
      strategy_patterns: [],
      race_history: [],
      notes: nxt.notes ?? [],
    },
    as_of: new Date().toISOString(),
  };
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

export async function getRecentRaces(limit = 3): Promise<RecentRaceCard[]> {
  const live = await tryFetch<RecentRaceCard[]>(`/api/recent-races?limit=${limit}`);
  return live ?? mockRecentRaces(limit);
}

export async function getNextRace(): Promise<NextRaceInfo> {
  const live = await tryFetch<NextRaceInfo>("/api/next-race", undefined, 8000);
  if (live && "raceName" in live) return live;
  const hub = await getLiveHub();
  if (hub) return hubToNextRaceInfo(hub);
  const again = await tryFetch<NextRaceInfo>("/api/next-race", undefined, 8000);
  if (again && "raceName" in again) return again;
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
      round: 12,
    },
  };
}

export function hubToNextRaceInfo(hub: LiveHub): NextRaceInfo {
  const prior = [...hub.weekend_sessions].reverse().find((s) => s.replayable);
  return {
    raceName: hub.next.name,
    circuitName: hub.circuit.circuit_name || hub.next.circuit_name,
    countryFlag: hub.circuit.country_flag || countryFlag(hub.next.country, hub.next.circuit_key),
    date: hub.next.date_race ?? hub.countdown_target ?? new Date().toISOString(),
    countdownTargetIso: hub.countdown_target ?? hub.next.next_session_datetime ?? new Date().toISOString(),
    sessions: hub.weekend_sessions.map((s) => ({
      name: s.session_type,
      localTime: s.datetime_utc ? new Date(s.datetime_utc).toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" }) : s.status,
    })),
    circuitLengthKm: hub.circuit.length_km ?? 0,
    lapRecord: { driver: "—", time: "—", year: 0 },
    numLaps: hub.circuit.total_laps ?? 0,
    strategyPatterns: hub.circuit.strategy_patterns,
    raceHistory: hub.circuit.race_history.map((r) => ({
      year: r.year,
      winner: r.winner ?? "—",
      pole: r.pole ?? "—",
      fastestLapDriver: r.fastest_lap ?? "—",
      fastestLapTime: "—",
      raceRecord: "—",
    })),
    priorSessionReplay: prior
      ? {
          sessionName: prior.session_name,
          dateLabel: prior.status,
          circuitName: hub.next.circuit_name,
          poleDriver: "—",
          poleTime: "",
          year: hub.next.year,
          round: hub.next.round_number,
        }
      : null,
  };
}

export interface PrewarmResponse {
  year: number;
  round_number: number;
  session_type: string;
  session_key?: number | null;
  status: "ready" | "warming";
  tasks?: string[];
}

/** Kick ingest + replay pack + circuit map so the console does not cold-start. */
export async function prewarmSession(payload: {
  year: number;
  round_number: number;
  session_type: string;
  driver_code?: string;
}): Promise<PrewarmResponse | null> {
  const live = await tryFetch<PrewarmResponse>(
    "/api/prewarm",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    25000,
  );
  if (live) return live;
  // Fallback: existing warm endpoints if /api/prewarm is unavailable.
  await Promise.all([
    tryFetch(`/api/session/${payload.year}/${payload.round_number}/${payload.session_type}/ingest`, {
      method: "POST",
    }, 15000),
    tryFetch(
      `/api/live/session-key?year=${payload.year}&round_number=${payload.round_number}&session_type=${payload.session_type}`,
      undefined,
      15000,
    ),
    tryFetch(`/api/circuit/${payload.year}/${payload.round_number}/preview`, undefined, 8000),
  ]);
  return {
    year: payload.year,
    round_number: payload.round_number,
    session_type: payload.session_type,
    status: "warming",
  };
}

export type ReplayPackStage = "empty" | "metadata" | "minimal" | "full";

export type ReplayPackFlags = {
  laps_ready?: boolean;
  map_ready?: boolean;
  gps_ready?: boolean;
  weather_ready?: boolean;
  race_control_ready?: boolean;
  synthetic_gps?: boolean;
};

export type ReplayPackStatus = {
  session_key?: number;
  session_id?: number;
  status?: "loading" | "ready" | "error";
  ready?: boolean;
  stage?: ReplayPackStage;
  progress?: number;
  flags?: ReplayPackFlags;
  laps_ready?: boolean;
  map_ready?: boolean;
  gps_ready?: boolean;
  weather_ready?: boolean;
  error?: string | null;
  elapsed_s?: number | null;
  source?: string;
  date_start?: string | null;
  date_end?: string | null;
  session_type?: string;
  green_flag_s?: number | null;
  pos_chunks?: { lo: number; hi: number }[];
  pos_chunk_loaded?: { lo: number; hi: number } | null;
  circuit_path?: { x: number[]; y: number[] } | null;
  pit_lane_x?: number[];
  pit_lane_y?: number[];
  markers?: CircuitCoords["markers"];
  drs_segments?: number[][];
};

export type ReplayInitResponse = {
  session_key: number;
  year: number;
  round_number: number;
  session_type: string;
  stage: ReplayPackStage;
  session_status: string;
  source: string;
  circuit: string;
  total_laps: number;
  drivers: string[];
  date_start?: string | null;
  date_end?: string | null;
  flags?: ReplayPackFlags;
  progress?: number;
  circuit_path?: { x: number[]; y: number[] } | null;
  pit_lane_x?: number[];
  pit_lane_y?: number[];
  markers?: CircuitCoords["markers"];
  drs_segments?: number[][];
};

export async function initReplay(payload: {
  year: number;
  round_number: number;
  session_type: string;
}): Promise<ReplayInitResponse | null> {
  return tryFetch<ReplayInitResponse>(
    "/api/replay/init",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    15000,
  );
}

export async function getReplayPackStatus(params: {
  session_key?: number;
  session_id?: number;
  year?: number;
  round_number?: number;
  session_type?: string;
  refresh?: boolean;
  outline?: boolean;
}): Promise<ReplayPackStatus | null> {
  const qs = new URLSearchParams();
  const key = params.session_key ?? params.session_id;
  if (key != null) qs.set("session_key", String(key));
  if (params.session_id != null) qs.set("session_id", String(params.session_id));
  if (params.year != null) qs.set("year", String(params.year));
  if (params.round_number != null) qs.set("round_number", String(params.round_number));
  if (params.session_type) qs.set("session_type", params.session_type);
  if (params.refresh) qs.set("refresh", "1");
  if (params.outline) qs.set("outline", "1");
  return tryFetch<ReplayPackStatus>(`/api/replay/pack-status?${qs}`, undefined, 8000);
}

export async function prefetchReplayPosChunk(params: {
  session_key: number;
  lap: number;
  year?: number;
  round_number?: number;
  session_type?: string;
}): Promise<{ ok?: boolean; pos_chunk_loaded?: { lo: number; hi: number } } | null> {
  const qs = new URLSearchParams({
    session_key: String(params.session_key),
    lap: String(params.lap),
  });
  if (params.year != null) qs.set("year", String(params.year));
  if (params.round_number != null) qs.set("round_number", String(params.round_number));
  if (params.session_type) qs.set("session_type", params.session_type);
  return tryFetch(`/api/replay/pos-chunk?${qs}`, undefined, 8000);
}

export async function getQuickAnalysis(
  year: number,
  round: number,
  driverCode: string,
): Promise<QuickAnalysisResponse | null> {
  const live = await tryFetch<QuickAnalysisResponse>(
    `/api/aris/quick-analysis?year=${year}&round_number=${round}&driver_code=${encodeURIComponent(driverCode)}`,
    undefined,
    30000,
  );
  if (live?.plans?.length) return live;
  const plans = await tryFetch<QuickAnalysisResponse>(
    `/api/aris/plans?year=${year}&round_number=${round}&driver_code=${encodeURIComponent(driverCode)}`,
    undefined,
    30000,
  );
  if (plans?.plans?.length) {
    const ranked = plans.plans.slice(0, 3);
    if (ranked[0] && !ranked.some((p) => p.recommended)) ranked[0] = { ...ranked[0], recommended: true };
    return { ...plans, plans: ranked };
  }
  return {
    year,
    round_number: round,
    driver_code: driverCode,
    plans: [
      { id: "rec", name: "1-stop Medium → Hard", pit_laps: [28], pit_compounds: ["H"], start_compound: "M", description: "Default dry winner pattern at this circuit.", recommended: true, risk: "Low" },
      { id: "alt", name: "2-stop Soft → Medium → Hard", pit_laps: [18, 42], pit_compounds: ["M", "H"], start_compound: "S", description: "Used when degradation is high.", recommended: false, risk: "Higher" },
      { id: "und", name: "Undercut Medium → Hard", pit_laps: [22], pit_compounds: ["H"], start_compound: "M", description: "Earlier stop to jump the car ahead.", recommended: false, risk: "Medium" },
    ],
  };
}

export async function askARIS(
  question: string,
  raceState?: unknown,
  meta?: { year?: number; round?: number; driver?: string; currentLap?: number },
): Promise<{ answer: string; offline: boolean }> {
  const live = await tryFetch<{ answer: string }>(
    "/api/ask",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        race_state: raceState,
        year: meta?.year,
        round_number: meta?.round,
        driver_code: meta?.driver,
        current_lap: meta?.currentLap,
      }),
    },
    8000,
  );
  if (live?.answer) return { answer: live.answer, offline: false };
  const viaChat = await tryFetch<{ answer: string }>(
    `/api/aris/chat?question=${encodeURIComponent(question)}${
      meta?.year != null ? `&year=${meta.year}` : ""
    }${meta?.round != null ? `&round_number=${meta.round}` : ""}${
      meta?.driver ? `&driver_code=${encodeURIComponent(meta.driver)}` : ""
    }${meta?.currentLap != null ? `&current_lap=${meta.currentLap}` : ""}`,
    undefined,
    8000,
  );
  if (viaChat?.answer) return { answer: viaChat.answer, offline: false };
  return { answer: mockAskAnswer(question), offline: true };
}

export async function getSessionResults(
  year: number,
  round: number,
  sessionType = "R",
): Promise<{ position: number | null; driver_code: string; status: string }[] | null> {
  const live = await tryFetch<{
    results: { position: number | null; driver_code: string; status: string }[];
  }>(`/api/session/${year}/${round}/${sessionType}/results`);
  return live?.results ?? null;
}

export async function getDegradationCurve(params: {
  session_id: string;
  driver: string;
  stint_id?: number | null;
  start_lap?: number | null;
  end_lap?: number | null;
}): Promise<DegradationCurveResponse> {
  const q = new URLSearchParams({ session_id: params.session_id, driver: params.driver });
  if (params.stint_id != null) q.set("stint_id", String(params.stint_id));
  if (params.start_lap != null) q.set("start_lap", String(params.start_lap));
  if (params.end_lap != null) q.set("end_lap", String(params.end_lap));
  const live = await tryFetch<DegradationCurveResponse>(`/api/explain/degradation?${q}`, undefined, 60000);
  return live ?? mockDegradationCurve(params.driver, params.stint_id ?? 1);
}

export async function getGhostVsReal(params: {
  session_id: string;
  driver: string;
}): Promise<GhostVsRealResponse> {
  const q = new URLSearchParams({ session_id: params.session_id, driver: params.driver });
  const live = await tryFetch<GhostVsRealResponse>(`/api/explain/ghost?${q}`, undefined, 60000);
  return live ?? mockGhostVsReal(params.driver);
}

export async function getRaceDebrief(params: {
  session_id: string;
  focus_driver?: string;
}): Promise<RaceDebriefResponse> {
  const q = new URLSearchParams({ session_id: params.session_id });
  if (params.focus_driver) q.set("focus_driver", params.focus_driver);
  const live = await tryFetch<RaceDebriefResponse>(`/api/explain/debrief?${q}`, undefined, 60000);
  return live ?? mockRaceDebrief(params.focus_driver ?? "VER");
}

export async function downloadDebriefExport(session_id: string, focus_driver: string): Promise<void> {
  try {
    const res = await fetch(
      `${API_BASE}/api/explain/debrief?session_id=${encodeURIComponent(session_id)}&focus_driver=${encodeURIComponent(focus_driver)}&format=parquet`,
    );
    if (!res.ok) return;
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    const disp = res.headers.get("Content-Disposition") ?? "";
    const match = /filename="?([^"]+)"?/.exec(disp);
    a.href = url;
    a.download = match?.[1] ?? "debrief.parquet";
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    /* ignore — export is optional */
  }
}

function mockDegradationCurve(driver: string, stintId: number): DegradationCurveResponse {
  const n = 18;
  const tyre_age = Array.from({ length: n }, (_, i) => i + 1);
  return {
    tyre_age,
    predicted_deg_s: tyre_age.map((a) => Number((0.05 * Math.max(0, a - 1) + (a === 1 ? 1.5 : 0)).toFixed(3))),
    actual_deg_s: tyre_age.map((a) => Number((0.055 * Math.max(0, a - 1) + (a === 1 ? 1.4 : 0) + Math.sin(a) * 0.04).toFixed(3))),
    lap_number: tyre_age,
    compound: "MEDIUM",
    circuit: "Netherlands",
    session_type: "R",
    session_id: "2025-15-R",
    driver,
    stint_id: stintId,
    start_lap: 1,
    end_lap: n,
    available_stints: [
      { stint_id: 1, compound: "MEDIUM", start_lap: 1, end_lap: 20 },
      { stint_id: 2, compound: "HARD", start_lap: 21, end_lap: 72 },
    ],
  };
}

function mockGhostVsReal(driver: string): GhostVsRealResponse {
  const laps = Array.from({ length: 32 }, (_, i) => i + 1);
  return {
    session_id: "2025-15-R",
    driver,
    circuit: "Netherlands",
    ghost: {
      laps,
      position: laps.map((l) => (l < 21 ? 1 : 1)),
      gap_to_leader: laps.map(() => 0),
      compound: laps.map((l) => (l < 33 ? "MEDIUM" : "HARD")),
      pit_laps: [33],
    },
    real: {
      laps,
      position: laps.map((l) => (l < 21 ? 1 : 2)),
      gap_to_leader: laps.map((l) => (l < 21 ? 0 : Number(((l - 20) * 0.12).toFixed(2)))),
      compound: laps.map((l) => (l <= 20 ? "MEDIUM" : "HARD")),
      pit_laps: [20],
    },
    delta: {
      laps,
      position_delta: laps.map((l) => (l < 21 ? 0 : -1)),
      gap_delta: laps.map((l) => (l < 21 ? 0 : Number((-(l - 20) * 0.12).toFixed(2)))),
    },
    aris_action: "Pit lap 33 for HARD",
    explanation: "Box lap 33 for HARD — remaining-race delta vs stay-out.",
  };
}

function mockRaceDebrief(driver: string): RaceDebriefResponse {
  return {
    timeline: {
      pit_stops: [{ lap: 20, driver, compound_in: "MEDIUM", compound_out: "HARD", stint_length: 20 }],
      sc_vsc_periods: [{ kind: "SC", start_lap: 8, end_lap: 10 }],
      rain_periods: [{ kind: "RAIN", start_lap: 12, end_lap: 16 }],
    },
    decisions: [
      {
        lap: 20,
        type: "pit",
        recommend_top3: [
          { rank: 1, label: "Pit lap 33 for HARD", delta_vs_stay_out_s: -3.4, p_best: 0.62 },
          { rank: 2, label: "Pit lap 30 for HARD", delta_vs_stay_out_s: -2.1, p_best: 0.28 },
          { rank: 3, label: "Stay out", delta_vs_stay_out_s: 0, p_best: 0.1 },
        ],
        chosen_action: "PIT_NOW_HARD",
        aris_action: "Pit lap 33 for HARD",
        explanation: "ARIS wanted HARD at lap 33; the team boxed lap 20 for HARD.",
      },
    ],
    metadata: {
      circuit: "Netherlands",
      season: 2025,
      round_number: 15,
      total_laps: 72,
      session_id: "2025-15-R",
      focus_driver: driver,
      session_type: "R",
    },
  };
}

export async function chatCopilot(payload: {
  message: string;
  session_id?: string;
  year?: number;
  round_number?: number;
  driver_code?: string;
  current_lap?: number;
}): Promise<CopilotChatResponse> {
  const live = await tryFetch<CopilotChatResponse>(
    "/api/copilot/chat",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    30000,
  );
  if (live) return { ...live, offline: false };
  // Backend unreachable — flag it so the UI never passes a canned answer off
  // as a real tool-calling response.
  return mockCopilotAnswer(payload.message);
}

function mockCopilotAnswer(message: string): CopilotChatResponse {
  const { answer } = { answer: mockAskAnswer(message) };
  const q = message.toLowerCase();
  const needs = /best strategy|pit now|recommend|should we|cover/.test(q);
  return {
    response: answer,
    tool_calls: [],
    retrieved_chunks: [],
    recommendations: needs
      ? [
          { rank: 1, label: "Pit lap 33 for HARD", delta_vs_stay_out_s: -3.4, p_best: 0.62 },
          { rank: 2, label: "Pit lap 30 for HARD", delta_vs_stay_out_s: -2.1, p_best: 0.28 },
          { rank: 3, label: "Stay out", delta_vs_stay_out_s: 0, p_best: 0.1 },
        ]
      : [],
    needs_approval: needs,
    offline: true,
  };
}

function mockAskAnswer(question: string): string {
  const q = question.toLowerCase();
  if (q.includes("gap") && (q.includes("ahead") || q.includes("leader") || q.includes("rival"))) {
    return "Gap to the driver ahead: +1.8s and closing at ~0.1s/lap over the last 3 laps. Inside the 22s undercut window.";
  }
  if (q.includes("extend")) {
    return "Extending is worth about −0.4s vs the base plan at current tyre life, but the model discounts confidence beyond lap 34 on this compound (extrapolation_weight 0.7). Marginal call.";
  }
  if (q.includes("undercut")) {
    return "Undercut window open: gap ahead 1.8s, cliff estimate for the car ahead is lap 31 ± 2. Dynamic undercut bonus currently −0.5s.";
  }
  return "Based on the current race state: physics-default scoring has HARD at lap 33 ranked #1, delta −3.4s vs stay-out, confidence std 1.1s. Ask a more specific question (gap, undercut, tyre) for detail.";
}

export async function postRecommend(payload: {
  year: number;
  round_number: number;
  session_type?: string;
  driver_code: string;
  current_lap: number;
  mode?: "live" | "replay" | "pre_race";
}, opts?: { force?: boolean }): Promise<RecommendApiResponse | null> {
  const force = Boolean(opts?.force);
  const key = force
    ? `POST:/api/aris/recommend:force:${payload.year}:${payload.round_number}:${payload.driver_code}:${payload.current_lap}:${Date.now()}`
    : `POST:/api/aris/recommend:${payload.year}:${payload.round_number}:${payload.driver_code}:${payload.current_lap}:${payload.mode ?? "replay"}`;
  return dedupe(key, () =>
    tryFetch<RecommendApiResponse>(
      "/api/aris/recommend",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          year: payload.year,
          round_number: payload.round_number,
          session_type: payload.session_type ?? "R",
          driver_code: payload.driver_code,
          current_lap: payload.current_lap,
          mode: payload.mode ?? "replay",
          force_refresh: force,
        }),
      },
      60000,
    ),
  );
}

export async function postGhostRecompute(opts: {
  year: number;
  round: number;
  driver: string;
  currentLap: number;
  pitLaps: number[];
  compounds: string[];
  label?: string;
  sessionKey?: number;
}): Promise<{ ticks: { lap: number; position: number; gap_to_leader_s: number; compound: string; tyre_life: number; stint: number; cumulative_delta_s: number; aris_action: string; aris_confidence: number }[] } | null> {
  return tryFetch(
    "/api/aris/ghost-recompute",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        year: opts.year,
        round: opts.round,
        driver: opts.driver,
        current_lap: opts.currentLap,
        pit_laps: opts.pitLaps,
        compounds: opts.compounds,
        label: opts.label || "",
        session_key: opts.sessionKey ?? null,
      }),
    },
    25000,
  );
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
