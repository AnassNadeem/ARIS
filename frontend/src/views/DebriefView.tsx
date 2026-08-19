import { apiGet } from "../api/client";
import type { SessionConfig } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { C, T } from "../theme";
import { Chip, EmptyState, Panel, PanelError, Skeleton } from "../components/atoms";
import { Shell } from "../components/Shell";

type Debrief = {
  actual_position: number | null;
  aris_projected_position: number | null;
  actual_pits: number[];
  summary: string;
  podium: { position: number | null; driver_code: string; team: string | null }[];
  decisions: { lap: number; aris_call: string; actual_call: string; outcome: string; net_delta_s: number | null }[];
};

export function DebriefView({
  config,
  onRestart,
  onBack,
}: {
  config: SessionConfig;
  onRestart: () => void;
  onBack: () => void;
}) {
  const data = useAsync(
    () =>
      apiGet<Debrief>(
        `/api/aris/debrief?year=${config.year}&round_number=${config.round.round_number}&driver_code=${config.driver}`,
        { timeout: 60_000 },
      ),
    [config.year, config.round.round_number, config.driver],
  );

  return (
    <Shell title="POST-RACE DEBRIEF" config={config}>
      <div style={{ maxWidth: 1080, margin: "0 auto", padding: "28px 24px" }}>
        {data.status === "loading" && <Skeleton height={200} />}
        {data.status === "error" && <PanelError message={data.error} onRetry={data.retry} />}
        {data.status === "ok" && (
          <>
            <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 24 }}>
              <div style={{ fontFamily: T.display, fontSize: 60, fontWeight: 900, color: C.signal, lineHeight: 1 }}>
                {data.data.actual_position != null ? `P${data.data.actual_position}` : "—"}
              </div>
              <div>
                <div style={{ fontFamily: T.display, fontSize: 20, fontWeight: 700 }}>{config.driver}</div>
                <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist }}>
                  {config.round.name} {config.year}
                </div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
              {data.data.podium.map((p) => (
                <Chip key={p.driver_code} tone={p.position === 1 ? "signal" : "mist"}>
                  P{p.position} {p.driver_code}
                </Chip>
              ))}
            </div>
            <Panel title="DECISION LOG — ARIS vs ACTUAL" style={{ marginBottom: 16 }}>
              {data.data.decisions.length === 0 && (
                <EmptyState title="No decision records" body="Ingest this session to compare ARIS calls to the team." />
              )}
              <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 11 }}>
                <thead>
                  <tr style={{ color: C.faint, fontSize: 9 }}>
                    {["LAP", "ARIS CALL", "ACTUAL CALL", "OUTCOME", "NET"].map((h) => (
                      <th key={h} style={{ textAlign: "left", padding: "8px 12px" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.data.decisions.map((d, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${C.border}40` }}>
                      <td style={{ padding: "8px 12px" }}>L{d.lap}</td>
                      <td style={{ padding: "8px 12px", color: C.signal }}>{d.aris_call}</td>
                      <td style={{ padding: "8px 12px" }}>{d.actual_call}</td>
                      <td style={{ padding: "8px 12px", color: C.mist, fontSize: 10 }}>{d.outcome}</td>
                      <td style={{ padding: "8px 12px", color: (d.net_delta_s ?? 0) < 0 ? C.green : C.caution }}>
                        {d.net_delta_s != null ? d.net_delta_s.toFixed(2) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Panel>
            <p style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginBottom: 16 }}>{data.data.summary}</p>
          </>
        )}
        <div style={{ display: "flex", gap: 12 }}>
          <button onClick={onRestart} style={{ padding: "12px 24px", background: C.signal, border: "none", color: C.ink, fontFamily: T.display, fontWeight: 800, cursor: "pointer", borderRadius: 4 }}>
            NEW SESSION →
          </button>
          <button onClick={onBack} style={{ padding: "12px 24px", background: "transparent", border: `1px solid ${C.border}`, color: C.mist, fontFamily: T.mono, fontSize: 11, cursor: "pointer" }}>
            ← BACK TO CONSOLE
          </button>
        </div>
      </div>
    </Shell>
  );
}
