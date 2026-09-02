import type {
  CarState,
  Compound,
  DriverListing,
  RecentRaceCard,
  RoundCard,
  WeatherForecastData,
} from "@/lib/types";

// Deterministic pseudo-random in [0, 1) so mock data is stable across renders/SSR.
function prand(seed: number): number {
  const x = Math.sin(seed * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

// Demo-only 2025/26-shaped grid (HAM at Ferrari). Replay must never use this
// for team/colour — those come from race_field.json for the selected race.
export const MOCK_DRIVERS_2025: DriverListing[] = [
  { driver_number: 1, driver_code: "VER", full_name: "Max Verstappen", team: "Red Bull Racing", team_colour: "#3671C6" },
  { driver_number: 4, driver_code: "NOR", full_name: "Lando Norris", team: "McLaren", team_colour: "#FF8000" },
  { driver_number: 81, driver_code: "PIA", full_name: "Oscar Piastri", team: "McLaren", team_colour: "#FF8000" },
  { driver_number: 16, driver_code: "LEC", full_name: "Charles Leclerc", team: "Ferrari", team_colour: "#E8002D" },
  { driver_number: 55, driver_code: "SAI", full_name: "Carlos Sainz", team: "Williams", team_colour: "#1868DB" },
  { driver_number: 44, driver_code: "HAM", full_name: "Lewis Hamilton", team: "Ferrari", team_colour: "#E8002D" },
  { driver_number: 63, driver_code: "RUS", full_name: "George Russell", team: "Mercedes", team_colour: "#27F4D2" },
  { driver_number: 12, driver_code: "ANT", full_name: "Kimi Antonelli", team: "Mercedes", team_colour: "#27F4D2" },
  { driver_number: 14, driver_code: "ALO", full_name: "Fernando Alonso", team: "Aston Martin", team_colour: "#00665E" },
  { driver_number: 18, driver_code: "STR", full_name: "Lance Stroll", team: "Aston Martin", team_colour: "#00665E" },
  { driver_number: 10, driver_code: "GAS", full_name: "Pierre Gasly", team: "Alpine", team_colour: "#0093CC" },
  { driver_number: 7, driver_code: "DOO", full_name: "Jack Doohan", team: "Alpine", team_colour: "#0093CC" },
  { driver_number: 22, driver_code: "TSU", full_name: "Yuki Tsunoda", team: "Red Bull Racing", team_colour: "#3671C6" },
  { driver_number: 30, driver_code: "LAW", full_name: "Liam Lawson", team: "Racing Bulls", team_colour: "#6692FF" },
  { driver_number: 23, driver_code: "ALB", full_name: "Alex Albon", team: "Williams", team_colour: "#1868DB" },
  { driver_number: 27, driver_code: "HUL", full_name: "Nico Hulkenberg", team: "Sauber", team_colour: "#52E252" },
  { driver_number: 5, driver_code: "BOR", full_name: "Gabriel Bortoleto", team: "Sauber", team_colour: "#52E252" },
  { driver_number: 31, driver_code: "OCO", full_name: "Esteban Ocon", team: "Haas", team_colour: "#B6BABD" },
  { driver_number: 87, driver_code: "BEA", full_name: "Oliver Bearman", team: "Haas", team_colour: "#B6BABD" },
  { driver_number: 6, driver_code: "HAD", full_name: "Isack Hadjar", team: "Racing Bulls", team_colour: "#6692FF" },
];

export const COMPOUND_COLOUR: Record<Compound, string> = {
  SOFT: "#E8002D",
  MEDIUM: "#F5D300",
  HARD: "#FFFFFF",
  INTERMEDIATE: "#39FF14",
  WET: "#1E90FF",
};

// Rough oval approximation of Zandvoort's layout — placeholder until
// /api/circuit-coords is wired to real fastf1.get_circuit_info() data.
export function zandvoortOvalCoords(points = 120): { x: number[]; y: number[] } {
  const x: number[] = [];
  const y: number[] = [];
  const cx = 400;
  const cy = 250;
  const rx = 340;
  const ry = 200;
  for (let i = 0; i < points; i++) {
    const t = (i / points) * Math.PI * 2;
    // Slight banked-corner distortion so it doesn't read as a perfect ellipse.
    const wobble = Math.sin(t * 3) * 14 + Math.sin(t * 7) * 6;
    x.push(cx + (rx + wobble) * Math.cos(t));
    y.push(cy + (ry + wobble * 0.6) * Math.sin(t));
  }
  return { x, y };
}

export function mockRoundsForYear(year: number): RoundCard[] {
  const calendar: { name: string; flag: string; sprint?: boolean }[] = [
    { name: "Bahrain", flag: "🇧🇭" },
    { name: "Saudi Arabia", flag: "🇸🇦" },
    { name: "Australia", flag: "🇦🇺" },
    { name: "Japan", flag: "🇯🇵" },
    { name: "China", flag: "🇨🇳", sprint: true },
    { name: "Miami", flag: "🇺🇸", sprint: true },
    { name: "Emilia Romagna", flag: "🇮🇹" },
    { name: "Monaco", flag: "🇲🇨" },
    { name: "Canada", flag: "🇨🇦" },
    { name: "Spain", flag: "🇪🇸" },
    { name: "Austria", flag: "🇦🇹", sprint: true },
    { name: "Great Britain", flag: "🇬🇧" },
    { name: "Belgium", flag: "🇧🇪" },
    { name: "Hungary", flag: "🇭🇺" },
    { name: "Netherlands", flag: "🇳🇱" },
    { name: "Italy", flag: "🇮🇹" },
    { name: "Azerbaijan", flag: "🇦🇿" },
    { name: "Singapore", flag: "🇸🇬" },
    { name: "United States", flag: "🇺🇸", sprint: true },
    { name: "Mexico City", flag: "🇲🇽" },
    { name: "São Paulo", flag: "🇧🇷", sprint: true },
    { name: "Las Vegas", flag: "🇺🇸" },
    { name: "Qatar", flag: "🇶🇦", sprint: true },
    { name: "Abu Dhabi", flag: "🇦🇪" },
  ];
  const rounds = calendar.map((c, i) => ({
    round: i + 1,
    circuitName: c.name,
    countryFlag: c.flag,
    date: new Date(year, i, 1 + i * 12).toISOString(),
    sessionType: "R" as const,
    isSprint: Boolean(c.sprint),
    arisEligible: true,
    status: "COMPLETED" as const,
  }));
  if (year >= 2026) {
    return rounds.filter((r) => r.circuitName !== "Bahrain" && r.circuitName !== "Saudi Arabia");
  }
  return rounds;
}

// The last N completed rounds, most recent first — used for the home page
// "Replay a race" preview cards. Dates are backdated from today so the cards
// always read as "already happened".
export function mockRecentRaces(limit = 3): RecentRaceCard[] {
  const winners = [
    { code: "VER", name: "Max Verstappen" },
    { code: "NOR", name: "Lando Norris" },
    { code: "PIA", name: "Oscar Piastri" },
    { code: "LEC", name: "Charles Leclerc" },
    { code: "RUS", name: "George Russell" },
  ];
  const rounds = mockRoundsForYear(2025).slice(0, 14).reverse();
  const now = new Date();
  return rounds.slice(0, limit).map((r, i) => {
    const date = new Date(now);
    date.setDate(date.getDate() - (i + 1) * 7);
    const w = winners[i % winners.length];
    return {
      year: 2025,
      round: r.round,
      circuitName: r.circuitName,
      countryFlag: r.countryFlag,
      raceName: `${r.circuitName} Grand Prix`,
      date: date.toISOString(),
      winner: w.name,
      winnerCode: w.code,
      sessionType: r.isSprint ? "S" : "R",
    };
  });
}

// Deterministic session-weekend weather: a forecast strip (per session) plus
// an in-race trend so the panel reads as both "what's coming" and "what's
// happening now".
export function mockWeatherForecast(totalLaps = 72): WeatherForecastData {
  const sessionNames = ["FP1", "FP2", "FP3", "Qualifying", "Race"];
  const sessions = sessionNames.map((session, i) => {
    const rainRoll = prand(i * 4.4 + 1);
    const condition: "sun" | "cloud" | "rain" = rainRoll > 0.82 ? "rain" : rainRoll > 0.55 ? "cloud" : "sun";
    return {
      session,
      condition,
      airTempC: Math.round(20 + prand(i * 2.1) * 8),
      trackTempC: Math.round(28 + prand(i * 3.3) * 14),
      rainChancePct: Math.round(rainRoll * 100),
    };
  });

  const trend = Array.from({ length: totalLaps }, (_, i) => {
    const lap = i + 1;
    const drift = Math.sin((lap / totalLaps) * Math.PI * 1.4) * 3;
    return {
      lap,
      airTempC: Number((22 + drift + prand(lap * 0.6) * 1.2).toFixed(1)),
      trackTempC: Number((34 + drift * 1.6 + prand(lap * 0.9) * 2).toFixed(1)),
      rainChancePct: Math.round(Math.max(0, prand(lap * 1.3) * 30 - 10 + Math.sin(lap / 12) * 10)),
    };
  });

  return { sessions, trend };
}

export function mockZandvoortCars(): Record<string, CarState> {
  const { x, y } = zandvoortOvalCoords();
  const compounds: Compound[] = ["HARD", "MEDIUM", "SOFT"];
  const out: Record<string, CarState> = {};
  MOCK_DRIVERS_2025.forEach((d, i) => {
    const frac = i / MOCK_DRIVERS_2025.length;
    const idx = Math.floor(frac * x.length);
    out[d.driver_code] = {
      driver_code: d.driver_code,
      driver_number: d.driver_number,
      full_name: d.full_name,
      team: d.team,
      team_colour: d.team_colour,
      position: i + 1,
      lap_number: 23,
      compound: compounds[i % compounds.length],
      tyre_life: 8 + (i % 12),
      gap_to_leader_s: i === 0 ? 0 : i * 3.4 + Math.random() * 2,
      gap_ahead_s: i === 0 ? null : 1.2 + Math.random() * 3,
      gap_ahead_history: [2.1, 1.9, 1.7, 1.5, 1.4],
      last_lap_s: 71.2 + Math.random() * 1.5,
      pit_stops: i % 3 === 0 ? 1 : 0,
      is_pitted: false,
      is_dnf: false,
      x: x[idx],
      y: y[idx],
      speed_kph: 260 + Math.random() * 40,
      heading_rad: 0,
      laps_remaining: 49,
      total_laps: 72,
      is_aris_driver: d.driver_code === "VER",
    };
  });
  return out;
}
