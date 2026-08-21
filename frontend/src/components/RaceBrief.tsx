import { useCircuit } from "../hooks/useCircuit";
import { C, T } from "../theme";
import { EmptyState, ErrorPanel, Panel, SkeletonPanel, Stat } from "./atoms";

export function RaceBrief({
  circuitKey,
  year,
  circuitName,
  driver,
}: {
  circuitKey: string;
  year: number;
  circuitName?: string;
  driver?: string;
}) {
  const circuit = useCircuit(circuitKey, year);
  const years = circuit.history.status === "ok" ? circuit.history.data.years : [];
  const meta = circuit.history.status === "ok" ? circuit.history.data : null;
  const last = [...years].sort((a, b) => b.year - a.year)[0];
  const priorSeason = years.filter((y) => y.year < year).sort((a, b) => b.year - a.year)[0];
  const chars = circuit.chars.status === "ok" ? circuit.chars.data : null;

  return (
    <div>
      <div style={{ fontFamily: T.display, fontSize: 28, fontWeight: 900, marginBottom: 6 }}>
        {(chars?.name || circuitName || circuitKey).toUpperCase()}
      </div>
      <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, marginBottom: 16 }}>
        Track analysis · historical results from {meta?.from_year ?? 2018} · used for ARIS strategy
        {driver ? ` · ${driver}` : ""}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 14 }}>
        <Panel title="TRACK ANALYSIS">
          {circuit.chars.status === "loading" && <SkeletonPanel rows={6} label="Loading circuit…" />}
          {circuit.chars.status === "error" && (
            <ErrorPanel message={circuit.chars.error} onRetry={circuit.chars.retry} />
          )}
          {chars && (
            <div style={{ padding: 12 }}>
              {[
                ["Length", chars.lap_length_km ? `${chars.lap_length_km} km` : "—"],
                ["Turns", chars.turns != null ? String(chars.turns) : "—"],
                ["Race laps", chars.total_laps != null ? String(chars.total_laps) : "—"],
                ["Pit loss", chars.pit_loss_seconds != null ? `~${chars.pit_loss_seconds}s` : "—"],
                ["DRS", chars.drs_zones != null ? String(chars.drs_zones) : "—"],
                ["Tyre stress", chars.tyre_stress_rating ?? "—"],
                ["Track evo", chars.track_evolution_rating ?? "—"],
              ].map(([k, v]) => (
                <div
                  key={k}
                  style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: `1px solid ${C.border}40` }}
                >
                  <span style={{ fontFamily: T.body, fontSize: 12, color: C.mist }}>{k}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 12 }}>{v}</span>
                </div>
              ))}
              {chars.sector_descriptions.slice(0, 3).map((s) => (
                <div key={s} style={{ fontFamily: T.body, fontSize: 11, color: C.mist, marginTop: 8 }}>
                  {s}
                </div>
              ))}
            </div>
          )}
        </Panel>
        <Panel title="PAST SEASON">
          {!priorSeason && circuit.history.status === "ok" && (
            <EmptyState title="No prior season here" body="This venue may be new on the calendar since 2018." />
          )}
          {circuit.history.status === "loading" && <SkeletonPanel rows={5} label="Loading past seasons…" />}
          {priorSeason && (
            <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
              <Stat label={`${priorSeason.year} winner`} value={priorSeason.winner ?? "—"} sub={priorSeason.winner_team ?? undefined} />
              <Stat label="Pole" value={priorSeason.pole ?? "—"} />
              <Stat label="Fastest lap" value={priorSeason.fastest_lap ?? "—"} />
              {priorSeason.winner_grid != null && <Stat label="Winner started" value={`P${priorSeason.winner_grid}`} />}
              {priorSeason.weather && <Stat label="Weather" value={priorSeason.weather} />}
              {last && last.year !== priorSeason.year && (
                <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint }}>
                  Latest on file: {last.year} · {last.winner ?? "—"}
                </div>
              )}
            </div>
          )}
        </Panel>
        <Panel title="HISTORICAL STRATEGY">
          {circuit.history.status === "loading" && <SkeletonPanel rows={5} label="Loading 2018–present…" />}
          {meta && (
            <div style={{ padding: 12 }}>
              <Stat label="Races in sample" value={String(years.length)} sub={`from ${meta.from_year ?? 2018}`} />
              <Stat label="Most common winner" value={meta.most_common_winner ?? "—"} />
              <Stat
                label="Typical stops"
                value={meta.typical_stop_count != null ? String(meta.typical_stop_count) : "—"}
              />
              <Stat
                label="Median first stop"
                value={meta.median_first_stop_lap != null ? `lap ${meta.median_first_stop_lap}` : "—"}
              />
              {meta.analysis && (
                <p style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginTop: 10, lineHeight: 1.6 }}>
                  {meta.analysis}
                </p>
              )}
            </div>
          )}
        </Panel>
      </div>
      <Panel title={`RACE HISTORY · ${meta?.from_year ?? 2018}–PRESENT`}>
        {circuit.history.status === "loading" && <SkeletonPanel rows={8} label="Loading historical results…" />}
        {circuit.history.status === "error" && (
          <ErrorPanel message={circuit.history.error} onRetry={circuit.history.retry} />
        )}
        {circuit.history.status === "ok" && years.length === 0 && (
          <EmptyState title="No history yet" body="Jolpica returned no races at this circuit from 2018 onward." />
        )}
        {years.length > 0 && (
          <div style={{ overflow: "auto", maxHeight: 280 }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
              <thead>
                <tr style={{ color: C.faint, fontSize: 9 }}>
                  {["Year", "Race", "Winner", "Team", "Pole", "FL", "Grid", "Weather"].map((h) => (
                    <th key={h} style={{ textAlign: "left", padding: "8px 10px" }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...years].sort((a, b) => b.year - a.year).map((h) => (
                  <tr key={`${h.year}-${h.race_name || ""}`} style={{ borderBottom: `1px solid ${C.border}40` }}>
                    <td style={{ padding: "8px 10px" }}>{h.year}</td>
                    <td style={{ padding: "8px 10px", color: C.mist }}>{h.race_name ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.winner ?? "—"}</td>
                    <td style={{ padding: "8px 10px", color: C.mist }}>{h.winner_team ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.pole ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.fastest_lap ?? "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.winner_grid != null ? `P${h.winner_grid}` : "—"}</td>
                    <td style={{ padding: "8px 10px" }}>{h.weather ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      {chars?.aris_notes && (
        <Panel title="ARIS CIRCUIT NOTES" style={{ marginTop: 12 }}>
          <div style={{ padding: 14, fontFamily: T.body, fontSize: 13, color: C.mist, lineHeight: 1.7 }}>
            <p>{chars.aris_notes.undercut_effectiveness}</p>
            <p style={{ marginTop: 8 }}>{chars.aris_notes.tyre_compound_tendencies}</p>
            <p style={{ marginTop: 8 }}>{chars.aris_notes.overtaking_difficulty}</p>
            <p style={{ marginTop: 8 }}>{chars.aris_notes.sc_probability_history}</p>
            {chars.aris_notes.summary && (
              <p style={{ marginTop: 8, color: C.paper }}>{chars.aris_notes.summary}</p>
            )}
          </div>
        </Panel>
      )}
    </div>
  );
}
