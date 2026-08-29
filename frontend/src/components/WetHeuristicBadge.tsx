import { C, T } from "../theme";

export function WetHeuristicBadge() {
  return (
    <div
      style={{
        padding: "4px 10px",
        background: C.blueDim,
        border: `1px solid ${C.blue}`,
        borderRadius: 3,
        marginTop: 6,
        display: "flex",
        alignItems: "center",
        gap: 6,
        flexWrap: "wrap",
      }}
    >
      <span
        style={{
          color: C.blue,
          fontFamily: T.mono,
          fontSize: 9,
          letterSpacing: "0.1em",
        }}
      >
        ⚠ WET HEURISTIC — REDUCED CONFIDENCE
      </span>
      <span style={{ color: C.mist, fontFamily: T.mono, fontSize: 9 }}>
        No calibrated wet model. Conservative estimate.
      </span>
    </div>
  );
}

export function WetConditionsBadge() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 6,
        padding: "3px 10px",
        background: C.blueDim,
        border: `1px solid ${C.blue}`,
        borderRadius: 3,
      }}
    >
      <span style={{ fontSize: 14 }}>🌧</span>
      <span
        style={{
          fontFamily: T.mono,
          fontSize: 10,
          color: C.blue,
          letterSpacing: "0.06em",
        }}
      >
        WET CONDITIONS
      </span>
    </div>
  );
}
