import { C, T } from "../theme";
import { Chip, LiveDot } from "./atoms";

export type NavId = "home" | "replay" | "live" | "analytics" | "standings" | "circuits";

export function GlobalNav({
  active,
  year,
  onNav,
  onYear,
  live,
}: {
  active: NavId;
  year: number;
  onNav: (id: NavId) => void;
  onYear: (y: number) => void;
  live?: boolean;
}) {
  const items: [NavId, string][] = [
    ["home", "HOME"],
    ["replay", "REPLAY"],
    ["live", "LIVE"],
    ["analytics", "ANALYTICS"],
    ["standings", "STANDINGS"],
    ["circuits", "CIRCUITS"],
  ];
  return (
    <div
      style={{
        padding: "8px 16px",
        borderBottom: `1px solid ${C.border}`,
        display: "flex",
        alignItems: "center",
        gap: 16,
        background: C.ink,
        flexShrink: 0,
      }}
    >
      <span style={{ fontFamily: T.display, fontSize: 22, fontWeight: 900, letterSpacing: "-0.5px" }}>ARIS</span>
      <div style={{ width: 1, height: 18, background: C.border }} />
      {items.map(([id, label]) => (
        <button
          key={id}
          onClick={() => onNav(id)}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: active === id ? C.signal : C.mist,
            fontFamily: T.mono,
            fontSize: 11,
            letterSpacing: "0.08em",
            fontWeight: active === id ? 700 : 500,
          }}
        >
          {id === "live" && live ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <LiveDot size={6} />
              {label}
            </span>
          ) : (
            label
          )}
        </button>
      ))}
      <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
        {[2024, 2025, 2026].map((y) => (
          <button
            key={y}
            onClick={() => onYear(y)}
            style={{
              padding: "4px 10px",
              borderRadius: 3,
              cursor: "pointer",
              background: year === y ? C.signalMid : "transparent",
              border: `1px solid ${year === y ? C.signal : C.border}`,
              color: year === y ? C.signal : C.mist,
              fontFamily: T.mono,
              fontSize: 11,
            }}
          >
            {y}
          </button>
        ))}
        {year === 2026 && <Chip tone="purple" size="xs">2026 REG NOTE</Chip>}
      </div>
    </div>
  );
}
