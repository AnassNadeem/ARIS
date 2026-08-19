import { NavLink } from "react-router-dom";
import { C, T } from "../theme";
import { LiveDot } from "./atoms";
import { useFlow } from "../session/FlowContext";

const ITEMS: { to: string; id: string; label: string }[] = [
  { to: "/", id: "home", label: "HOME" },
  { to: "/replay", id: "replay", label: "REPLAY" },
  { to: "/live", id: "live", label: "LIVE" },
  { to: "/standings", id: "standings", label: "STANDINGS" },
  { to: "/circuits", id: "circuits", label: "CIRCUITS" },
];

export function GlobalNav({ live }: { live?: boolean }) {
  const flow = useFlow();
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
      <NavLink
        to="/"
        style={{
          fontFamily: T.display,
          fontSize: 22,
          fontWeight: 900,
          letterSpacing: "-0.5px",
          color: C.paper,
          textDecoration: "none",
        }}
      >
        ARIS
      </NavLink>
      <div style={{ width: 1, height: 18, background: C.border }} />
      {ITEMS.map((item) => (
        <NavLink
          key={item.id}
          to={item.to}
          end={item.to === "/"}
          onClick={() => {
            if (item.id === "replay") {
              flow.setConfig(null);
              flow.setPartial(null);
              flow.setReplayStep("setup");
              flow.setPreselectRound(null);
            }
          }}
          style={({ isActive }) => ({
            background: "none",
            border: "none",
            cursor: "pointer",
            color: isActive ? C.signal : C.mist,
            fontFamily: T.mono,
            fontSize: 11,
            letterSpacing: "0.08em",
            fontWeight: isActive ? 700 : 500,
            textDecoration: "none",
          })}
        >
          {item.id === "live" && live ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <LiveDot size={6} />
              {item.label}
            </span>
          ) : (
            item.label
          )}
        </NavLink>
      ))}
    </div>
  );
}
