import { useState } from "react";
import { useCalendar } from "../hooks/useCalendar";
import { useStandings } from "../hooks/useStandings";
import { C, T } from "../theme";
import { EmptyState, ErrorPanel, Panel, SkeletonPanel, TabBar } from "../components/atoms";
import { Shell } from "../components/Shell";

export function StandingsView() {
  const [year, setYear] = useState(2026);
  const [tab, setTab] = useState("drivers");
  const { drivers, constructors } = useStandings(year);
  const cal = useCalendar(year);
  const completed = cal.status === "ok" ? cal.data.rounds.filter((r) => r.status === "COMPLETED").length : 0;
  const total = cal.status === "ok" ? cal.data.rounds.length : 24;

  return (
    <Shell title="CHAMPIONSHIP STANDINGS">
      <div style={{ padding: 24 }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {[2024, 2025, 2026].map((y) => (
            <button
              key={y}
              onClick={() => setYear(y)}
              style={{
                padding: "6px 14px",
                cursor: "pointer",
                background: year === y ? C.signalMid : "transparent",
                border: `1px solid ${year === y ? C.signal : C.border}`,
                color: year === y ? C.signal : C.mist,
                fontFamily: T.mono,
                fontSize: 12,
              }}
            >
              {y}
              {y === 2026 ? " ▶ LIVE" : ""}
            </button>
          ))}
        </div>
        {year === 2026 && (
          <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal, marginBottom: 12 }}>
            SEASON IN PROGRESS — ROUND {completed} OF {total || 24}
          </div>
        )}
        <TabBar tabs={[["drivers", "DRIVERS"], ["constructors", "CONSTRUCTORS"]]} active={tab} onChange={setTab} />
        {tab === "drivers" && (
          <Panel title="DRIVERS" style={{ marginTop: 12 }}>
            {drivers.status === "loading" && (
              <SkeletonPanel rows={10} label="Loading driver standings — this may take a moment on first load as data is being cached..." />
            )}
            {drivers.status === "error" && (
              <ErrorPanel message={`Could not load driver standings. ${drivers.error}`} onRetry={drivers.retry} />
            )}
            {drivers.status === "ok" && drivers.data.standings.length === 0 && (
              <EmptyState title="No standings" body="Jolpica has no driver standings for this year yet." />
            )}
            {drivers.status === "ok" && (
              <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
                <thead>
                  <tr style={{ color: C.faint, fontSize: 9 }}>
                    {["POS", "DRIVER", "TEAM", "POINTS", "WINS", "PODIUMS", "FASTEST LAPS", "DNFs", "GAP TO LEADER"].map((h) => (
                      <th key={h} style={{ textAlign: "left", padding: "8px 10px" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {drivers.data.standings.map((r) => (
                    <tr key={r.driver_code} style={{ borderBottom: `1px solid ${C.border}40` }}>
                      <td style={{ padding: "8px 10px" }}>{r.position}</td>
                      <td style={{ padding: "8px 10px" }}>
                        <span style={{ display: "inline-block", width: 3, height: 14, background: r.team_colour || C.mist, marginRight: 8 }} />
                        {r.full_name} ({r.driver_code})
                      </td>
                      <td style={{ padding: "8px 10px", color: C.mist }}>{r.team_name}</td>
                      <td style={{ padding: "8px 10px", color: C.signal }}>{r.points}</td>
                      <td style={{ padding: "8px 10px" }}>{r.wins}</td>
                      <td style={{ padding: "8px 10px" }}>{r.podiums ?? 0}</td>
                      <td style={{ padding: "8px 10px" }}>{r.fastest_laps ?? 0}</td>
                      <td style={{ padding: "8px 10px" }}>{r.dnfs ?? 0}</td>
                      <td style={{ padding: "8px 10px" }}>{r.gap_to_leader}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        )}
        {tab === "constructors" && (
          <Panel title="CONSTRUCTORS" style={{ marginTop: 12 }}>
            {constructors.status === "loading" && (
              <SkeletonPanel rows={8} label="Loading constructor standings — this may take a moment on first load as data is being cached..." />
            )}
            {constructors.status === "error" && (
              <ErrorPanel message={`Could not load constructor standings. ${constructors.error}`} onRetry={constructors.retry} />
            )}
            {constructors.status === "ok" && constructors.data.standings.length === 0 && (
              <EmptyState title="No constructor standings" body="Jolpica has no constructor table for this year yet." />
            )}
            {constructors.status === "ok" && (
              <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
                <thead>
                  <tr style={{ color: C.faint, fontSize: 9 }}>
                    {["POS", "TEAM", "POINTS", "WINS", "PODIUMS", "DRIVERS"].map((h) => (
                      <th key={h} style={{ textAlign: "left", padding: "8px 10px" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {constructors.data.standings.map((r) => {
                    const teamDrivers =
                      r.drivers?.join(" / ") ||
                      (drivers.status === "ok"
                        ? drivers.data.standings.filter((d) => d.team_name === r.team_name).map((d) => d.driver_code).join(" / ")
                        : "—");
                    return (
                      <tr key={r.team_name} style={{ borderBottom: `1px solid ${C.border}40` }}>
                        <td style={{ padding: "8px 10px" }}>{r.position}</td>
                        <td style={{ padding: "8px 10px" }}>{r.team_name}</td>
                        <td style={{ padding: "8px 10px", color: C.signal }}>{r.points}</td>
                        <td style={{ padding: "8px 10px" }}>{r.wins}</td>
                        <td style={{ padding: "8px 10px" }}>{r.podiums ?? 0}</td>
                        <td style={{ padding: "8px 10px", color: C.mist }}>{teamDrivers}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </Panel>
        )}
      </div>
    </Shell>
  );
}
