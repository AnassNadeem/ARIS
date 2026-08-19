import type { LiveTimingRow } from "../api/types";
import { C, T } from "../theme";
import { SectorDot, Skeleton, TyreBadge, formatMs } from "./atoms";

export function TimingTower({
  rows,
  focus,
  loading,
}: {
  rows: LiveTimingRow[];
  focus?: string;
  loading?: boolean;
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
  return (
    <div style={{ overflow: "auto", height: "100%" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 11 }}>
        <thead>
          <tr style={{ color: C.faint, fontSize: 9 }}>
            {["P", "DRV", "GAP", "LAST", "S1", "S2", "S3", "TYR"].map((h) => (
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
          {rows.map((row, i) => (
            <tr
              key={row.driver_code}
              style={{
                background: row.driver_code === focus ? C.signalMid : i % 2 ? C.panel2 : "transparent",
                borderBottom: `1px solid ${C.border}60`,
              }}
            >
              <td style={{ padding: "6px 8px", color: C.mist }}>{row.position}</td>
              <td
                style={{
                  padding: "6px 8px",
                  fontWeight: 700,
                  color: row.driver_code === focus ? C.signal : C.paper,
                }}
              >
                {row.driver_code}
              </td>
              <td style={{ padding: "6px 8px", color: C.mist, fontSize: 10 }}>
                {row.position === 1 ? "LEADER" : row.gap_to_leader_s != null ? `+${row.gap_to_leader_s.toFixed(3)}` : "—"}
              </td>
              <td style={{ padding: "6px 8px", color: C.paper }}>{formatMs(row.last_lap_ms)}</td>
              <td style={{ padding: "6px 8px" }}>
                <SectorDot tone={row.s1_colour} />
              </td>
              <td style={{ padding: "6px 8px" }}>
                <SectorDot tone={row.s2_colour} />
              </td>
              <td style={{ padding: "6px 8px" }}>
                <SectorDot tone={row.s3_colour} />
              </td>
              <td style={{ padding: "6px 8px" }}>
                <TyreBadge compound={row.compound} life={row.tyre_life} size="sm" />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
