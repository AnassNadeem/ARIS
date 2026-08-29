import type { CSSProperties, ReactNode } from "react";
import { C, T, compoundColour, compoundLetter } from "../theme";

export function Chip({
  children,
  tone = "mist",
  size = "sm",
}: {
  children: ReactNode;
  tone?: "mist" | "signal" | "green" | "caution" | "blue" | "purple";
  size?: "sm" | "xs";
}) {
  const map = {
    mist: { bg: "transparent", fg: C.mist, bd: C.border },
    signal: { bg: C.signalMid, fg: C.signal, bd: C.signal + "80" },
    green: { bg: C.greenDim, fg: C.green, bd: C.green + "60" },
    caution: { bg: C.cautionDim, fg: C.caution, bd: C.caution + "60" },
    blue: { bg: C.blueDim, fg: C.blue, bd: C.blue + "60" },
    purple: { bg: C.purpleDim, fg: C.purple, bd: C.purple + "60" },
  };
  const t = map[tone];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: size === "xs" ? "4px 6px" : "3px 8px",
        borderRadius: 3,
        border: `1px solid ${t.bd}`,
        background: t.bg,
        color: t.fg,
        fontFamily: T.mono,
        fontSize: size === "xs" ? 9 : 10,
        letterSpacing: "0.04em",
        fontWeight: 600,
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

export function LiveDot({ size = 7, color = C.caution }: { size?: number; color?: string }) {
  return (
    <span style={{ position: "relative", display: "inline-flex", width: size, height: size }}>
      <span
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "50%",
          background: color,
          opacity: 0.5,
          animation: "ping 1.5s cubic-bezier(0,0,0.2,1) infinite",
        }}
      />
      <span
        style={{
          position: "relative",
          width: size,
          height: size,
          borderRadius: "50%",
          background: color,
        }}
      />
    </span>
  );
}

export function TyreBadge({
  compound,
  life,
  size = "md",
}: {
  compound: string | null | undefined;
  life?: number | null;
  size?: "md" | "sm";
}) {
  const letter = compoundLetter(compound);
  const col = compoundColour(letter);
  const r = size === "sm" ? 12 : 16;
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      <span
        style={{
          width: r,
          height: r,
          borderRadius: "50%",
          border: `2px solid ${col}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: T.mono,
          fontSize: r === 12 ? 8 : 10,
          fontWeight: 700,
          color: col,
        }}
      >
        {letter}
      </span>
      {life !== undefined && life !== null && (
        <span style={{ fontFamily: T.mono, color: C.mist, fontSize: 10 }}>{life}L</span>
      )}
    </span>
  );
}

export function SectorDot({ tone }: { tone?: string }) {
  const map: Record<string, string> = {
    purple: C.purple,
    green: C.green,
    yellow: C.signal,
    grey: C.mist,
    none: C.mist,
  };
  return (
    <span
      style={{
        display: "inline-block",
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: map[tone || "grey"] || C.mist,
      }}
    />
  );
}

export function Panel({
  title,
  right,
  children,
  style = {},
}: {
  title?: string;
  right?: ReactNode;
  children: ReactNode;
  style?: CSSProperties;
}) {
  return (
    <div
      style={{
        background: C.panel,
        border: `1px solid ${C.border}`,
        borderRadius: 6,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        ...style,
      }}
    >
      {title && (
        <div
          style={{
            padding: "8px 14px",
            borderBottom: `1px solid ${C.border}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <span
            style={{
              fontFamily: T.mono,
              fontSize: 10,
              letterSpacing: "0.1em",
              color: C.mist,
              textTransform: "uppercase",
            }}
          >
            {title}
          </span>
          {right}
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0, height: "100%", display: "flex", flexDirection: "column" }}>{children}</div>
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  accent?: string;
}) {
  return (
    <div>
      <div
        style={{
          fontFamily: T.mono,
          fontSize: 10,
          color: C.faint,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          marginBottom: 2,
        }}
      >
        {label}
      </div>
      <div style={{ fontFamily: T.display, fontSize: 22, fontWeight: 800, color: accent || C.paper, lineHeight: 1 }}>
        {value}
      </div>
      {sub && (
        <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, marginTop: 2 }}>
          {sub}
        </div>
      )}
    </div>
  );
}

export function ReasoningBar({
  paceGain,
  pitCost,
  label,
}: {
  paceGain: number;
  pitCost: number;
  label?: boolean;
}) {
  const total = Math.abs(paceGain) + Math.abs(pitCost) || 1;
  const pct = Math.round((Math.abs(paceGain) / total) * 100);
  const net = paceGain - pitCost;
  const positive = net > 0;
  return (
    <div style={{ marginTop: 8 }}>
      {label && (
        <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, letterSpacing: "0.1em", marginBottom: 4 }}>
          REASONING
        </div>
      )}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginBottom: 3,
          fontFamily: T.mono,
          fontSize: 9,
          color: C.faint,
        }}
      >
        <span>PACE GAINED +{paceGain.toFixed(1)}s</span>
        <span style={{ color: positive ? C.green : C.caution }}>
          NET {positive ? "+" : ""}
          {net.toFixed(1)}s
        </span>
        <span>PIT-LOSS {pitCost.toFixed(1)}s</span>
      </div>
      <div style={{ display: "flex", height: 6, borderRadius: 3, overflow: "hidden", background: C.ghost }}>
        <div style={{ width: pct + "%", background: C.green }} />
        <div style={{ width: 100 - pct + "%", background: C.caution, opacity: 0.7 }} />
      </div>
    </div>
  );
}

export function TabBar({
  tabs,
  active,
  onChange,
  style = {},
}: {
  tabs: [string, string][];
  active: string;
  onChange: (id: string) => void;
  style?: CSSProperties;
}) {
  return (
    <div style={{ display: "flex", gap: 2, ...style }}>
      {tabs.map(([id, label]) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 5,
            padding: "6px 12px",
            borderRadius: "4px 4px 0 0",
            border: "none",
            cursor: "pointer",
            background: active === id ? C.panel2 : "transparent",
            color: active === id ? C.signal : C.mist,
            fontFamily: T.mono,
            fontSize: 10,
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            borderTop: active === id ? `1px solid ${C.signal}` : "1px solid transparent",
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function SectionLabel({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
      <div style={{ fontFamily: T.mono, fontSize: 10, letterSpacing: "0.12em", color: C.faint, textTransform: "uppercase" }}>
        {children}
      </div>
      {right}
    </div>
  );
}

export function Skeleton({ height = 12, width = "100%" }: { height?: number; width?: string | number }) {
  return (
    <div
      style={{
        height,
        width,
        borderRadius: 3,
        background: `linear-gradient(90deg, ${C.raised}, ${C.border}, ${C.raised})`,
        backgroundSize: "200% 100%",
        animation: "shimmer 1.4s ease-in-out infinite",
      }}
    />
  );
}

export function SkeletonPanel({ rows = 8, label }: { rows?: number; label?: string }) {
  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
      {label && (
        <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, letterSpacing: "0.04em", marginBottom: 4 }}>
          {label}
        </div>
      )}
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} height={12} width={`${92 - (i % 4) * 8}%`} />
      ))}
    </div>
  );
}

function friendlyError(message: string): string {
  if (/timeout|abort|failed to fetch|network error/i.test(message)) {
    return "Could not load data. This may take a moment on first load as data is being cached.";
  }
  return message.replace(/Timeout \([^)]+\)\s*/gi, "").replace(/Failed to fetch/gi, "").trim() || message;
}

export function PanelError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontFamily: T.body, fontSize: 12, color: C.caution, marginBottom: 8 }}>{friendlyError(message)}</div>
      <button
        onClick={onRetry}
        style={{
          padding: "6px 12px",
          background: C.raised,
          border: `1px solid ${C.border}`,
          color: C.signal,
          fontFamily: T.mono,
          fontSize: 10,
          cursor: "pointer",
          borderRadius: 3,
        }}
      >
        RETRY
      </button>
    </div>
  );
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <PanelError message={message} onRetry={onRetry} />;
}

export function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div style={{ padding: 16 }}>
      <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal, marginBottom: 6 }}>{title}</div>
      <div style={{ fontFamily: T.body, fontSize: 12, color: C.mist, lineHeight: 1.6 }}>{body}</div>
    </div>
  );
}

export function formatMs(ms: number | null | undefined): string {
  if (ms == null) return "—";
  const s = ms / 1000;
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  return m > 0 ? `${m}:${rest.toFixed(3).padStart(6, "0")}` : rest.toFixed(3);
}

export function YearSelect({
  year,
  years,
  onChange,
}: {
  year: number;
  years: number[];
  onChange: (y: number) => void;
}) {
  return (
    <select
      value={year}
      onChange={(e) => onChange(Number(e.target.value))}
      style={{
        background: C.raised,
        color: C.paper,
        border: `1px solid ${C.border}`,
        fontFamily: T.mono,
        fontSize: 13,
        padding: "8px 12px",
        borderRadius: 4,
        minWidth: 120,
      }}
    >
      {years.map((y) => (
        <option key={y} value={y}>
          {y}
        </option>
      ))}
    </select>
  );
}

export function initials(name: string): string {
  const parts = name.split(" ").filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}
