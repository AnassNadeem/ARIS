// Shared TypeScript types. Field names mirror the Python backend shapes in
// src/aris/state.py (RaceState) and src/aris/recommend.py (Recommendation)
// so the wire format needs no translation layer.

export type Compound = "SOFT" | "MEDIUM" | "HARD" | "INTERMEDIATE" | "WET";

export type RacePhase = "GREEN" | "VSC" | "SC" | "RED_FLAG" | "FORMATION_LAP" | "STANDING_START";

export interface PhaseHistoryEntry {
  lap: number;
  phase: RacePhase;
}

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

export type SectorColour = "purple" | "green" | "yellow" | "grey";

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
  best_lap_s?: number | null;
  pit_stops: number;
  is_pitted: boolean;
  is_dnf: boolean;
  status?: "RUNNING" | "DNF" | "DNS";
  fastest_lap?: boolean;
  sector1_s?: number | null;
  sector2_s?: number | null;
  sector3_s?: number | null;
  s1_colour?: SectorColour;
  s2_colour?: SectorColour;
  s3_colour?: SectorColour;
  laps_completed?: number | null;
  laps_down?: number | null;
  path_frac?: number;
  x: number;
  y: number;
  speed_kph: number;
  heading_rad: number;
  laps_remaining: number;
  total_laps: number;
  is_aris_driver?: boolean;
  // Ghost-specific fields (only present when driver_code starts with "A_")
  ghost_cumulative_delta?: number;
  divergence_lap?: number;
  aris_action?: string;
  real_action?: string;
}

export interface GhostDeltaPoint {
  lap: number;
  delta: number;
  ghost_pos: number;
  real_pos: number;
}

/** Full ghost state from the backend tick payload. */
export interface GhostTickData {
  driver_code: string;
  divergence_lap: number;
  aris_action: string;
  real_action: string;
  ghost_tyre: Compound;
  ghost_tyre_age: number;
  ghost_position: number;
  ghost_cumulative_delta: number;
  active: boolean;
  outcome: "ARIS_CORRECT" | "ARIS_INCORRECT" | "INCONCLUSIVE" | null;
  delta_history: GhostDeltaPoint[];
  ghost_compound?: Compound;
  typical_lap_s?: number;
  from_lap_one?: boolean;
  ghost_position_on_track?: number;
  plan_pit_laps?: number[];
  plan_pit_compounds?: Compound[];
  gap_to_leader_s?: number;
}

export interface RaceFieldMeta {
  year: number;
  round: number;
  session_type: string;
  circuit_name: string;
  total_laps: number;
  date_race: string;
  green_flag_s: number | null;
  session_key: number | null;
}

export interface RaceFieldDriver {
  code: string;
  name: string;
  team: string;
  colour: string;
  grid_position: number | null;
}

export interface RaceFieldLap {
  lap: number;
  driver: string;
  position: number | null;
  gap_to_leader_s: number | null;
  gap_ahead_s: number | null;
  compound: string | null;
  tyre_life: number | null;
  stint_number: number | null;
  pit_this_lap: boolean;
  is_dnf: boolean;
  is_dsq: boolean;
  track_status: string | null;
  lap_time_s: number | null;
}

export interface RaceFieldStint {
  driver: string;
  stint: number;
  compound: string | null;
  lap_start: number;
  lap_end: number;
}

export interface RaceFieldWeather {
  lap: number;
  rainfall: boolean;
  track_temp_c: number | null;
  air_temp_c: number | null;
}

export interface RaceFieldRaceControl {
  lap: number | null;
  message: string;
  flag: string | null;
  category: string | null;
}

export interface RaceFieldPosSample {
  lap_frac: number;
  path_frac: number;
}

export interface RaceField {
  meta: RaceFieldMeta;
  outline: { x: number[]; y: number[] };
  drivers: RaceFieldDriver[];
  laps: RaceFieldLap[];
  stints: RaceFieldStint[];
  weather: RaceFieldWeather[];
  race_control: RaceFieldRaceControl[];
  pos_samples: Record<string, RaceFieldPosSample[]>;
}

export interface GhostR2Tick {
  lap: number;
  position: number;
  gap_to_leader_s: number;
  compound: string;
  tyre_life: number;
  stint: number;
  cumulative_delta_s: number;
  aris_action: string;
  aris_confidence: number;
}

export interface GhostData {
  driver: string;
  strategy: { pit_laps: number[]; compounds: string[]; label: string };
  ticks: GhostR2Tick[];
  outcome: { aris_action: string; real_action: string; verdict: string | null };
}

export interface CommsEntry {
  id: string;
  lap: number;
  source: "ARIS" | "USER" | "ARIS_ANALYSIS" | "FIELD" | "ARIS_RESET";
  text: string;
  timestamp: number;
  wetHeuristic?: boolean;
  recommendationId?: string;
}

export type SessionType = "R" | "S" | "Q" | "FP1" | "FP2" | "FP3" | "SS" | "SQ";
export type RoundStatus = "COMPLETED" | "LIVE" | "UPCOMING" | "CANCELLED";
export type SessionStatus = "COMPLETED" | "LIVE" | "UPCOMING";
export type HubMode = "live_session" | "waiting_for_session" | "next_weekend" | "session_ended";

export interface SessionMeta {
  year: number;
  round: number;
  sessionType: SessionType;
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
  headshot_url?: string | null;
}

export interface RoundCard {
  round: number;
  circuitName: string;
  countryFlag: string;
  date: string;
  sessionType: SessionType;
  isSprint: boolean;
  arisEligible: boolean;
  status?: RoundStatus;
  cancelledReason?: string | null;
  totalLaps?: number;
  circuitKey?: string;
}

export interface CircuitMarker {
  kind: string;
  x: number;
  y: number;
  label: string;
}

export interface CircuitSectorPath {
  kind: string;
  label: string;
  x: number[];
  y: number[];
}

export interface CircuitCoords {
  x: number[];
  y: number[];
  markers?: CircuitMarker[];
  pitLaneX?: number[];
  pitLaneY?: number[];
  sectorPaths?: CircuitSectorPath[];
  available?: boolean;
}

export interface LiveTimingRow {
  position: number;
  driver_code: string;
  gap_to_leader_s: number | null;
  gap_to_ahead_s: number | null;
  last_lap_ms: number | null;
  compound: string | null;
  tyre_life: number | null;
  pit_count: number;
  team_colour: string | null;
  in_pit: boolean;
  lap_number: number | null;
  speed_kph: number | null;
  sector1_ms?: number | null;
  sector2_ms?: number | null;
  sector3_ms?: number | null;
  s1_colour?: SectorColour;
  s2_colour?: SectorColour;
  s3_colour?: SectorColour;
  best_lap_ms?: number | null;
  fastest_lap?: boolean;
  eliminated?: boolean;
  status?: "RUNNING" | "DNF" | "DNS";
  laps_completed?: number | null;
  laps_down?: number | null;
  reason?: string | null;
}

export interface LivePosition {
  driver_code: string;
  x: number;
  y: number;
  team_colour: string | null;
  is_pitted: boolean;
  is_dnf: boolean;
  path_frac: number;
  speed_ms: number | null;
}

export interface ApiLapRow {
  driver_code: string;
  lap_number: number;
  lap_time_ms: number | null;
  sector1_ms: number | null;
  sector2_ms: number | null;
  sector3_ms: number | null;
  compound: string | null;
  tyre_life: number | null;
  pit_in_lap: boolean;
  pit_out_lap: boolean;
  position?: number | null;
  end_time_ms?: number | null;
  track_status?: string | null;
}

export interface ApiStintRow {
  driver_code: string;
  stint_number: number;
  compound: string | null;
  lap_start: number;
  lap_end: number;
  total_laps: number;
  average_lap_ms: number | null;
}

export interface HubSession {
  session_type: string;
  session_name: string;
  datetime_utc: string | null;
  status: SessionStatus;
  replayable: boolean;
  live: boolean;
}

export interface HubStrategyPattern {
  label: string;
  note: string;
}

export interface LiveHub {
  mode: HubMode;
  waiting_reason: string | null;
  countdown_seconds: number;
  countdown_target: string | null;
  live: {
    is_live: boolean;
    year: number | null;
    round_number: number | null;
    session_type: string | null;
    session_name: string | null;
    gp_name: string | null;
    current_lap: number | null;
    total_laps: number | null;
    session_flag: string | null;
    session_ended: boolean;
  };
  next: {
    year: number;
    round_number: number;
    name: string;
    circuit_name: string;
    circuit_key: string;
    country: string;
    city: string;
    date_race: string | null;
    status: RoundStatus;
    is_sprint_weekend: boolean;
    is_this_weekend: boolean;
    countdown_seconds: number;
    next_session_name: string | null;
    next_session_datetime: string | null;
    notes: string[];
  };
  weekend_sessions: HubSession[];
  circuit: {
    circuit_key: string;
    circuit_name: string;
    country: string;
    country_flag: string;
    length_km: number | null;
    total_laps: number | null;
    turns: number | null;
    pit_loss_seconds: number | null;
    tyre_stress_rating: string | null;
    strategy_patterns: HubStrategyPattern[];
    race_history: { year: number; winner: string | null; pole: string | null; fastest_lap: string | null }[];
    notes: string[];
  };
  as_of: string;
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

export interface WeatherSessionForecast {
  session: string;
  condition: "sun" | "cloud" | "rain";
  airTempC: number;
  trackTempC: number;
  rainChancePct: number;
}

export interface WeatherTrendPoint {
  lap: number;
  airTempC: number;
  trackTempC: number;
  rainChancePct: number;
}

export interface WeatherForecastData {
  sessions: WeatherSessionForecast[];
  trend: WeatherTrendPoint[];
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
  r2_available?: boolean;
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

export interface CopilotRetrievedChunk {
  chunk_id: string;
  source: string;
  title: string;
  text: string;
  score?: number | null;
}

export interface CopilotToolCall {
  name: string;
  arguments: Record<string, unknown>;
  result?: unknown;
}

export interface CopilotRecommendationRow {
  rank: number;
  label: string;
  delta_vs_stay_out_s: number | null;
  p_best?: number | null;
  p10_delta_s?: number | null;
  p90_delta_s?: number | null;
}

export interface CopilotChatResponse {
  response: string;
  tool_calls: CopilotToolCall[];
  retrieved_chunks: CopilotRetrievedChunk[];
  recommendations: CopilotRecommendationRow[];
  needs_approval: boolean;
}

export interface ExplainStintMeta {
  stint_id: number;
  compound: string;
  start_lap: number;
  end_lap: number;
}

export interface DegradationCurveResponse {
  tyre_age: number[];
  predicted_deg_s: number[];
  actual_deg_s: Array<number | null>;
  lap_number: number[];
  compound: string;
  circuit: string;
  session_type: string;
  session_id?: string | null;
  driver: string;
  stint_id?: number | null;
  start_lap?: number | null;
  end_lap?: number | null;
  fresh_baseline_s?: number | null;
  available_stints: ExplainStintMeta[];
}

export interface GhostSeries {
  laps: number[];
  position: number[];
  gap_to_leader: number[];
  compound: string[];
  pit_laps: number[];
  remaining_s?: number[];
}

export interface GhostVsRealResponse {
  session_id?: string | null;
  driver: string;
  circuit?: string | null;
  ghost: GhostSeries;
  real: GhostSeries;
  delta: { laps: number[]; position_delta: number[]; gap_delta: number[] };
  aris_action?: string;
  explanation?: string;
}

export interface DebriefPitStop {
  lap: number;
  driver?: string | null;
  compound_in?: string | null;
  compound_out?: string | null;
  stint_length?: number | null;
}

export interface DebriefPeriod {
  kind: string;
  start_lap: number;
  end_lap: number;
}

export interface DebriefDecision {
  lap: number;
  type: string;
  recommend_top3: CopilotRecommendationRow[];
  chosen_action: string;
  aris_action?: string | null;
  explanation: string;
}

export interface RaceDebriefResponse {
  timeline: {
    pit_stops: DebriefPitStop[];
    sc_vsc_periods: DebriefPeriod[];
    rain_periods: DebriefPeriod[];
  };
  decisions: DebriefDecision[];
  metadata: {
    circuit: string;
    season: number;
    round_number: number;
    total_laps: number;
    session_id?: string | null;
    focus_driver?: string | null;
    session_type?: string | null;
  };
}

export interface StratPlan {
  id: string;
  name: string;
  pit_laps: number[];
  pit_compounds: string[];
  start_compound: string;
  expected_race_time_s?: number | null;
  description?: string;
  recommended?: boolean;
  pace_gain_s?: number | null;
  pit_cost_s?: number | null;
  risk?: string;
}

export interface QuickAnalysisResponse {
  year: number;
  round_number: number;
  driver_code: string;
  plans: StratPlan[];
  pit_loss_s?: number | null;
}

export type RecommendApiAction = "STAY_OUT" | "BOX" | "PIT_SOON" | "MANAGE_PACE" | "PUSH";

export interface RecommendApiAlternative {
  action: string;
  compound: string | null;
  net_delta_s: number;
  note: string;
}

/** Wire shape of POST /api/aris/recommend (backend RecommendResponse). */
export interface RecommendApiResponse {
  action: RecommendApiAction;
  compound_recommendation: string | null;
  reasoning: string;
  pace_gain_s: number;
  pit_cost_s: number;
  net_delta_s: number;
  confidence: number;
  decision_record_id: string;
  alternatives: RecommendApiAlternative[];
  wet_heuristic?: boolean;
  p10_delta_s?: number | null;
  p90_delta_s?: number | null;
  data_source?: string | null;
  lap_note?: string | null;
}

export type StandingsSource = "jolpica" | "unavailable" | "estimated";

export interface DriverStandingRow {
  position: number;
  driver_code: string;
  full_name: string;
  team_name: string;
  team_colour: string | null;
  points: number;
  wins: number;
  podiums: number;
  fastest_laps: number;
  dnfs: number;
  gap_to_leader: number;
}

export interface ConstructorStandingRow {
  position: number;
  team_name: string;
  team_colour: string | null;
  points: number;
  wins: number;
  podiums: number;
  drivers: string[];
  gap_to_leader: number;
}

export interface DriverStandingsResponse {
  year: number;
  standings: DriverStandingRow[];
  source: StandingsSource;
  champion_code?: string | null;
  leader_code?: string | null;
  message?: string | null;
}

export interface ConstructorStandingsResponse {
  year: number;
  standings: ConstructorStandingRow[];
  source: StandingsSource;
  champion_name?: string | null;
  message?: string | null;
}
