// Shared TypeScript types. Field names mirror the Python backend shapes in
// src/aris/state.py (RaceState) and src/aris/recommend.py (Recommendation)
// so the wire format needs no translation layer.

export type Compound = "SOFT" | "MEDIUM" | "HARD" | "INTERMEDIATE" | "WET";

export type RacePhase = "GREEN" | "VSC" | "SC" | "RED" | "STANDING_START";

export type ActionKind = "stay_out" | "pit_now" | "pit_lap" | "lift";

export interface StrategyAction {
  kind: ActionKind;
  pit_lap?: number | null;
  pit_compound?: Compound | null;
  pit_laps?: number[] | null;
  pit_compounds?: Compound[] | null;
  corner_index?: number | null;
}

export interface ARISRecommendation {
  rank: number;
  label: string;
  action: StrategyAction;
  delta_vs_stay_out_s: number;
  mean_race_time_s: number;
  confidence_std_s: number;
  p10_delta_s: number;
  p90_delta_s: number;
  evidence: string;
  narration_context: Record<string, unknown>;
  tactical?: string | null;
  extrapolation_beyond_laps: number;
  extrapolation_weight: number;
  wet_heuristic: boolean;
  cql_q_delta: number;
  rank_score: number;
  // UI-only bookkeeping (not from backend)
  id: string;
  lap: number;
}

export interface CarState {
  driver_code: string;
  driver_number: number;
  full_name: string;
  team: string;
  team_colour: string;
  position: number | null;
  lap_number: number;
  compound: Compound;
  tyre_life: number;
  gap_to_leader_s: number | null;
  gap_ahead_s: number | null;
  gap_ahead_history: number[];
  last_lap_s: number | null;
  pit_stops: number;
  is_pitted: boolean;
  is_dnf: boolean;
  x: number;
  y: number;
  speed_kph: number;
  heading_rad: number;
  laps_remaining: number;
  total_laps: number;
  is_aris_driver?: boolean;
}

export interface CommsEntry {
  id: string;
  lap: number;
  source: "ARIS" | "USER" | "ARIS_ANALYSIS" | "FIELD";
  text: string;
  timestamp: number;
  wetHeuristic?: boolean;
  recommendationId?: string;
}

export interface SessionMeta {
  year: number;
  round: number;
  sessionType: "R" | "S" | "Q" | "FP1" | "FP2" | "FP3" | "SS";
  circuitName: string;
  countryFlag: string;
  totalLaps: number;
  date: string;
  driverCode: string;
}

export interface DriverListing {
  driver_number: number;
  driver_code: string;
  full_name: string;
  team: string;
  team_colour: string;
}

export interface RoundCard {
  round: number;
  circuitName: string;
  countryFlag: string;
  date: string;
  sessionType: "R" | "S" | "Q" | "FP1" | "FP2" | "FP3" | "SS";
  isSprint: boolean;
  arisEligible: boolean;
}

export interface CircuitCoords {
  x: number[];
  y: number[];
}

export interface StatusResponse {
  version: string;
  match_rate: number;
  match_rate_fraction: string;
  last_gate: string;
  timestamp: string;
}

export interface RaceHistoryRow {
  year: number;
  winner: string;
  pole: string;
  fastestLapDriver: string;
  fastestLapTime: string;
  raceRecord: string;
}

export interface RecentRaceCard {
  year: number;
  round: number;
  circuitName: string;
  countryFlag: string;
  raceName: string;
  date: string;
  winner: string;
  winnerCode: string;
  sessionType: "R" | "S";
}

export interface NextRaceInfo {
  raceName: string;
  circuitName: string;
  countryFlag: string;
  date: string;
  countdownTargetIso: string;
  sessions: { name: string; localTime: string }[];
  circuitLengthKm: number;
  lapRecord: { driver: string; time: string; year: number };
  numLaps: number;
  strategyPatterns: { label: string; note: string }[];
  raceHistory: RaceHistoryRow[];
  priorSessionReplay?: {
    sessionName: string;
    dateLabel: string;
    circuitName: string;
    poleDriver: string;
    poleTime: string;
    year: number;
    round: number;
  } | null;
}
