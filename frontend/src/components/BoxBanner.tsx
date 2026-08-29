import { useState } from "react";
import type { RecommendResponse } from "../api/types";
import { C, T, compoundColour, compoundLetter } from "../theme";
import { ReasoningBar } from "./atoms";
import { WetHeuristicBadge } from "./WetHeuristicBadge";

const TYRES: { code: string; label: string }[] = [
  { code: "S", label: "SOFT" },
  { code: "M", label: "MEDIUM" },
  { code: "H", label: "HARD" },
  { code: "I", label: "INTER" },
  { code: "W", label: "WET" },
];

export function BoxBanner({
  rec,
  onBox,
  onStay,
}: {
  rec: RecommendResponse;
  onBox: (compound: string) => void;
  onStay: () => void;
}) {
  const recComp = compoundLetter(rec.compound_recommendation) || "M";
  const [picked, setPicked] = useState(recComp);
  const name = TYRES.find((t) => t.code === picked)?.label ?? picked;
  return (
    <div
      style={{
        padding: "12px 16px",
        borderBottom: `1px solid ${C.border}`,
        background: `linear-gradient(90deg, ${C.signalDim}, ${C.panel})`,
      }}
    >
      <div style={{ fontFamily: T.mono, fontSize: 12, color: C.signal }}>
        ⚡ ARIS RECOMMENDS: BOX this lap
      </div>
      <div style={{ fontFamily: T.body, fontSize: 12, color: C.mist, margin: "6px 0 10px" }}>
        {rec.net_delta_s >= 0 ? "+" : ""}
        {rec.net_delta_s.toFixed(1)}s net vs staying out. Reasoning: {rec.reasoning}
      </div>
      {(rec.wet_heuristic || rec.wet_reduced_confidence) && <WetHeuristicBadge />}
      <ReasoningBar paceGain={rec.pace_gain_s} pitCost={rec.pit_cost_s} />
      <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, margin: "10px 0 6px" }}>CHOOSE TYRE:</div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
        {TYRES.map((t) => {
          const recd = t.code === recComp;
          const on = t.code === picked;
          return (
            <button
              key={t.code}
              onClick={() => setPicked(t.code)}
              style={{
                padding: "6px 12px",
                cursor: "pointer",
                fontFamily: T.mono,
                fontSize: 10,
                background: compoundColour(t.code),
                border: `2px solid ${on ? C.signal : recd ? C.signal : "transparent"}`,
                color: t.code === "H" || t.code === "M" ? C.ink : C.paper,
                borderRadius: 3,
                fontWeight: 700,
                boxShadow: recd ? `0 0 0 1px ${C.signal}` : undefined,
              }}
            >
              ● {t.label}
              {recd ? " ✓" : ""}
            </button>
          );
        })}
      </div>
      <div style={{ fontFamily: T.mono, fontSize: 9, color: C.mist, marginBottom: 8 }}>
        (ARIS recommends {TYRES.find((t) => t.code === recComp)?.label ?? recComp} — amber highlight)
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={() => onBox(picked)}
          style={{ padding: "6px 14px", background: C.green, border: "none", color: C.ink, fontFamily: T.mono, fontSize: 10, cursor: "pointer" }}
        >
          ✓ BOX BOX — {name}
        </button>
        <button
          onClick={() => {
            const next = TYRES.find((t) => t.code !== picked)?.code ?? "H";
            setPicked(next);
          }}
          style={{
            padding: "6px 14px",
            background: "transparent",
            border: `1px solid ${C.border}`,
            color: C.mist,
            fontFamily: T.mono,
            fontSize: 10,
            cursor: "pointer",
          }}
        >
          OVERRIDE TYRE
        </button>
        <button
          onClick={onStay}
          style={{
            padding: "6px 14px",
            background: "transparent",
            border: `1px solid ${C.caution}`,
            color: C.caution,
            fontFamily: T.mono,
            fontSize: 10,
            cursor: "pointer",
          }}
        >
          STAY OUT
        </button>
      </div>
    </div>
  );
}
