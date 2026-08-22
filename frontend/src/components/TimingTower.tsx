import type { LiveTimingRow } from "../api/types";
import { C, T } from "../theme";
import { SectorDot, Skeleton, TyreBadge, formatMs } from "./atoms";

export function TimingTower({
  rows,
  focus,
  loading,
  quali,
  splitQ,
  onSelect,
}: {
  rows: LiveTimingRow[];
  focus?: string;
  loading?: boolean;
  quali?: boolean;
  splitQ?: boolean;
  onSelect?: (code: string) => void;
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
  const heads = splitQ
    ? ["P", "DRV", "Q1", "Q2", "Q3", "S1", "S2", "S3"]
    : ["P", "DRV", quali ? "BEST" : "GAP", quali ? "LAST" : "LAST", "S1", "S2", "S3", "TYR"];
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
                  padding: "6px 8px",
                  borderBottom: `1px solid ${C.border}`,
                  fontWeight: 500,
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
              <td style={{ padding: "6px 8px", color: C.mist }}>{row.position}</td>
              <td
                style={{
                  padding: "6px 8px",
                  fontWeight: 700,
                  color: row.fastest_lap ? C.purple : row.driver_code === focus ? C.signal : C.paper,
                }}
              >
                {row.driver_code}
                {row.reason ? <span style={{ marginLeft: 6, color: C.faint, fontWeight: 500 }}>{row.reason}</span> : out ? <span style={{ marginLeft: 6, color: C.faint, fontWeight: 500 }}>OUT</span> : null}
                {row.fastest_lap ? <span style={{ marginLeft: 6, color: C.purple, fontWeight: 500 }}>FL</span> : null}
              </td>
              {splitQ ? (
                <>
                  <td style={{ padding: "6px 8px", color: C.paper }}>{formatMs(row.q1_ms)}</td>
                  <td style={{ padding: "6px 8px", color: C.paper }}>{formatMs(row.q2_ms)}</td>
                  <td style={{ padding: "6px 8px", color: C.paper }}>{formatMs(row.q3_ms)}</td>
                </>
              ) : (
                <>
                  <td style={{ padding: "6px 8px", color: C.mist, fontSize: 10 }}>
                    {quali
                      ? formatMs(row.best_lap_ms)
                      : row.position === 1
                        ? "LEADER"
                        : row.gap_to_leader_s != null
                          ? `+${row.gap_to_leader_s.toFixed(3)}`
                          : "—"}
                  </td>
                  <td style={{ padding: "6px 8px", color: C.paper }}>{formatMs(row.last_lap_ms)}</td>
                </>
              )}
              <td style={{ padding: "6px 8px" }}>
                <SectorDot tone={row.s1_colour} />
              </td>
              <td style={{ padding: "6px 8px" }}>
                <SectorDot tone={row.s2_colour} />
              </td>
              <td style={{ padding: "6px 8px" }}>
                <SectorDot tone={row.s3_colour} />
              </td>
              {!splitQ && (
                <td style={{ padding: "6px 8px" }}>
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
