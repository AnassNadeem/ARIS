/** Shared Recharts axis styling so every analytics panel labels X/Y the same way. */
export const AXIS_TICK = {
  fontFamily: "var(--font-jbmono)",
  fontSize: 10,
  fill: "#888888",
} as const;

export function xAxisLabel(value: string) {
  return {
    value,
    position: "insideBottom" as const,
    offset: -2,
    fill: "#888888",
    fontSize: 10,
  };
}

export function yAxisLabel(value: string) {
  return {
    value,
    angle: -90,
    position: "insideLeft" as const,
    fill: "#888888",
    fontSize: 10,
  };
}
