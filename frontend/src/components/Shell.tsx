import type { ReactNode } from "react";
import { C, T } from "../theme";
import { Chip, LiveDot } from "./atoms";
import type { SessionConfig } from "../api/types";

export function Shell({
  children,
  title,
  config,
}: {
  children: ReactNode;
  title?: string;
  config?: SessionConfig | null;
}) {
  return (
    <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {title && (
        <div
          style={{
            padding: "8px 16px",
            borderBottom: `1px solid ${C.border}`,
            display: "flex",
            alignItems: "center",
            gap: 10,
            flexShrink: 0,
          }}
        >
          <span style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, letterSpacing: "0.1em" }}>{title}</span>
          {config && (
            <>
              <Chip tone="mist">{config.round.name} {config.year}</Chip>
              {config.mode === "live" ? (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                  <LiveDot />
                  <Chip tone="caution">LIVE</Chip>
                </span>
              ) : (
                <Chip tone="mist">REPLAY</Chip>
              )}
              <Chip tone="signal">{config.driver}</Chip>
            </>
          )}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, overflow: "auto" }}>{children}</div>
    </div>
  );
}
