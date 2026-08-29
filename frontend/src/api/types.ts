import { z } from "zod";

export const calendarRoundSchema = z
  .object({
    round_number: z.number(),
    name: z.string(),
    circuit_name: z.string(),
    circuit_key: z.string(),
    country: z.string(),
    city: z.string(),
    date_fp1: z.string().nullable().optional(),
    date_fp2: z.string().nullable().optional(),
    date_fp3: z.string().nullable().optional(),
    date_sprint_quali: z.string().nullable().optional(),
    date_sprint: z.string().nullable().optional(),
    date_quali: z.string().nullable().optional(),
    date_race: z.string().nullable().optional(),
    status: z.enum(["COMPLETED", "LIVE", "UPCOMING", "CANCELLED"]),
    is_sprint_weekend: z.boolean(),
    cancelled_reason: z.string().nullable().optional(),
    notes: z.array(z.string()).default([]),
    estimated: z.boolean().optional(),
    official_event_name: z.string().nullable().optional(),
  })
  .passthrough();

export const calendarSchema = z.object({
  year: z.number(),
  rounds: z.array(calendarRoundSchema),
  source: z.enum(["fastf1", "estimated"]),
  as_of: z.string(),
});

export const weekendSessionSchema = z.object({
  session_type: z.string(),
  session_name: z.string(),
  datetime_utc: z.string().nullable().optional(),
  status: z.enum(["COMPLETED", "LIVE", "UPCOMING"]),
});

export const nextRaceSchema = z
  .object({
    year: z.number(),
    round_number: z.number(),
    name: z.string(),
    circuit_name: z.string(),
    circuit_key: z.string(),
    country: z.string(),
    city: z.string(),
    date_race: z.string().nullable().optional(),
    status: z.enum(["COMPLETED", "LIVE", "UPCOMING", "CANCELLED"]),
    is_sprint_weekend: z.boolean(),
    is_this_weekend: z.boolean(),
    countdown_seconds: z.number(),
    days_until: z.number(),
    hours_until: z.number(),
    next_session_name: z.string().nullable().optional(),
    next_session_datetime: z.string().nullable().optional(),
    sessions_this_weekend: z.array(weekendSessionSchema),
    notes: z.array(z.string()).default([]),
    as_of: z.string(),
    off_season: z.boolean().optional().default(false),
  })
  .passthrough();

export const driverSchema = z.object({
  driver_code: z.string(),
  full_name: z.string(),
  team_name: z.string(),
  team_colour: z.string().nullable().optional(),
  driver_number: z.number().nullable().optional(),
  country_code: z.string().nullable().optional(),
  headshot_url: z.string().nullable().optional(),
  estimated: z.boolean().optional(),
});

export const driversSchema = z.object({
  year: z.number(),
  drivers: z.array(driverSchema),
  source: z.enum(["openf1", "fastf1", "estimated"]),
  estimated_label: z.string().nullable().optional(),
});

export const liveStatusSchema = z
  .object({
    is_live: z.boolean(),
    year: z.number().nullable().optional(),
    round_number: z.number().nullable().optional(),
    session_type: z.string().nullable().optional(),
    session_name: z.string().nullable().optional(),
    session_key: z.number().nullable().optional(),
    gp_name: z.string().nullable().optional(),
    current_lap: z.number().nullable().optional(),
    total_laps: z.number().nullable().optional(),
    session_elapsed_seconds: z.number().nullable().optional(),
    session_flag: z.string().optional(),
    last_success_utc: z.string().nullable().optional(),
    replay_mode: z.boolean().optional(),
    view_only: z.boolean().optional(),
    aris_ready: z.boolean().optional(),
    session_remaining_seconds: z.number().nullable().optional(),
    source: z.string().nullable().optional(),
    session_ended: z.boolean().optional(),
    ended_session_name: z.string().nullable().optional(),
    ended_session_type: z.string().nullable().optional(),
    replay_preparing: z.boolean().optional(),
  })
  .passthrough();

export const liveTimingRowSchema = z
  .object({
    position: z.number(),
    driver_code: z.string(),
    gap_to_leader_s: z.number().nullable().optional(),
    gap_to_ahead_s: z.number().nullable().optional(),
    last_lap_ms: z.number().nullable().optional(),
    best_lap_ms: z.number().nullable().optional(),
    sector1_ms: z.number().nullable().optional(),
    sector2_ms: z.number().nullable().optional(),
    sector3_ms: z.number().nullable().optional(),
    s1_colour: z.string().optional(),
    s2_colour: z.string().optional(),
    s3_colour: z.string().optional(),
    compound: z.string().nullable().optional(),
    tyre_life: z.number().nullable().optional(),
    stint_number: z.number().nullable().optional(),
    pit_count: z.number().optional(),
    drs_open: z.boolean().optional(),
    speed_trap_kph: z.number().nullable().optional(),
    team_colour: z.string().nullable().optional(),
    eliminated: z.boolean().optional(),
    in_pit: z.boolean().optional(),
    fastest_lap: z.boolean().optional(),
    reason: z.string().nullable().optional(),
    q1_ms: z.number().nullable().optional(),
    q2_ms: z.number().nullable().optional(),
    q3_ms: z.number().nullable().optional(),
    lap_number: z.number().nullable().optional(),
    throttle_pct: z.number().nullable().optional(),
    brake_pct: z.number().nullable().optional(),
    speed_kph: z.number().nullable().optional(),
  })
  .passthrough();

export const liveWeatherSchema = z
  .object({
    is_live: z.boolean(),
    air_temp: z.number().nullable().optional(),
    track_temp: z.number().nullable().optional(),
    humidity: z.number().nullable().optional(),
    rainfall: z.boolean().nullable().optional(),
    wind_speed: z.number().nullable().optional(),
    wind_direction: z.number().nullable().optional(),
    pressure: z.number().nullable().optional(),
    last_success_utc: z.string().nullable().optional(),
  })
  .passthrough();

export const liveTimingSchema = z.object({
  is_live: z.boolean(),
  session_key: z.number().nullable().optional(),
  rows: z.array(liveTimingRowSchema),
  last_success_utc: z.string().nullable().optional(),
  current_lap: z.number().nullable().optional(),
  replay: z.boolean().optional(),
  rainfall: z.boolean().optional(),
});

export const driverStandingSchema = z
  .object({
    position: z.number(),
    driver_code: z.string(),
    full_name: z.string(),
    team_name: z.string(),
    team_colour: z.string().nullable().optional(),
    points: z.number(),
    wins: z.number(),
    podiums: z.number().optional(),
    fastest_laps: z.number().optional(),
    dnfs: z.number().optional(),
    gap_to_leader: z.number(),
  })
  .passthrough();

export const driverStandingsSchema = z.object({
  year: z.number(),
  standings: z.array(driverStandingSchema),
  source: z.enum(["jolpica", "unavailable", "estimated"]),
  champion_code: z.string().nullable().optional(),
  leader_code: z.string().nullable().optional(),
});

export const constructorStandingSchema = z
  .object({
    position: z.number(),
    team_name: z.string(),
    team_colour: z.string().nullable().optional(),
    points: z.number(),
    wins: z.number(),
    podiums: z.number().optional(),
    drivers: z.array(z.string()).optional(),
    gap_to_leader: z.number(),
  })
  .passthrough();

export const constructorStandingsSchema = z.object({
  year: z.number(),
  standings: z.array(constructorStandingSchema),
  source: z.enum(["jolpica", "unavailable", "estimated"]),
  champion_name: z.string().nullable().optional(),
});

export const lapRowSchema = z
  .object({
    driver_code: z.string(),
    lap_number: z.number(),
    lap_time_ms: z.number().nullable().optional(),
    sector1_ms: z.number().nullable().optional(),
    sector2_ms: z.number().nullable().optional(),
    sector3_ms: z.number().nullable().optional(),
    compound: z.string().nullable().optional(),
    tyre_life: z.number().nullable().optional(),
    is_personal_best: z.boolean().optional(),
    pit_in_lap: z.boolean().optional(),
    pit_out_lap: z.boolean().optional(),
    stint_number: z.number().nullable().optional(),
    s1_colour: z.string().optional(),
    s2_colour: z.string().optional(),
    s3_colour: z.string().optional(),
    team: z.string().nullable().optional(),
  })
  .passthrough();

export const lapsSchema = z.object({
  year: z.number(),
  round_number: z.number(),
  session_type: z.string(),
  laps: z.array(lapRowSchema),
});

export const liveLapsSchema = z.object({
  is_live: z.boolean(),
  session_key: z.number().nullable().optional(),
  current_lap: z.number().nullable().optional(),
  laps: z.array(lapRowSchema),
});

export const liveTelemetrySchema = z.object({
  is_live: z.boolean(),
  driver_code: z.string(),
  t_s: z.array(z.number()).default([]),
  throttle: z.array(z.number()).default([]),
  speed: z.array(z.number()).default([]),
  brake: z.array(z.number()).default([]),
  rpm: z.array(z.number()).optional(),
});

export const recommendSchema = z
  .object({
    action: z.string(),
    compound_recommendation: z.string().nullable().optional(),
    reasoning: z.string(),
    pace_gain_s: z.number(),
    pit_cost_s: z.number(),
    net_delta_s: z.number(),
    confidence: z.number(),
    decision_record_id: z.string(),
    alternatives: z.array(z.any()).default([]),
    wet_reduced_confidence: z.boolean().optional(),
    wet_heuristic: z.boolean().optional(),
    reg_note_2026: z.boolean().optional(),
    data_source: z.string().nullable().optional(),
    lap_note: z.string().nullable().optional(),
    ingest_status: z.string().nullable().optional(),
  })
  .passthrough();

export type CalendarRound = z.infer<typeof calendarRoundSchema>;
export type CalendarResponse = z.infer<typeof calendarSchema>;
export type NextRace = z.infer<typeof nextRaceSchema>;
export type Driver = z.infer<typeof driverSchema>;
export type DriversResponse = z.infer<typeof driversSchema>;
export type LiveStatus = z.infer<typeof liveStatusSchema>;
export type LiveTimingRow = z.infer<typeof liveTimingRowSchema>;
export type LiveTiming = z.infer<typeof liveTimingSchema>;
export type LiveWeather = z.infer<typeof liveWeatherSchema>;
export type DriverStandings = z.infer<typeof driverStandingsSchema>;
export type ConstructorStandings = z.infer<typeof constructorStandingsSchema>;
export type LapsResponse = z.infer<typeof lapsSchema>;
export type RecommendResponse = z.infer<typeof recommendSchema>;
export type WeekendSession = z.infer<typeof weekendSessionSchema>;

export const sessionResultRowSchema = z
  .object({
    position: z.number().nullable().optional(),
    driver_code: z.string(),
    team: z.string().nullable().optional(),
    time_ms: z.number().nullable().optional(),
    gap_to_winner_ms: z.number().nullable().optional(),
    points: z.number().nullable().optional(),
    fastest_lap: z.boolean().optional(),
    laps_completed: z.number().nullable().optional(),
    status: z.string(),
    grid: z.number().nullable().optional(),
  })
  .passthrough();

export const sessionResultsSchema = z.object({
  year: z.number(),
  round_number: z.number(),
  session_type: z.string(),
  results: z.array(sessionResultRowSchema),
});

export const tyreStrategyStintSchema = z.object({
  driver_code: z.string(),
  lap_start: z.number(),
  lap_end: z.number(),
  compound: z.string().nullable().optional(),
  fresh: z.boolean().nullable().optional(),
  tyre_life_at_end: z.number().nullable().optional(),
});

export const tyreStrategySchema = z.object({
  year: z.number(),
  round_number: z.number(),
  stints: z.array(tyreStrategyStintSchema),
});

export type SessionResultRow = z.infer<typeof sessionResultRowSchema>;
export type SessionResultsResponse = z.infer<typeof sessionResultsSchema>;
export type TyreStrategyStint = z.infer<typeof tyreStrategyStintSchema>;
export type TyreStrategyResponse = z.infer<typeof tyreStrategySchema>;

export const roundSessionsSchema = z.object({
  year: z.number(),
  round_number: z.number(),
  name: z.string(),
  is_sprint_weekend: z.boolean(),
  sessions: z.array(
    z.object({
      session_type: z.string(),
      session_name: z.string(),
      datetime_utc: z.string().nullable().optional(),
      status: z.enum(["COMPLETED", "LIVE", "UPCOMING"]),
    }),
  ),
});

export type RoundSessions = z.infer<typeof roundSessionsSchema>;

export type ReplayWatchPick = {
  year: number;
  round: z.infer<typeof calendarRoundSchema>;
  sessionType: string;
  segment?: string | null;
};

export type CircuitCharacteristics = {
  circuit_key: string;
  name: string;
  country: string;
  lap_length_km: number | null;
  turns: number | null;
  drs_zones: number | null;
  pit_loss_seconds: number | null;
  total_laps: number | null;
  tyre_stress_rating?: string | null;
  track_evolution_rating?: string | null;
  sector_descriptions: string[];
  similar_circuits: string[];
  known_deg_compounds: Record<string, number>;
  aris_notes?: {
    undercut_effectiveness: string;
    tyre_compound_tendencies: string;
    overtaking_difficulty: string;
    sc_probability_history: string;
    summary: string;
  } | null;
  estimated: boolean;
  reg_note_2026: boolean;
};

export type CircuitHistoryYear = {
  year: number;
  winner: string | null;
  winner_team: string | null;
  pole: string | null;
  fastest_lap: string | null;
  weather?: string | null;
  incident_notes: string[];
  winner_grid?: number | null;
  race_name?: string | null;
};

export type CircuitHistoryResponse = {
  circuit_key: string;
  years: CircuitHistoryYear[];
  from_year?: number;
  typical_stop_count?: number | null;
  median_first_stop_lap?: number | null;
  most_common_winner?: string | null;
  analysis?: string;
};

export type CircuitMap = {
  year: number;
  round_number: number;
  x: number[];
  y: number[];
  corners: {
    number: number;
    letter?: string;
    angle?: number | null;
    distance?: number | null;
    x: number;
    y: number;
    description?: string | null;
  }[];
  markers?: { kind: string; x: number; y: number; label: string }[];
  drs_segments?: number[][];
  pit_lane_x?: number[];
  pit_lane_y?: number[];
  pit_stalls?: number[][];
  grid_slots?: number[][];
  bounds?: { min_x: number; max_x: number; min_y: number; max_y: number } | null;
  available: boolean;
  fallback?: boolean;
  error?: string | null;
  view_box?: string;
};

export type CarPosition = {
  driver_code: string;
  x: number;
  y: number;
  path_frac?: number | null;
  speed_ms?: number | null;
  team_colour?: string | null;
  is_pitted?: boolean;
  is_dnf?: boolean;
  reason?: string | null;
};

export type QualiWindow = { id: string; label: string; start_s: number; end_s: number };

export type ReplayPathTrace = { t: number[]; f: number[] };

export type ReplayPath = {
  session_key: number;
  source?: string | null;
  date_start?: string | null;
  traces: Record<string, ReplayPathTrace>;
  drivers?: string[];
};

export type ChatResponse = { answer: string; cited_ids: string[]; abstained: boolean };
export type StratPlan = {
  id: string;
  name: string;
  pit_laps: number[];
  pit_compounds: string[];
  start_compound: string;
  expected_race_time_s: number | null;
  description: string;
  recommended: boolean;
  pace_gain_s: number | null;
  pit_cost_s: number | null;
  risk: string;
  reasoning?: string;
};

export type SessionConfig = {
  mode: "replay" | "live";
  year: number;
  round: CalendarRound;
  driver: string;
  arisMode: "auto" | "assisted";
  planId: string;
};

export type CalendarState =
  | { type: "LIVE_RACE"; next: NextRace; live: LiveStatus }
  | { type: "LIVE_QUALI"; next: NextRace; live: LiveStatus }
  | { type: "LIVE_PRACTICE"; next: NextRace; live: LiveStatus; fpNumber: 1 | 2 | 3 }
  | { type: "RACE_WEEKEND"; next: NextRace; daysUntilRace: number }
  | { type: "BETWEEN_ROUNDS"; next: NextRace; daysUntil: number }
  | { type: "POST_RACE"; completed: CalendarRound; hoursAgo: number; year: number }
  | { type: "OFF_SEASON"; nextYear: number; next: NextRace };
