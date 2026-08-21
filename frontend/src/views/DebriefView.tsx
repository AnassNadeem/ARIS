import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, CartesianGrid } from "recharts";
import { apiGet, peekGet } from "../api/client";
import type { SessionConfig } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { C, T } from "../theme";
import { Chip, EmptyState, ErrorPanel, Panel, ReasoningBar, SkeletonPanel, Stat, formatMs } from "../components/atoms";
import { Shell } from "../components/Shell";

type Debrief = {
  actual_position: number | null;
  aris_projected_position: number | null;
  optimal_position?: number | null;
  actual_pits: number[];
  summary: string;
  podium: { position: number | null; driver_code: string; team: string | null }[];
  decisions: {
    lap: number;
    aris_call: string;
    actual_call: string;
    outcome: string;
    net_delta_s: number | null;
    reasoning?: string | null;
    user_override?: string | null;
    pace_gain_s?: number | null;
    pit_cost_s?: number | null;
  }[];
  aris_strategy?: { label: string; position: number | null; plan_name: string | null; pits: { lap: number; compound: string }[] };
  actual_strategy?: { label: string; position: number | null; plan_name: string | null; pits: { lap: number; compound: string }[] };
  optimal_strategy?: { label: string; position: number | null; plan_name: string | null; pits: { lap: number; compound: string }[] };
  stats?: {
    laps_led: number;
    pit_time_s: number | null;
    compounds_used: string[];
    positions_gained: number | null;
    fastest_lap_ms: number | null;
    field_fastest_lap_ms: number | null;
    deg_rate_ms: number | null;
    field_deg_rate_ms: number | null;
    aris_correct: number;
    aris_total: number;
    sc_events: number;
    sc_handled: number;
  };
  delta_series?: { lap: number; aris_vs_actual_s: number; optimal_vs_actual_s: number }[];
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
  const path = `/api/aris/debrief?year=${config.year}&round_number=${config.round.round_number}&driver_code=${config.driver}`;
  const data = useAsync(
    () => apiGet<Debrief>(path, { timeout: 60_000 }),
    [config.year, config.round.round_number, config.driver],
    true,
    () => peekGet<Debrief>(path),
  );

  return (
    <Shell title="POST-RACE DEBRIEF" config={config}>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px" }}>
        {data.status === "loading" && (
          <SkeletonPanel rows={8} label="Loading debrief — this may take a moment on first load as data is being cached..." />
        )}
        {data.status === "error" && (
          <ErrorPanel message={`Could not load debrief. ${data.error}`} onRetry={data.retry} />
        )}
        {data.status === "ok" && (
          <DebriefBody d={data.data} driver={config.driver} />
        )}
        <div style={{ display: "flex", gap: 12, marginTop: 16 }}>
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

function Col({ s }: { s?: Debrief["aris_strategy"] }) {
  if (!s) return null;
  return (
    <div style={{ padding: 14, background: C.panel, border: `1px solid ${C.border}`, borderRadius: 4 }}>
      <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint }}>{s.label}</div>
      <div style={{ fontFamily: T.display, fontSize: 42, fontWeight: 900, color: C.signal }}>
        {s.position != null ? `P${s.position}` : "—"}
      </div>
      <div style={{ fontFamily: T.body, fontSize: 12, color: C.mist }}>{s.plan_name}</div>
      <div style={{ fontFamily: T.mono, fontSize: 11, marginTop: 8 }}>
        {s.pits.map((p) => `${p.lap} → ${p.compound}`).join(" · ") || "no stop"}
      </div>
    </div>
  );
}

function DebriefBody({ d, driver }: { d: Debrief; driver: string }) {
  const stats = d.stats;
  const classified = d.actual_position ?? d.actual_strategy?.position ?? null;
  return (
    <>
      <div style={{ marginBottom: 16, padding: "14px 16px", background: C.panel, border: `1px solid ${C.signal}55`, borderRadius: 4 }}>
        <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, letterSpacing: "0.1em" }}>CLASSIFIED FINISH · {driver}</div>
        <div style={{ fontFamily: T.display, fontSize: 48, fontWeight: 900, color: C.signal, lineHeight: 1 }}>
          {classified != null ? `P${classified}` : "—"}
        </div>
        <p style={{ fontFamily: T.body, fontSize: 13, color: C.mist, marginTop: 8 }}>{d.summary}</p>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 16 }}>
        <Col s={d.aris_strategy} />
        <Col s={d.actual_strategy} />
        <Col s={d.optimal_strategy} />
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        {d.podium.map((p) => (
          <Chip key={p.driver_code} tone={p.position === 1 ? "signal" : "mist"}>
            P{p.position} {p.driver_code}
          </Chip>
        ))}
      </div>
      {d.decisions.map((dec, i) => (
        <Panel key={i} title={`LAP ${dec.lap} — ${dec.aris_call}`} style={{ marginBottom: 10 }}>
          <div style={{ padding: 12 }}>
            <div style={{ fontFamily: T.body, fontSize: 12, color: C.paper }}>ARIS reasoning: {dec.reasoning || dec.outcome}</div>
            <div style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginTop: 6 }}>What actually happened: {dec.actual_call}</div>
            <div style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginTop: 4 }}>{dec.outcome}</div>
            <div style={{ fontFamily: T.mono, fontSize: 11, color: (dec.net_delta_s ?? 0) <= 0 ? C.green : C.caution, marginTop: 6 }}>
              ARIS vs actual delta: {dec.net_delta_s != null ? `${dec.net_delta_s.toFixed(1)}s` : "—"}
            </div>
            {dec.user_override && (
              <div style={{ fontFamily: T.mono, fontSize: 11, color: C.caution, marginTop: 6 }}>USER OVERRIDE: {dec.user_override}</div>
            )}
            {dec.pace_gain_s != null && dec.pit_cost_s != null && (
              <ReasoningBar paceGain={dec.pace_gain_s} pitCost={dec.pit_cost_s} label />
            )}
          </div>
        </Panel>
      ))}
      {d.decisions.length === 0 && <EmptyState title="No decision records" body="Ingest this session to compare ARIS calls to the team." />}
      {stats && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, margin: "16px 0" }}>
          <Stat label="Laps led" value={String(stats.laps_led)} />
          <Stat label="Time in pits" value={stats.pit_time_s != null ? `${stats.pit_time_s.toFixed(1)}s` : "—"} />
          <Stat label="Compounds" value={stats.compounds_used.join(" ") || "—"} />
          <Stat label="Pos gained" value={stats.positions_gained != null ? String(stats.positions_gained) : "—"} />
          <Stat label="Fastest lap" value={formatMs(stats.fastest_lap_ms)} sub={stats.field_fastest_lap_ms ? `field ${formatMs(stats.field_fastest_lap_ms)}` : undefined} />
          <Stat label="Deg vs field" value={stats.deg_rate_ms != null ? `${stats.deg_rate_ms.toFixed(1)} ms` : "—"} sub={stats.field_deg_rate_ms != null ? `field ${stats.field_deg_rate_ms.toFixed(1)}` : undefined} />
          <Stat label="ARIS decisions" value={`${stats.aris_correct} / ${stats.aris_total}`} />
          <Stat label="SC events" value={`${stats.sc_handled} / ${stats.sc_events}`} />
        </div>
      )}
      {d.delta_series && d.delta_series.length > 0 && (
        <Panel title="CUMULATIVE DELTA vs ACTUAL">
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={d.delta_series}>
              <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
              <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
              <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
              <Line dataKey="aris_vs_actual_s" stroke={C.signal} dot={false} name="ARIS" isAnimationActive={false} />
              <Line dataKey="optimal_vs_actual_s" stroke={C.green} dot={false} name="Optimal" isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      )}
      <span style={{ display: "none" }}>{driver}</span>
    </>
  );
}

