import { useStandings } from "../hooks/useStandings";
import { C, T } from "../theme";
import { EmptyState, Panel, PanelError, Skeleton, Stat } from "../components/atoms";
import { Shell } from "../components/Shell";

export function AnalyticsView({ year }: { year: number }) {
  const { drivers, constructors } = useStandings(year);
  const leader = drivers.status === "ok" ? drivers.data.standings[0] : null;
  const max = leader?.points || 1;
  return (
    <Shell title="SEASON ANALYTICS">
      <div style={{ padding: 24, maxWidth: 1000, margin: "0 auto" }}>
        {drivers.status === "loading" && <Skeleton height={80} />}
        {drivers.status === "error" && <PanelError message={drivers.error} onRetry={drivers.retry} />}
        {leader && <Stat label="Leader" value={`${leader.driver_code} · ${leader.points} pts`} sub={`${leader.wins} wins`} accent={C.signal} />}
        {drivers.status === "ok" && drivers.data.standings.length === 0 && (
          <EmptyState title="No analytics yet" body="Standings feed is empty for this year." />
        )}
        <Panel title="POINTS" style={{ marginTop: 16 }}>
          <div style={{ padding: 14 }}>
            {(drivers.status === "ok" ? drivers.data.standings.slice(0, 10) : []).map((r) => (
              <div key={r.driver_code} style={{ marginBottom: 8 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontFamily: T.mono, fontSize: 10 }}>
                  <span>{r.driver_code}</span>
                  <span style={{ color: r.team_colour || C.signal }}>{r.points}</span>
                </div>
                <div style={{ height: 6, background: C.ghost, borderRadius: 3 }}>
                  <div style={{ width: `${(r.points / max) * 100}%`, height: "100%", background: r.team_colour || C.signal, borderRadius: 3 }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="CONSTRUCTORS" style={{ marginTop: 12 }}>
          <div style={{ padding: 14, fontFamily: T.mono, fontSize: 12 }}>
            {constructors.status === "ok" &&
              constructors.data.standings.slice(0, 5).map((r) => (
                <div key={r.team_name} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                  <span>{r.team_name}</span>
                  <span style={{ color: C.signal }}>{r.points}</span>
                </div>
              ))}
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
