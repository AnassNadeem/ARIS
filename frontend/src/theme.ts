export const C = {
  void: "#070A0E",
  ink: "#0B0E12",
  panel: "#0F1318",
  panel2: "#131820",
  raised: "#181E27",
  border: "#1E2630",
  borderHi: "#2A3545",
  paper: "#E8ECF0",
  mist: "#7A8796",
  faint: "#4A5560",
  ghost: "#2E3840",
  signal: "#E8A33D",
  signalDim: "#1F1A0D",
  signalMid: "#2E2510",
  green: "#2DD4A0",
  greenDim: "#0A1F18",
  blue: "#4FA8E0",
  blueDim: "#0C1E2E",
  purple: "#9B72F0",
  purpleDim: "#15102A",
  caution: "#E05B4A",
  cautionDim: "#2A1210",
  soft: "#E8002D",
  medium: "#D4B800",
  hard: "#C0C4CC",
  inter: "#39B54A",
  wet: "#0067FF",
} as const;

export const T = {
  display: "'Big Shoulders Display', sans-serif",
  body: "'IBM Plex Sans', sans-serif",
  mono: "'IBM Plex Mono', monospace",
} as const;

export const PIRELLI: Record<string, string> = {
  S: C.soft,
  SOFT: C.soft,
  M: C.medium,
  MEDIUM: C.medium,
  H: C.hard,
  HARD: C.hard,
  I: C.inter,
  INTERMEDIATE: C.inter,
  W: C.wet,
  WET: C.wet,
};

export const FONT_HREF =
  "https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800;900&family=IBM+Plex+Sans:wght@300;400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap";

export const FALLBACK_TRACK_PATH =
  "M 60 185 C 35 145, 32 85, 72 55 C 102 32, 155 36, 175 62 C 190 82, 178 106, 198 118 C 232 136, 274 112, 302 88 C 328 66, 364 62, 382 88 C 402 112, 388 148, 356 158 C 328 166, 318 188, 340 203 C 361 218, 352 244, 318 248 C 255 260, 145 252, 98 232 C 74 222, 68 210, 60 185 Z";

export const SPEED_OPTIONS = ["1×", "2×", "5×", "10×", "25×", "50×"] as const;

export const SPEED_MS: Record<(typeof SPEED_OPTIONS)[number], number> = {
  "1×": 90_000,
  "2×": 45_000,
  "5×": 18_000,
  "10×": 9_000,
  "25×": 3_600,
  "50×": 1_800,
};

export const SPEED_FACTOR: Record<(typeof SPEED_OPTIONS)[number], number> = {
  "1×": 1,
  "2×": 2,
  "5×": 5,
  "10×": 10,
  "25×": 25,
  "50×": 50,
};

export function compoundColour(code: string | null | undefined): string {
  if (!code) return "#AAAAAA";
  return PIRELLI[code.toUpperCase()] ?? "#AAAAAA";
}

export function compoundLetter(raw: string | null | undefined): string {
  if (!raw) return "?";
  const u = raw.toUpperCase();
  if (u.startsWith("SOFT") || u === "S") return "S";
  if (u.startsWith("MED") || u === "M") return "M";
  if (u.startsWith("HARD") || u === "H") return "H";
  if (u.startsWith("INTER") || u === "I") return "I";
  if (u.startsWith("WET") || u === "W") return "W";
  return u.slice(0, 1);
}
