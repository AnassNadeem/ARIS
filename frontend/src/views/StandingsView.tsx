import { useStandings } from "../hooks/useStandings";
import { C, T } from "../theme";
import { EmptyState, Panel, PanelError, Skeleton } from "../components/atoms";
import { Shell } from "../components/Shell";

export function StandingsView({ year }: { year: number }) {
  const { drivers, constructors } = useStandings(year);
  return (
    <Shell title="CHAMPIONSHIP STANDINGS">
      <div style={{ padding: 24, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Panel title="DRIVERS">
          {drivers.status === "loading" && <div style={{ padding: 12 }}>{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} height={18} />)}</div>}
          {drivers.status === "error" && <PanelError message={drivers.error} onRetry={drivers.retry} />}
          {drivers.status === "ok" && drivers.data.standings.length === 0 && (
            <EmptyState title="No standings" body="Jolpica has no driver standings for this year yet." />
          )}
          {drivers.status === "ok" && (
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
              <tbody>
                {drivers.data.standings.map((r) => (
                  <tr key={r.driver_code} style={{ borderBottom: `1px solid ${C.border}40` }}>
                    <td style={{ padding: "8px 12px", color: C.mist }}>{r.position}</td>
                    <td style={{ padding: "8px 12px" }}>
                      <span style={{ display: "inline-block", width: 3, height: 14, background: r.team_colour || C.mist, marginRight: 8 }} />
                      {r.driver_code}
                    </td>
                    <td style={{ padding: "8px 12px", color: C.mist }}>{r.team_name}</td>
                    <td style={{ padding: "8px 12px", color: C.signal }}>{r.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
        <Panel title="CONSTRUCTORS">
          {constructors.status === "loading" && <div style={{ padding: 12 }}>{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} height={18} />)}</div>}
          {constructors.status === "error" && <PanelError message={constructors.error} onRetry={constructors.retry} />}
          {constructors.status === "ok" && constructors.data.standings.length === 0 && (
            <EmptyState title="No constructor standings" body="Jolpica has no constructor table for this year yet." />
          )}
          {constructors.status === "ok" && (
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
              <tbody>
                {constructors.data.standings.map((r) => (
                  <tr key={r.team_name} style={{ borderBottom: `1px solid ${C.border}40` }}>
                    <td style={{ padding: "8px 12px" }}>{r.position}</td>
                    <td style={{ padding: "8px 12px" }}>{r.team_name}</td>
                    <td style={{ padding: "8px 12px", color: C.signal }}>{r.points}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>
    </Shell>
  );
}
