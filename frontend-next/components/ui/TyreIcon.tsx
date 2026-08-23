import { COMPOUND_COLOUR } from "@/lib/mockData";
import type { Compound } from "@/lib/types";

const LETTER: Record<Compound, string> = {
  SOFT: "S",
  MEDIUM: "M",
  HARD: "H",
  INTERMEDIATE: "I",
  WET: "W",
};

export function TyreIcon({ compound, size = 14 }: { compound: Compound; size?: number }) {
  const colour = COMPOUND_COLOUR[compound] ?? "#888888";
  const dark = compound === "HARD" || compound === "MEDIUM";
  return (
    <span
      title={compound}
      className="inline-flex shrink-0 items-center justify-center rounded-full border font-mono-data font-bold"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.55,
        background: colour,
        color: dark ? "#0a0a0a" : "#0a0a0a",
        borderColor: "rgba(0,0,0,0.35)",
      }}
    >
      {LETTER[compound] ?? "?"}
    </span>
  );
}
