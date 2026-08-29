import type { LiveTimingRow } from "../api/types";
import { C, T } from "../theme";
import { Skeleton, TyreBadge, formatMs } from "./atoms";

function sectorColor(tone?: string) {
  if (tone === "purple") return C.purple;
  if (tone === "green") return C.green;
  if (tone === "yellow") return C.signal;
  return C.mist;
}

function SectorTime({ ms, tone }: { ms?: number | null; tone?: string }) {
  const color = sectorColor(tone);
  return (
    <span style={{ color, fontWeight: tone && tone !== "grey" ? 700 : 500 }}>
      {ms == null ? "—" : (ms / 1000).toFixed(3)}
    </span>
  );
}

function PedalBar({ pct, tone }: { pct?: number | null; tone: "throttle" | "brake" }) {
  const n = pct == null || Number.isNaN(pct) ? null : Math.max(0, Math.min(100, pct));
  const fill =
    n == null
      ? C.faint
      : tone === "brake"
        ? n > 5
          ? C.signal
          : C.caution
        : n > 95
          ? C.green
          : n > 20
            ? C.signal
            : C.caution;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5, minWidth: 48 }}>
      <div style={{ width: 26, height: 6, background: C.ghost, borderRadius: 2, overflow: "hidden" }}>
        <div style={{ width: `${n ?? 0}%`, height: "100%", background: fill }} />
      </div>
      <span style={{ color: n == null ? C.faint : C.paper, fontSize: 10 }}>{n == null ? "—" : Math.round(n)}</span>
    </div>
  );
}

function intervalLabel(row: LiveTimingRow, quali?: boolean) {
  if (quali) return formatMs(row.best_lap_ms);
  if (row.position === 1) return "LEADER";
  if (row.gap_to_ahead_s != null) return `+${row.gap_to_ahead_s.toFixed(3)}`;
  if (row.gap_to_leader_s != null) return `+${row.gap_to_leader_s.toFixed(3)}`;
  return "—";
}

function gapLabel(row: LiveTimingRow) {
  if (row.position === 1) return "—";
  if (row.gap_to_leader_s != null) return `+${row.gap_to_leader_s.toFixed(3)}`;
  return "—";
}

function posDelta(row: LiveTimingRow, gridByCode?: Map<string, number>) {
  const grid = gridByCode?.get(row.driver_code);
  if (grid == null || !row.position) return null;
  return grid - row.position;
}

export function TimingTower({
  rows,
  focus,
  loading,
  quali,
  splitQ,
  onSelect,
  showPedals = false,
  gridByCode,
}: {
  rows: LiveTimingRow[];
  focus?: string;
  loading?: boolean;
  quali?: boolean;
  splitQ?: boolean;
  onSelect?: (code: string) => void;
  showPedals?: boolean;
  gridByCode?: Map<string, number>;
}) {
  if (loading) {
    return (
      <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        {Array.from({ length: 10 }).map((_, i) => (
          <Skeleton key={i} height={18} />
        ))}
      </div>
    );
  }
  const raceDetail = !quali && !splitQ;
  const heads = splitQ
    ? ["P", "DRV", "LAP", "Q1", "Q2", "Q3", "S1", "S2", "S3", ...(showPedals ? ["THR", "BRK"] : [])]
    : raceDetail
      ? ["P", "DRV", "LAP", "LAST", "INT", "GAP", "+/−", "S1", "S2", "S3", ...(showPedals ? ["THR", "BRK"] : []), "TYR"]
      : ["P", "DRV", "LAP", quali ? "BEST" : "GAP", "LAST", "S1", "S2", "S3", ...(showPedals ? ["THR", "BRK"] : []), "TYR"];
  return (
    <div style={{ overflow: "auto", height: "100%" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 11 }}>
        <thead>
          <tr style={{ color: C.faint, fontSize: 9 }}>
            {heads.map((h) => (
              <th
                key={h}
                style={{
                  textAlign: "left",
                  padding: "6px 5px",
                  borderBottom: `1px solid ${C.border}`,
                  fontWeight: 500,
                  position: "sticky",
                  top: 0,
                  background: C.panel,
                  zIndex: 1,
                }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const out = Boolean(row.eliminated);
            const gained = posDelta(row, gridByCode);
            return (
              <tr
                key={row.driver_code}
                onClick={() => onSelect?.(row.driver_code)}
                style={{
                  background: row.driver_code === focus ? C.signalMid : i % 2 ? C.panel2 : "transparent",
                  borderBottom: `1px solid ${C.border}60`,
                  opacity: out ? 0.38 : 1,
                  cursor: onSelect ? "pointer" : "default",
                }}
              >
                <td style={{ padding: "6px 5px", color: C.mist }}>{row.position}</td>
                <td
                  style={{
                    padding: "6px 5px",
                    fontWeight: 700,
                    color: row.fastest_lap ? C.purple : row.driver_code === focus ? C.signal : C.paper,
                  }}
                >
                  {row.driver_code}
                  {row.reason ? (
                    <span style={{ marginLeft: 6, color: C.faint, fontWeight: 500 }}>{row.reason}</span>
                  ) : out ? (
                    <span style={{ marginLeft: 6, color: C.faint, fontWeight: 500 }}>OUT</span>
                  ) : null}
                  {row.fastest_lap ? <span style={{ marginLeft: 6, color: C.purple, fontWeight: 500 }}>FL</span> : null}
                </td>
                <td style={{ padding: "6px 5px", color: C.paper }}>{row.lap_number ?? "—"}</td>
                {splitQ ? (
                  <>
                    <td style={{ padding: "6px 5px", color: C.paper }}>{formatMs(row.q1_ms)}</td>
                    <td style={{ padding: "6px 5px", color: C.paper }}>{formatMs(row.q2_ms)}</td>
                    <td style={{ padding: "6px 5px", color: C.paper }}>{formatMs(row.q3_ms)}</td>
                  </>
                ) : raceDetail ? (
                  <>
                    <td style={{ padding: "6px 5px", color: C.paper }}>{formatMs(row.last_lap_ms)}</td>
                    <td style={{ padding: "6px 5px", color: C.mist, fontSize: 10 }}>{intervalLabel(row)}</td>
                    <td style={{ padding: "6px 5px", color: C.faint, fontSize: 10 }}>{gapLabel(row)}</td>
                    <td
                      style={{
                        padding: "6px 5px",
                        fontWeight: 700,
                        color: gained == null ? C.faint : gained > 0 ? C.green : gained < 0 ? C.caution : C.mist,
                      }}
                    >
                      {gained == null ? "—" : gained > 0 ? `+${gained}` : `${gained}`}
                    </td>
                  </>
                ) : (
                  <>
                    <td style={{ padding: "6px 5px", color: C.mist, fontSize: 10 }}>
                      {quali
                        ? formatMs(row.best_lap_ms)
                        : row.position === 1
                          ? "LEADER"
                          : row.gap_to_leader_s != null
                            ? `+${row.gap_to_leader_s.toFixed(3)}`
                            : "—"}
                    </td>
                    <td style={{ padding: "6px 5px", color: C.paper }}>{formatMs(row.last_lap_ms)}</td>
                  </>
                )}
                <td style={{ padding: "6px 5px" }}>
                  <SectorTime ms={row.sector1_ms} tone={row.s1_colour} />
                </td>
                <td style={{ padding: "6px 5px" }}>
                  <SectorTime ms={row.sector2_ms} tone={row.s2_colour} />
                </td>
                <td style={{ padding: "6px 5px" }}>
                  <SectorTime ms={row.sector3_ms} tone={row.s3_colour} />
                </td>
                {showPedals && (
                  <>
                    <td style={{ padding: "6px 5px" }}>
                      <PedalBar pct={row.throttle_pct} tone="throttle" />
                    </td>
                    <td style={{ padding: "6px 5px" }}>
                      <PedalBar pct={row.brake_pct} tone="brake" />
                    </td>
                  </>
                )}
                {!splitQ && (
                  <td style={{ padding: "6px 5px" }}>
                    <TyreBadge compound={row.compound} life={row.tyre_life} size="sm" />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
