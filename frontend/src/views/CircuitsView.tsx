import { useState } from "react";
import { useCalendar } from "../hooks/useCalendar";
import { useCircuit } from "../hooks/useCircuit";
import { C, T } from "../theme";
import { Chip, EmptyState, Panel, PanelError, Skeleton } from "../components/atoms";
import { Shell } from "../components/Shell";

export function CircuitsView({ year }: { year: number }) {
  const cal = useCalendar(year);
  const [key, setKey] = useState<string | null>(null);
  const circuit = useCircuit(key ?? undefined, year);
  const unique = cal.status === "ok"
    ? [...new Map(cal.data.rounds.map((r) => [r.circuit_key, r])).values()]
    : [];

  return (
    <Shell title="CIRCUITS">
      <div style={{ display: "grid", gridTemplateColumns: "280px 1fr", minHeight: "100%" }}>
        <div style={{ borderRight: `1px solid ${C.border}`, overflow: "auto", padding: 12 }}>
          {cal.status === "loading" && Array.from({ length: 12 }).map((_, i) => <Skeleton key={i} height={28} />)}
          {cal.status === "error" && <PanelError message={cal.error} onRetry={cal.retry} />}
          {unique.map((r) => (
            <button
              key={r.circuit_key}
              onClick={() => setKey(r.circuit_key)}
              style={{
                display: "block",
                width: "100%",
                textAlign: "left",
                padding: "8px 10px",
                background: key === r.circuit_key ? C.signalMid : "transparent",
                border: "none",
                color: key === r.circuit_key ? C.signal : C.paper,
                fontFamily: T.body,
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              {r.name}
              <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint }}>{r.circuit_name}</div>
            </button>
          ))}
        </div>
        <div style={{ padding: 16 }}>
          {!key && <EmptyState title="Select a circuit" body="History and characteristics load from FastF1 + track YAML." />}
          {key && circuit.chars.status === "loading" && <Skeleton height={160} />}
          {key && circuit.chars.status === "error" && <PanelError message={circuit.chars.error} onRetry={circuit.chars.retry} />}
          {key && circuit.chars.status === "ok" && (
            <Panel title={circuit.chars.data.name}>
              <div style={{ padding: 14 }}>
                {circuit.chars.data.estimated && <Chip tone="signal">ESTIMATED</Chip>}
                <div style={{ marginTop: 8, fontFamily: T.mono, fontSize: 12, color: C.mist }}>
                  {circuit.chars.data.lap_length_km ?? "—"} km · {circuit.chars.data.turns ?? "—"} turns · pit {circuit.chars.data.pit_loss_seconds ?? "—"}s
                </div>
              </div>
            </Panel>
          )}
          {key && circuit.history.status === "ok" && (
            <Panel title="HISTORY" style={{ marginTop: 12 }}>
              <div style={{ padding: 14 }}>
                {circuit.history.data.map((h) => (
                  <div key={h.year} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontFamily: T.mono, fontSize: 12 }}>
                    <span>{h.year}</span>
                    <span>{h.winner ?? "—"} · pole {h.pole ?? "—"}</span>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      </div>
    </Shell>
  );
}
