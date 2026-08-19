import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet, apiPost } from "../api/client";
import type { ChatResponse, LapsResponse, LiveTimingRow, RecommendResponse, SessionConfig } from "../api/types";
import { useARISRecommend } from "../hooks/useARISRecommend";
import { useCircuit } from "../hooks/useCircuit";
import { useLiveTiming } from "../hooks/useLiveTiming";
import { useReplayTiming, useSessionLaps } from "../hooks/useSession";
import { useStandings } from "../hooks/useStandings";
import { C, SPEED_OPTIONS, T, compoundLetter } from "../theme";
import { Chip, EmptyState, LiveDot, Panel, PanelError, ReasoningBar, Skeleton, Stat, TabBar, TyreBadge, formatMs } from "../components/atoms";
import { TimingTower } from "../components/TimingTower";
import { TrackMap } from "../components/TrackMap";

const CHART_COLORS = [C.blue, C.signal, C.green, C.caution, C.purple, "#FF8000"];

type Msg = { id: number; type: string; text: string };

export function ConsoleView({ config, onDebrief }: { config: SessionConfig; onDebrief: () => void }) {
  const isLive = config.mode === "live";
  const [mainTab, setMainTab] = useState("race");
  const [analyticsTab, setAnalyticsTab] = useState("driver");
  const [simTab, setSimTab] = useState("h2h");
  const [speed, setSpeed] = useState<(typeof SPEED_OPTIONS)[number]>("1×");
  const [running, setRunning] = useState(false);
  const [lap, setLap] = useState(1);
  const [hiddenCars, setHiddenCars] = useState<string[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [pitDecision, setPitDecision] = useState<string | null>(null);
  const [whatIf, setWhatIf] = useState({ pitLap: 22, sc: 0, rain: 0, deg: 1 });
  const [simResult, setSimResult] = useState<string | null>(null);

  const live = useLiveTiming(isLive);
  const replay = useReplayTiming(config.year, config.round.round_number, "R", lap, !isLive);
  const laps = useSessionLaps(config.year, config.round.round_number, "R", !isLive);
  const rec = useARISRecommend(config.year, config.round.round_number, config.driver, lap, !isLive);
  const standings = useStandings(config.year);
  const circuit = useCircuit(config.round.circuit_key, config.year);

  const totalLaps = circuit.chars.status === "ok" ? circuit.chars.data.total_laps ?? 60 : 60;
  const rows: LiveTimingRow[] = isLive ? live.timing?.rows ?? [] : replay.status === "ok" ? replay.data.rows : [];
  const focusStint = rows.find((r) => r.driver_code === config.driver);

  const [chartLap, setChartLap] = useState(1);
  useEffect(() => {
    const delay = lap <= 1 ? 0 : 2000;
    const id = window.setTimeout(() => setChartLap(lap), delay);
    return () => window.clearTimeout(id);
  }, [lap]);

  const speedMs: Record<string, number> = {
    "1×": 90000,
    "2×": 45000,
    "5×": 18000,
    "10×": 9000,
    "25×": 5000,
    "50×": 3000,
  };

  useEffect(() => {
    if (isLive || !running) return;
    const id = window.setInterval(() => {
      setLap((n) => Math.min(totalLaps, n + 1));
    }, speedMs[speed] ?? 90000);
    return () => window.clearInterval(id);
  }, [running, speed, isLive, totalLaps]);

  useEffect(() => {
    if (rec.status !== "ok") return;
    const r = rec.data;
    setMessages((m) => {
      if (m.some((x) => x.text.includes(r.decision_record_id))) return m;
      const next: Msg[] = [
        ...m,
        { id: m.length + 1, type: "recommend", text: `${r.action}: ${r.reasoning} [${r.decision_record_id}]` },
      ];
      if (r.wet_reduced_confidence) {
        next.push({ id: next.length + 1, type: "alert", text: "[WET: REDUCED CONFIDENCE]" });
      }
      if (config.arisMode === "auto" && (r.action === "BOX" || r.action === "PIT_SOON") && r.net_delta_s < 0) {
        next.push({
          id: next.length + 2,
          type: "confirm",
          text: `BOX called. ${r.compound_recommendation ?? ""} tyres. Net ${r.net_delta_s.toFixed(1)}s.`,
        });
      }
      return next;
    });
  }, [rec.status, rec.status === "ok" ? rec.data.decision_record_id : null, config.arisMode]);

  const chartData = useMemo(() => buildLapChart(laps.status === "ok" ? laps.data : null, chartLap), [laps, chartLap]);
  const codes = chartData.codes.slice(0, 6);

  const sendChat = async () => {
    const q = chatInput.trim();
    if (!q) return;
    setChatInput("");
    setMessages((m) => [...m, { id: m.length + 1, type: "user", text: q }]);
    try {
      const ans = await apiGet<ChatResponse>(
        `/api/aris/chat?question=${encodeURIComponent(q)}&driver_code=${config.driver}`,
        { timeout: 20_000 },
      );
      setMessages((m) => [
        ...m,
        {
          id: m.length + 1,
          type: "aris_response",
          text: ans.answer + (ans.cited_ids.length ? ` [${ans.cited_ids.join(", ")}]` : ""),
        },
      ]);
    } catch (err) {
      setMessages((m) => [...m, { id: m.length + 1, type: "alert", text: String(err) }]);
    }
  };

  const runSim = async () => {
    try {
      const out = await apiPost<{
        total_race_time_delta_s: number;
        risk_level: string;
        note: string | null;
        wet_reduced_confidence: boolean;
      }>("/api/aris/simulate", {
        year: config.year,
        round_number: config.round.round_number,
        driver_code: config.driver,
        current_lap: lap,
        pit_lap: whatIf.pitLap,
        compound: "HARD",
        sc_probability: whatIf.sc / 100,
        rain_lap: whatIf.rain || null,
        deg_factor: whatIf.deg,
      });
      setSimResult(
        `Δ ${out.total_race_time_delta_s.toFixed(2)}s vs stay-out · risk ${out.risk_level}` +
          (out.wet_reduced_confidence ? " · [WET: REDUCED CONFIDENCE]" : "") +
          (out.note ? ` · ${out.note}` : ""),
      );
    } catch (err) {
      setSimResult(String(err));
    }
  };

  return (
    <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div
        style={{
          padding: "8px 16px",
          borderBottom: `1px solid ${C.border}`,
          display: "flex",
          alignItems: "center",
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span style={{ fontFamily: T.mono, fontSize: 10, color: C.faint }}>LAP</span>
          <span style={{ fontFamily: T.display, fontSize: 26, fontWeight: 900, color: C.signal }}>{lap}</span>
          <span style={{ fontFamily: T.mono, fontSize: 10, color: C.faint }}>/ {totalLaps}</span>
        </div>
        <div style={{ flex: 1, minWidth: 80, height: 4, background: C.ghost, borderRadius: 2, maxWidth: 200 }}>
          <div style={{ width: `${(lap / totalLaps) * 100}%`, height: "100%", background: C.signal }} />
        </div>
        {!isLive && (
          <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <span style={{ fontFamily: T.mono, fontSize: 9, color: C.faint }}>SPEED</span>
            {SPEED_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                style={{
                  padding: "3px 8px",
                  cursor: "pointer",
                  background: speed === s ? C.signalMid : "transparent",
                  border: `1px solid ${speed === s ? C.signal : C.border}`,
                  color: speed === s ? C.signal : C.faint,
                  fontFamily: T.mono,
                  fontSize: 10,
                }}
              >
                {s}
              </button>
            ))}
            <button
              onClick={() => setRunning((r) => !r)}
              style={{
                padding: "4px 14px",
                cursor: "pointer",
                background: running ? C.cautionDim : C.greenDim,
                border: `1px solid ${running ? C.caution : C.green}`,
                color: running ? C.caution : C.green,
                fontFamily: T.mono,
                fontSize: 10,
              }}
            >
              {running ? "■ PAUSE" : "▶ RUN"}
            </button>
          </div>
        )}
        <Chip tone={config.arisMode === "auto" ? "green" : "signal"}>{config.arisMode === "auto" ? "AUTO" : "ASSISTED"}</Chip>
        {isLive ? (
          <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <LiveDot />
            <Chip tone="caution">LIVE</Chip>
          </span>
        ) : (
          <Chip tone="mist">REPLAY {speed}</Chip>
        )}
        {config.year === 2026 && <Chip tone="purple" size="xs">2026 REG NOTE</Chip>}
      </div>

      {!isLive && rec.status === "error" && (
        <PanelError
          message={
            rec.error.toLowerCase().includes("ingest") || rec.error.includes("503")
              ? "Strategy engine requires ingested session. Retry, or ingest this weekend into Postgres."
              : rec.error
          }
          onRetry={rec.retry}
        />
      )}
      {config.arisMode === "assisted" && rec.status === "ok" && pitDecision === null && (
        <div
          style={{
            padding: "10px 16px",
            borderBottom: `1px solid ${C.border}`,
            background: `linear-gradient(90deg, ${C.signalDim}, ${C.panel})`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <span style={{ fontFamily: T.mono, fontSize: 11, color: C.signal }}>
            ARIS RECOMMENDS: {rec.data.action}
            {rec.data.compound_recommendation ? ` → ${rec.data.compound_recommendation}` : ""} — {rec.data.reasoning}
          </span>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <div style={{ minWidth: 220 }}>
              <ReasoningBar paceGain={rec.data.pace_gain_s} pitCost={rec.data.pit_cost_s} />
            </div>
            <button
              onClick={() => setPitDecision("pit")}
              style={{ padding: "5px 16px", background: C.green, border: "none", color: C.ink, fontFamily: T.mono, fontSize: 10, cursor: "pointer" }}
            >
              ✓ BOX BOX
            </button>
            <button
              onClick={() => setPitDecision("stay")}
              style={{
                padding: "5px 16px",
                background: "transparent",
                border: `1px solid ${C.caution}`,
                color: C.caution,
                fontFamily: T.mono,
                fontSize: 10,
                cursor: "pointer",
              }}
            >
              STAY OUT
            </button>
          </div>
        </div>
      )}

      <div style={{ padding: "0 16px", borderBottom: `1px solid ${C.border}` }}>
        <TabBar
          tabs={[
            ["race", "RACE CONSOLE"],
            ["analytics", "ANALYTICS"],
            ["strategy", "STRATEGY SIM"],
            ["telemetry", "TELEMETRY"],
            ...(isLive ? ([["ops", "OPS ROOM"]] as [string, string][]) : []),
          ]}
          active={mainTab}
          onChange={setMainTab}
          style={{ padding: "6px 0 0" }}
        />
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
        {mainTab === "race" && (
          <div
            style={{
              height: "100%",
              display: "grid",
              gridTemplateColumns: "1fr 280px 280px",
              gridTemplateRows: "1fr 180px",
              gap: 8,
              padding: 10,
            }}
          >
            <Panel
              title="TRACK MAP"
              style={{ gridRow: "1 / 2" }}
              right={
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {rows.slice(0, 12).map((c) => (
                    <button
                      key={c.driver_code}
                      onClick={() =>
                        setHiddenCars((h) =>
                          h.includes(c.driver_code) ? h.filter((x) => x !== c.driver_code) : [...h, c.driver_code],
                        )
                      }
                      style={{
                        fontSize: 8,
                        fontFamily: T.mono,
                        border: `1px solid ${hiddenCars.includes(c.driver_code) ? C.border : c.team_colour || C.mist}`,
                        background: "transparent",
                        color: hiddenCars.includes(c.driver_code) ? C.faint : C.paper,
                        cursor: "pointer",
                      }}
                    >
                      {c.driver_code}
                    </button>
                  ))}
                </div>
              }
            >
              <TrackMap
                year={config.year}
                round={config.round.round_number}
                sessionType="R"
                cars={rows}
                focusCode={config.driver}
                hiddenCars={hiddenCars}
              />
            </Panel>
            <Panel title="TIMING TOWER">
              {replay.status === "error" && !isLive && <PanelError message={replay.error} onRetry={replay.retry} />}
              {isLive && live.error && <EmptyState title="Live data connection pending" body={`${live.error} Retrying.`} />}
              <TimingTower
                rows={rows}
                focus={config.driver}
                loading={
                  isLive
                    ? !live.timing && !live.error
                    : replay.status === "loading" && rows.length === 0
                }
              />
            </Panel>
            <Panel title="ARIS COMMS" style={{ gridRow: "1 / 3" }} right={<Chip tone="signal" size="xs">{config.arisMode.toUpperCase()}</Chip>}>
              <Comms messages={messages} input={chatInput} setInput={setChatInput} onSend={() => void sendChat()} />
            </Panel>
            <Panel title="LAP TIME TREND">
              {laps.status === "loading" && <div style={{ padding: 12 }}><Skeleton height={140} /></div>}
              {laps.status === "error" && <PanelError message={laps.error} onRetry={laps.retry} />}
              {laps.status === "ok" && (
                <ResponsiveContainer width="100%" height={170}>
                  <LineChart data={chartData.rows} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
                    <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: C.faint, fontSize: 9 }} domain={["dataMin - 0.3", "dataMax + 0.5"]} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}`, fontSize: 10 }} />
                    {codes.map((code, i) => (
                      <Line key={code} type="monotone" dataKey={code} stroke={CHART_COLORS[i % CHART_COLORS.length]} strokeWidth={code === config.driver ? 2.2 : 1.2} dot={false} isAnimationActive={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Panel>
            <Panel title={`TYRE STATUS · ${config.driver}`}>
              <div style={{ padding: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <TyreBadge compound={focusStint?.compound} life={focusStint?.tyre_life} />
                  <div>
                    <div style={{ fontFamily: T.display, fontSize: 22, fontWeight: 800, color: C.signal }}>
                      {focusStint?.tyre_life ?? "—"} LAPS
                    </div>
                    <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint }}>
                      {compoundLetter(focusStint?.compound)} · stint {focusStint?.stint_number ?? "—"}
                    </div>
                  </div>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {mainTab === "analytics" && (
          <AnalyticsPane
            tab={analyticsTab}
            onTab={setAnalyticsTab}
            config={config}
            lap={chartLap}
            chartData={chartData}
            codes={codes}
            standings={standings}
            circuit={circuit}
            rec={rec.status === "ok" ? rec.data : null}
            rows={rows}
          />
        )}

        {mainTab === "strategy" && (
          <div style={{ height: "100%", overflow: "auto", padding: 14 }}>
            <TabBar
              tabs={[["h2h", "HEAD-TO-HEAD"], ["whatif", "WHAT-IF"], ["field", "FIELD STRATEGY"]]}
              active={simTab}
              onChange={setSimTab}
            />
            {simTab === "h2h" && (
              <H2H config={config} codes={codes} chartData={chartData} />
            )}
            {simTab === "whatif" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
                <Panel title="WHAT-IF SCENARIOS">
                  <div style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10 }}>
                    <label style={lab}>
                      Pit lap override
                      <input type="number" value={whatIf.pitLap} onChange={(e) => setWhatIf({ ...whatIf, pitLap: Number(e.target.value) })} style={inp} />
                    </label>
                    <label style={lab}>
                      SC probability %
                      <input type="number" min={0} max={100} value={whatIf.sc} onChange={(e) => setWhatIf({ ...whatIf, sc: Number(e.target.value) })} style={inp} />
                    </label>
                    <label style={lab}>
                      Rain lap (0 = none)
                      <input type="number" value={whatIf.rain} onChange={(e) => setWhatIf({ ...whatIf, rain: Number(e.target.value) })} style={inp} />
                    </label>
                    <label style={lab}>
                      Deg factor
                      <input type="number" step={0.1} min={0.5} max={2} value={whatIf.deg} onChange={(e) => setWhatIf({ ...whatIf, deg: Number(e.target.value) })} style={inp} />
                    </label>
                    <button onClick={() => void runSim()} style={{ padding: 10, background: C.signalMid, border: `1px solid ${C.signal}`, color: C.signal, fontFamily: T.mono, cursor: "pointer" }}>
                      RUN SIMULATION →
                    </button>
                  </div>
                </Panel>
                <Panel title="SIMULATION RESULT">
                  <div style={{ padding: 16, fontFamily: T.body, color: C.mist }}>
                    {simResult || "Adjust parameters and run to see projected outcome vs baseline stay-out."}
                  </div>
                </Panel>
              </div>
            )}
            {simTab === "field" && (
              <Panel title="FIELD STRATEGY">
                <div style={{ padding: 14 }}>
                  {rows.map((row) => (
                    <div key={row.driver_code} style={{ display: "flex", gap: 12, padding: "8px 0", borderBottom: `1px solid ${C.border}40`, alignItems: "center" }}>
                      <span style={{ fontFamily: T.mono, width: 28, color: C.faint }}>P{row.position}</span>
                      <span style={{ fontFamily: T.mono, width: 36, fontWeight: 700 }}>{row.driver_code}</span>
                      <TyreBadge compound={row.compound} life={row.tyre_life} size="sm" />
                    </div>
                  ))}
                </div>
              </Panel>
            )}
          </div>
        )}

        {mainTab === "telemetry" && <TelemetryPane config={config} codes={codes} />}

        {mainTab === "ops" && isLive && <OpsPane />}
      </div>

      <div style={{ position: "fixed", bottom: 16, right: 16 }}>
        <button
          onClick={onDebrief}
          style={{
            padding: "10px 18px",
            background: C.signalMid,
            border: `1px solid ${C.signal}`,
            color: C.signal,
            fontFamily: T.mono,
            fontSize: 10,
            cursor: "pointer",
            borderRadius: 4,
          }}
        >
          END RACE → DEBRIEF
        </button>
      </div>
    </div>
  );
}

function buildLapChart(data: LapsResponse | null, upTo: number) {
  if (!data) return { rows: [] as Record<string, number>[], codes: [] as string[] };
  const codes = [...new Set(data.laps.map((l) => l.driver_code))];
  const byLap = new Map<number, Record<string, number>>();
  for (const lap of data.laps) {
    if (lap.lap_number > upTo || lap.lap_time_ms == null) continue;
    const row = byLap.get(lap.lap_number) ?? { lap: lap.lap_number };
    row[lap.driver_code] = lap.lap_time_ms / 1000;
    byLap.set(lap.lap_number, row);
  }
  return { rows: [...byLap.values()].sort((a, b) => a.lap - b.lap), codes };
}

function Comms({
  messages,
  input,
  setInput,
  onSend,
}: {
  messages: Msg[];
  input: string;
  setInput: (s: string) => void;
  onSend: () => void;
}) {
  const border: Record<string, string> = {
    intel: C.mist,
    recommend: C.signal,
    alert: C.caution,
    confirm: C.green,
    user: C.blue,
    aris_response: C.purple,
  };
  const label: Record<string, string> = {
    intel: "◉ INTEL",
    recommend: "⚡ ARIS RECOMMENDS",
    alert: "⚠ ALERT",
    confirm: "✓ CONFIRM",
    user: "YOU",
    aris_response: "ARIS RESPONSE",
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflow: "auto", padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        {messages.length === 0 && (
          <EmptyState title="No messages yet" body="Recommendations appear as the replay clock advances. Ask ARIS below." />
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            style={{
              padding: "8px 10px",
              borderRadius: 4,
              background: C.panel2,
              borderLeft: `3px solid ${border[m.type] || C.border}`,
            }}
          >
            <div style={{ fontFamily: T.mono, fontSize: 8, color: C.faint, marginBottom: 3 }}>{label[m.type] || "ARIS"}</div>
            <div style={{ fontFamily: T.body, fontSize: 11.5, color: C.paper, lineHeight: 1.5 }}>{m.text}</div>
          </div>
        ))}
      </div>
      <div style={{ padding: 8, borderTop: `1px solid ${C.border}`, display: "flex", gap: 6 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && onSend()}
          placeholder="Ask ARIS anything…"
          style={{
            flex: 1,
            background: C.raised,
            border: `1px solid ${C.border}`,
            borderRadius: 3,
            padding: "6px 10px",
            color: C.paper,
            fontFamily: T.body,
            fontSize: 11,
            outline: "none",
          }}
        />
        <button onClick={onSend} style={{ padding: "6px 10px", background: C.signal, border: "none", borderRadius: 3, cursor: "pointer", color: C.ink, fontFamily: T.mono, fontSize: 10 }}>
          →
        </button>
      </div>
    </div>
  );
}

function AnalyticsPane({
  tab,
  onTab,
  config,
  lap,
  chartData,
  codes,
  standings,
  circuit,
  rec,
  rows,
}: {
  tab: string;
  onTab: (s: string) => void;
  config: SessionConfig;
  lap: number;
  chartData: { rows: Record<string, number>[]; codes: string[] };
  codes: string[];
  standings: ReturnType<typeof useStandings>;
  circuit: ReturnType<typeof useCircuit>;
  rec: RecommendResponse | null;
  rows: LiveTimingRow[];
}) {
  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ padding: "0 14px", borderBottom: `1px solid ${C.border}` }}>
        <TabBar
          tabs={[
            ["driver", "DRIVER STATS"],
            ["standings", "STANDINGS"],
            ["gaps", "GAP TRENDS"],
            ["positions", "POSITIONS"],
            ["tyres", "TYRE ANALYSIS"],
            ["track", "TRACK INFO"],
          ]}
          active={tab}
          onChange={onTab}
          style={{ paddingTop: 6 }}
        />
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: 14 }}>
        {tab === "driver" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12 }}>
            <Panel title={`${config.driver} RACE STATS`}>
              <div style={{ padding: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <Stat label="Current pos" value={rows.find((r) => r.driver_code === config.driver)?.position ? `P${rows.find((r) => r.driver_code === config.driver)?.position}` : "—"} />
                <Stat label="Last lap" value={formatMs(rows.find((r) => r.driver_code === config.driver)?.last_lap_ms)} />
                <Stat label="Best lap" value={formatMs(rows.find((r) => r.driver_code === config.driver)?.best_lap_ms)} />
                <Stat label="Tyre" value={`${compoundLetter(rows.find((r) => r.driver_code === config.driver)?.compound)} ${rows.find((r) => r.driver_code === config.driver)?.tyre_life ?? "—"}L`} />
              </div>
            </Panel>
            <Panel title="LAP ANALYSIS">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData.rows}>
                  <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
                  <YAxis domain={["dataMin - 0.2", "dataMax + 0.3"]} tick={{ fill: C.faint, fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
                  {codes.map((code, i) => (
                    <Line key={code} dataKey={code} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} strokeWidth={code === config.driver ? 2.4 : 1.2} isAnimationActive={false} />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            </Panel>
          </div>
        )}
        {tab === "standings" && (
          <Panel title="DRIVERS CHAMPIONSHIP">
            {standings.drivers.status === "loading" && <div style={{ padding: 12 }}>{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} height={16} />)}</div>}
            {standings.drivers.status === "error" && <PanelError message={standings.drivers.error} onRetry={standings.drivers.retry} />}
            {standings.drivers.status === "ok" && standings.drivers.data.standings.length === 0 && (
              <EmptyState title="Standings unavailable" body="Jolpica returned no championship data for this year." />
            )}
            {standings.drivers.status === "ok" && (
              <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
                <thead>
                  <tr style={{ color: C.faint, fontSize: 9 }}>
                    {["POS", "DRIVER", "TEAM", "PTS", "WINS"].map((h) => (
                      <th key={h} style={{ textAlign: "left", padding: "8px 12px" }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {standings.drivers.data.standings.map((r) => (
                    <tr key={r.driver_code} style={{ borderBottom: `1px solid ${C.border}50`, background: r.driver_code === config.driver ? C.signalMid : "transparent" }}>
                      <td style={{ padding: "8px 12px" }}>{r.position}</td>
                      <td style={{ padding: "8px 12px" }}>{r.driver_code}</td>
                      <td style={{ padding: "8px 12px", color: C.mist }}>{r.team_name}</td>
                      <td style={{ padding: "8px 12px", color: C.signal }}>{r.points}</td>
                      <td style={{ padding: "8px 12px" }}>{r.wins}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Panel>
        )}
        {tab === "gaps" && <GapPane year={config.year} round={config.round.round_number} lap={lap} />}
        {tab === "positions" && <PosPane year={config.year} round={config.round.round_number} lap={lap} codes={codes} />}
        {tab === "tyres" && (
          <Panel title="TYRE STRATEGY">
            <TyrePane year={config.year} round={config.round.round_number} rec={rec} />
          </Panel>
        )}
        {tab === "track" && (
          <Panel title={`${config.round.circuit_name}`}>
            {circuit.chars.status === "ok" ? (
              <div style={{ padding: 14 }}>
                {[
                  ["Length", circuit.chars.data.lap_length_km ? `${circuit.chars.data.lap_length_km} km` : "—"],
                  ["Turns", String(circuit.chars.data.turns ?? "—")],
                  ["Pit loss", circuit.chars.data.pit_loss_seconds != null ? `~${circuit.chars.data.pit_loss_seconds}s` : "—"],
                ].map(([k, v]) => (
                  <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0" }}>
                    <span style={{ color: C.mist }}>{k}</span>
                    <span style={{ fontFamily: T.mono }}>{v}</span>
                  </div>
                ))}
              </div>
            ) : circuit.chars.status === "error" ? (
              <PanelError message={circuit.chars.error} onRetry={circuit.chars.retry} />
            ) : (
              <div style={{ padding: 14 }}><Skeleton height={80} /></div>
            )}
          </Panel>
        )}
      </div>
    </div>
  );
}

function GapPane({ year, round, lap }: { year: number; round: number; lap: number }) {
  const [data, setData] = useState<{ lap: number; gaps: Record<string, number> }[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    apiGet<{ laps: { lap: number; gaps: Record<string, number> }[] }>(`/api/race/${year}/${round}/gap-history`, { timeout: 120_000 })
      .then((d) => setData(d.laps.filter((x) => x.lap <= lap)))
      .catch((e) => setErr(String(e)));
  }, [year, round, lap]);
  if (err) return <PanelError message={err} onRetry={() => setErr(null)} />;
  if (!data) return <Skeleton height={200} />;
  const codes = data[0] ? Object.keys(data[0].gaps).slice(0, 6) : [];
  const rows = data.map((d) => ({ lap: d.lap, ...d.gaps }));
  return (
    <Panel title="GAP TO LEADER (s)">
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={rows}>
          <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
          <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
          <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
          {codes.map((c, i) => (
            <Line key={c} dataKey={c} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}

function PosPane({ year, round, lap, codes }: { year: number; round: number; lap: number; codes: string[] }) {
  const [data, setData] = useState<{ lap: number }[] | null>(null);
  useEffect(() => {
    apiGet<{ laps: { lap: number; positions: Record<string, number> }[] }>(`/api/race/${year}/${round}/position-history`, { timeout: 120_000 })
      .then((d) => setData(d.laps.filter((x) => x.lap <= lap).map((x) => ({ lap: x.lap, ...x.positions }))))
      .catch(() => setData([]));
  }, [year, round, lap]);
  if (!data) return <Skeleton height={200} />;
  return (
    <Panel title="POSITION CHANGES BY LAP">
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data}>
          <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
          <YAxis reversed domain={[1, 20]} tick={{ fill: C.faint, fontSize: 9 }} />
          <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
          {codes.map((c, i) => (
            <Line key={c} type="stepAfter" dataKey={c} stroke={CHART_COLORS[i % CHART_COLORS.length]} dot={false} isAnimationActive={false} />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}

function TyrePane({ year, round, rec }: { year: number; round: number; rec: RecommendResponse | null }) {
  const [stints, setStints] = useState<{ driver_code: string; compound: string | null; lap_start: number; lap_end: number }[] | null>(null);
  useEffect(() => {
    apiGet<{ stints: { driver_code: string; compound: string | null; lap_start: number; lap_end: number }[] }>(
      `/api/race/${year}/${round}/tyre-strategy`,
      { timeout: 120_000 },
    )
      .then((d) => setStints(d.stints))
      .catch(() => setStints([]));
  }, [year, round]);
  if (!stints) return <Skeleton height={120} />;
  return (
    <div style={{ padding: 14 }}>
      {rec && <ReasoningBar paceGain={rec.pace_gain_s} pitCost={rec.pit_cost_s} label />}
      {stints.slice(0, 24).map((s, i) => (
        <div key={i} style={{ display: "flex", gap: 8, padding: "4px 0", fontFamily: T.mono, fontSize: 11 }}>
          <span style={{ width: 36 }}>{s.driver_code}</span>
          <TyreBadge compound={s.compound} size="sm" />
          <span style={{ color: C.mist }}>
            L{s.lap_start}–{s.lap_end}
          </span>
        </div>
      ))}
    </div>
  );
}

function H2H({
  config,
  codes,
  chartData,
}: {
  config: SessionConfig;
  codes: string[];
  chartData: { rows: Record<string, number>[] };
}) {
  const b = codes.find((c) => c !== config.driver) || codes[0];
  const [cmp, setCmp] = useState<{ quali_wins_a: number; quali_wins_b: number; race_wins_a: number; race_wins_b: number; avg_lap_delta_ms: number | null } | null>(null);
  useEffect(() => {
    if (!b) return;
    apiGet<{ quali_wins_a: number; quali_wins_b: number; race_wins_a: number; race_wins_b: number; avg_lap_delta_ms: number | null }>(`/api/compare/drivers?driver_a=${config.driver}&driver_b=${b}&year=${config.year}&round_number=${config.round.round_number}`, { timeout: 60_000 })
      .then((d) => setCmp(d))
      .catch(() => setCmp(null));
  }, [b, config]);
  const deltaRows = chartData.rows.map((r) => ({
    lap: r.lap,
    delta: typeof r[config.driver] === "number" && typeof r[b] === "number" ? Number(r[config.driver]) - Number(r[b]) : 0,
  }));
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginTop: 12 }}>
      <Panel title={`HEAD-TO-HEAD: ${config.driver} vs ${b ?? "—"}`}>
        <div style={{ padding: 14 }}>
          {!cmp && <EmptyState title="Compare loading or unavailable" body="Needs both drivers in this session." />}
          {cmp && (
            <>
              <Stat label="Quali record" value={`${cmp.quali_wins_a}–${cmp.quali_wins_b}`} />
              <Stat label="Race record" value={`${cmp.race_wins_a}–${cmp.race_wins_b}`} />
              <Stat label="Avg lap delta" value={cmp.avg_lap_delta_ms != null ? `${(cmp.avg_lap_delta_ms / 1000).toFixed(3)}s` : "—"} />
            </>
          )}
        </div>
      </Panel>
      <Panel title="PACE DELTA BY LAP">
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={deltaRows}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
            <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
            <Area dataKey="delta" stroke={C.signal} fill={C.signalDim} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}

function TelemetryPane({ config, codes }: { config: SessionConfig; codes: string[] }) {
  const other = codes.find((c) => c !== config.driver);
  const [a, setA] = useState<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] } | null>(null);
  const [b, setB] = useState<{ distance: number[]; speed: number[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    apiGet<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] }>(`/api/session/${config.year}/${config.round.round_number}/R/telemetry/${config.driver}`, { timeout: 120_000 })
      .then((d) => setA(d))
      .catch((e) => setErr(String(e)));
    if (other) {
      apiGet<{ distance: number[]; speed: number[] }>(`/api/session/${config.year}/${config.round.round_number}/R/telemetry/${other}`, { timeout: 120_000 })
        .then((d) => setB(d))
        .catch(() => undefined);
    }
  }, [config, other]);
  if (err) return <PanelError message={err} onRetry={() => setErr(null)} />;
  if (!a) return <div style={{ padding: 14 }}><Skeleton height={220} /></div>;
  const speedRows = a.distance.map((d, i) => ({
    dist: Math.round(d),
    [config.driver]: a.speed[i],
    ...(b ? { [other as string]: b.speed[i] } : {}),
  }));
  const thr = a.distance.map((d, i) => ({ dist: Math.round(d), throttle: a.throttle[i], brake: a.brake[i] }));
  const intercept = speedRows.slice(0, 80).map((row, i) => {
    const va = Number(row[config.driver] ?? 0);
    const vb = Number(other ? row[other] ?? 0 : 0);
    return { i, delta: va - vb };
  });
  return (
    <div style={{ overflow: "auto", padding: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      <Panel title={`SPEED TRACE — ${config.driver}${other ? ` vs ${other}` : ""}`}>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={speedRows}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="dist" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
            <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
            <Line dataKey={config.driver} stroke={C.signal} dot={false} isAnimationActive={false} />
            {other && <Line dataKey={other} stroke={C.blue} dot={false} isAnimationActive={false} />}
          </LineChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title={`THROTTLE vs BRAKE — ${config.driver}`}>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={thr}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="dist" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
            <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
            <Area dataKey="throttle" stroke={C.green} fill={C.greenDim} isAnimationActive={false} />
            <Area dataKey="brake" stroke={C.caution} fill={C.cautionDim} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title="MINI-SECTOR INTERCEPT">
        <div style={{ padding: 14 }}>
          {intercept.filter((_, i) => i % 10 === 0).slice(0, 8).map((m, idx) => (
            <div key={idx} style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center" }}>
              <span style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, width: 48 }}>Mini {idx + 1}</span>
              <div style={{ flex: 1, height: 6, background: C.ghost, position: "relative" }}>
                <div style={{ position: "absolute", left: "50%", width: 1, height: "100%", background: C.border }} />
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    height: "100%",
                    width: `${Math.min(50, Math.abs(m.delta) / 4)}%`,
                    left: m.delta >= 0 ? "50%" : undefined,
                    right: m.delta < 0 ? "50%" : undefined,
                    background: m.delta >= 0 ? C.green : C.signal,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function OpsPane() {
  const [msgs, setMsgs] = useState<{ utc_time: string | null; category: string | null; message: string }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    apiGet<{ messages: typeof msgs }>("/api/live/race-control", { timeout: 15_000 })
      .then((d) => setMsgs(d.messages))
      .catch((e) => setErr(String(e)));
  }, []);
  return (
    <div style={{ padding: 12 }}>
      <Panel title="RACE CONTROL FEED">
        {err && <EmptyState title="Live data connection pending. Retrying in 15s." body={err} />}
        <div style={{ padding: 10, display: "flex", flexDirection: "column", gap: 6 }}>
          {msgs.map((m, i) => (
            <div key={i} style={{ padding: "6px 10px", borderLeft: `3px solid ${C.signal}`, background: C.panel2 }}>
              <div style={{ fontFamily: T.mono, fontSize: 8, color: C.signal }}>{m.category}</div>
              <div style={{ fontFamily: T.body, fontSize: 11 }}>{m.message}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

const lab: CSSProperties = { display: "flex", justifyContent: "space-between", fontFamily: T.body, fontSize: 12, color: C.mist, alignItems: "center" };
const inp: CSSProperties = { background: C.raised, border: `1px solid ${C.border}`, color: C.paper, padding: "4px 8px", width: 80, fontFamily: T.mono };
