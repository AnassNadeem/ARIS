import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceArea,
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
import { C, SPEED_MS, SPEED_OPTIONS, T, compoundLetter } from "../theme";
import { Chip, EmptyState, LiveDot, Panel, PanelError, ReasoningBar, Skeleton, SkeletonPanel, Stat, TabBar, TyreBadge, formatMs } from "../components/atoms";
import { TimingTower } from "../components/TimingTower";
import { TrackMap } from "../components/TrackMap";
import { CarFilter } from "../components/CarFilter";
import { CommsPanel, type CommMsg } from "../components/CommsPanel";
import { BoxBanner } from "../components/BoxBanner";
import { LapTimeChart } from "../components/LapTimeChart";
import { CircuitOutline } from "../components/CircuitSvg";
import { useCircuitMap } from "../hooks/useCircuitMap";
import { useDrivers } from "../hooks/useDrivers";

const CHART_COLORS = [C.blue, C.signal, C.green, C.caution, C.purple, "#FF8000"];

type Msg = CommMsg;

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
  const rec = useARISRecommend(
    config.year,
    config.round.round_number,
    config.driver,
    lap,
    true,
    isLive ? "live" : "replay",
    live.status?.session_key,
  );
  const standings = useStandings(config.year);
  const circuit = useCircuit(config.round.circuit_key, config.year);
  const drivers = useDrivers(config.year);
  const [scRanges, setScRanges] = useState<[number, number][]>([]);

  useEffect(() => {
    apiGet<{ messages: { lap: number | null; flag: string | null; category: string | null; message: string }[] }>(
      `/api/session/${config.year}/${config.round.round_number}/R/messages`,
      { timeout: 60_000 },
    )
      .then((d) => {
        const ranges: [number, number][] = [];
        let start: number | null = null;
        for (const m of d.messages) {
          const blob = `${m.flag || ""} ${m.category || ""} ${m.message || ""}`.toUpperCase();
          const lapNo = m.lap ?? 0;
          if ((blob.includes("SAFETY CAR") || blob.includes("VSC") || blob === "SC") && start == null) {
            start = lapNo || 1;
          }
          if (start != null && (blob.includes("CLEAR") || blob.includes("GREEN") || blob.includes("END"))) {
            ranges.push([start, lapNo || start + 1]);
            start = null;
          }
        }
        if (start != null) ranges.push([start, start + 3]);
        setScRanges(ranges);
      })
      .catch(() => undefined);
  }, [config.year, config.round.round_number]);

  const totalLaps = circuit.chars.status === "ok" ? circuit.chars.data.total_laps ?? 60 : 60;
  const rows: LiveTimingRow[] = isLive ? live.timing?.rows ?? [] : replay.status === "ok" ? replay.data.rows : [];
  const focusStint = rows.find((r) => r.driver_code === config.driver);

  const [chartLap, setChartLap] = useState(1);
  useEffect(() => {
    const delay = lap <= 1 ? 0 : 2000;
    const id = window.setTimeout(() => setChartLap(lap), delay);
    return () => window.clearTimeout(id);
  }, [lap]);

  useEffect(() => {
    if (isLive || !running) return;
    const id = window.setInterval(() => {
      setLap((n) => Math.min(totalLaps, n + 1));
    }, SPEED_MS[speed] ?? 1500);
    return () => window.clearInterval(id);
  }, [running, speed, isLive, totalLaps]);

  const lastRecId = useRef<string | null>(null);
  const lastAction = useRef<string | null>(null);
  const lastEventsLap = useRef<number | null>(null);

  useEffect(() => {
    if (isLive) return;
    if (lastEventsLap.current === lap) return;
    lastEventsLap.current = lap;
    apiGet<{ events: { type: string; text: string }[] }>(
      `/api/session/${config.year}/${config.round.round_number}/R/events/${lap}?driver_code=${config.driver}`,
      { timeout: 30_000 },
    )
      .then((d) => {
        if (!d.events.length) return;
        setMessages((m) => [
          ...m,
          ...d.events.map((e, i) => ({
            id: m.length + i + 1,
            type: e.type.toLowerCase() === "alert" ? "alert" : "intel",
            text: e.text,
          })),
        ]);
      })
      .catch(() => undefined);
  }, [lap, isLive, config.year, config.round.round_number, config.driver]);

  useEffect(() => {
    if (rec.status !== "ok") return;
    const r = rec.data;
    const stayRepeat = r.action === "STAY_OUT" && lastAction.current === "STAY_OUT";
    if (r.decision_record_id === lastRecId.current) return;
    if (stayRepeat) {
      lastRecId.current = r.decision_record_id;
      return;
    }
    lastRecId.current = r.decision_record_id;
    lastAction.current = r.action;
    setMessages((m) => {
      const next: Msg[] = [
        ...m,
        { id: m.length + 1, type: "recommend", text: `${r.action}: ${r.reasoning}` },
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
  }, [rec.status, rec.status === "ok" ? rec.data.decision_record_id : null, rec.status === "ok" ? rec.data.action : null, config.arisMode]);

  const chartData = useMemo(() => buildLapChart(laps.status === "ok" ? laps.data : null, chartLap), [laps, chartLap]);
  const codes = chartData.codes;

  const sendChat = async () => {
    const q = chatInput.trim();
    if (!q) return;
    setChatInput("");
    setMessages((m) => [...m, { id: m.length + 1, type: "user", text: q }]);
    try {
      const ans = await apiGet<ChatResponse>(
        `/api/aris/chat?question=${encodeURIComponent(q)}&driver_code=${config.driver}&year=${config.year}&round_number=${config.round.round_number}&current_lap=${lap}`,
        { timeout: 60_000 },
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
      {config.arisMode === "assisted" && rec.status === "ok" && pitDecision === null && (rec.data.action === "BOX" || rec.data.action === "PIT_SOON") && (
        <BoxBanner
          rec={rec.data}
          onBox={(compound) => {
            setPitDecision("pit");
            setMessages((m) => [
              ...m,
              { id: m.length + 1, type: "confirm", text: `BOX BOX — ${compound} (user confirmed)` },
            ]);
          }}
          onStay={() => {
            setPitDecision("stay");
            setMessages((m) => [...m, { id: m.length + 1, type: "alert", text: "STAY OUT — user override" }]);
          }}
        />
      )}
      {config.arisMode === "assisted" && rec.status === "ok" && pitDecision === null && rec.data.action !== "BOX" && rec.data.action !== "PIT_SOON" && (
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
            ARIS RECOMMENDS: {rec.data.action} — {rec.data.reasoning}
          </span>
          <div style={{ minWidth: 220 }}>
            <ReasoningBar paceGain={rec.data.pace_gain_s} pitCost={rec.data.pit_cost_s} />
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
            <Panel title="TRACK MAP" style={{ gridRow: "1 / 2" }}>
              <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
                <div style={{ flex: 1, minHeight: 0 }}>
                  <TrackMap
                    year={config.year}
                    round={config.round.round_number}
                    cars={rows}
                    focusCode={config.driver}
                    hiddenCars={hiddenCars}
                    lap={lap}
                    live={isLive}
                    speed={speed}
                  />
                </div>
                {drivers.status === "ok" && (
                  <CarFilter
                    drivers={drivers.data.drivers}
                    hidden={hiddenCars}
                    onToggle={(code) =>
                      setHiddenCars((h) => (h.includes(code) ? h.filter((x) => x !== code) : [...h, code]))
                    }
                  />
                )}
              </div>
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
              <CommsPanel messages={messages} input={chatInput} setInput={setChatInput} onSend={() => void sendChat()} />
            </Panel>
            {(() => {
              const colourBy = new Map(rows.map((r) => [r.driver_code, r.team_colour || C.signal]));
              if (drivers.status === "ok") {
                for (const d of drivers.data.drivers) {
                  if (d.team_colour) colourBy.set(d.driver_code, d.team_colour);
                }
              }
              const pitLaps =
                laps.status === "ok"
                  ? [...new Set(laps.data.laps.filter((l) => l.pit_in_lap).map((l) => l.lap_number))]
                  : [];
              return (
                <LapTimeChart
                  laps={laps}
                  upTo={chartLap}
                  focus={config.driver}
                  colourBy={colourBy}
                  pitLaps={pitLaps}
                  scRanges={scRanges}
                />
              );
            })()}
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
              tabs={[["h2h", "HEAD-TO-HEAD"], ["three", "3-WAY SIM"], ["whatif", "WHAT-IF"], ["field", "FIELD STRATEGY"]]}
              active={simTab}
              onChange={setSimTab}
            />
            {simTab === "h2h" && (
              <H2H config={config} codes={chartData.codes} chartData={chartData} rows={rows} standings={standings} />
            )}
            {simTab === "three" && (
              <ThreeWay config={config} rows={rows} codes={chartData.codes} />
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

        {mainTab === "telemetry" && <TelemetryPane config={config} codes={codes} rows={rows} />}

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
            {standings.drivers.status === "loading" && (
              <SkeletonPanel
                rows={8}
                label="Loading standings — this may take a moment on first load as data is being cached..."
              />
            )}
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
          <TyreAnalysis config={config} rec={rec} rows={rows} />
        )}
        {tab === "track" && (
          <TrackInfoTab config={config} circuit={circuit} />
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

function H2H({
  config,
  codes,
  chartData,
  rows,
  standings,
}: {
  config: SessionConfig;
  codes: string[];
  chartData: { rows: Record<string, number>[] };
  rows: LiveTimingRow[];
  standings: ReturnType<typeof useStandings>;
}) {
  const p2 =
    standings.drivers.status === "ok"
      ? standings.drivers.data.standings.find((s) => s.driver_code !== config.driver)?.driver_code
      : undefined;
  const defaultB =
    p2 ||
    rows.find((r) => r.driver_code !== config.driver)?.driver_code ||
    codes.find((c) => c !== config.driver) ||
    codes[0];
  const [a, setA] = useState(config.driver);
  const [b, setB] = useState(defaultB || "");
  const [cmp, setCmp] = useState<{
    quali_wins_a: number;
    quali_wins_b: number;
    race_wins_a: number;
    race_wins_b: number;
    avg_lap_delta_ms: number | null;
    race_pace_median_delta_ms?: number | null;
    fastest_lap_a_ms?: number | null;
    fastest_lap_b_ms?: number | null;
  } | null>(null);
  useEffect(() => {
    if (!a || !b) return;
    apiGet<{
      quali_wins_a: number;
      quali_wins_b: number;
      race_wins_a: number;
      race_wins_b: number;
      avg_lap_delta_ms: number | null;
      race_pace_median_delta_ms?: number | null;
      fastest_lap_a_ms?: number | null;
      fastest_lap_b_ms?: number | null;
    }>(`/api/compare/drivers?driver_a=${a}&driver_b=${b}&year=${config.year}&round_number=${config.round.round_number}`, { timeout: 60_000 })
      .then((d) => setCmp(d))
      .catch(() => setCmp(null));
  }, [a, b, config]);
  const all = [...new Set([...codes, ...rows.map((r) => r.driver_code)])];
  const deltaRows = chartData.rows.map((r) => ({
    lap: r.lap,
    delta: typeof r[a] === "number" && typeof r[b] === "number" ? Number(r[a]) - Number(r[b]) : 0,
  }));
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
        <label style={{ fontFamily: T.mono, fontSize: 11, color: C.mist }}>
          DRIVER A{" "}
          <select value={a} onChange={(e) => setA(e.target.value)} style={sel}>
            {all.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
        <label style={{ fontFamily: T.mono, fontSize: 11, color: C.mist }}>
          DRIVER B{" "}
          <select value={b} onChange={(e) => setB(e.target.value)} style={sel}>
            {all.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </label>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <Panel title={`HEAD-TO-HEAD: ${a} vs ${b || "—"}`}>
          <div style={{ padding: 14 }}>
            {!cmp && <EmptyState title="Compare loading or unavailable" body="Needs both drivers in this session." />}
            {cmp && (
              <>
                <Stat label="Qualifying record" value={`${cmp.quali_wins_a}–${cmp.quali_wins_b}`} />
                <Stat label="Race pace / wins" value={`${cmp.race_wins_a}–${cmp.race_wins_b}`} />
                <Stat label="Median pace delta" value={cmp.race_pace_median_delta_ms != null ? `${(cmp.race_pace_median_delta_ms / 1000).toFixed(3)}s` : cmp.avg_lap_delta_ms != null ? `${(cmp.avg_lap_delta_ms / 1000).toFixed(3)}s` : "—"} />
                <Stat label="Fastest laps" value={`${cmp.fastest_lap_a_ms != null ? (cmp.fastest_lap_a_ms / 1000).toFixed(3) : "—"} vs ${cmp.fastest_lap_b_ms != null ? (cmp.fastest_lap_b_ms / 1000).toFixed(3) : "—"}`} />
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
    </div>
  );
}

function ThreeWay({ config, rows, codes }: { config: SessionConfig; rows: LiveTimingRow[]; codes: string[] }) {
  const sorted = [...rows].sort((a, b) => a.position - b.position);
  const d0 = config.driver;
  const d1 = sorted.find((r) => r.driver_code !== d0)?.driver_code || codes[1];
  const d2 = sorted.find((r) => r.driver_code !== d0 && r.driver_code !== d1)?.driver_code || codes[2];
  const [a, setA] = useState(d0);
  const [b, setB] = useState(d1 || "");
  const [c, setC] = useState(d2 || "");
  const all = [...new Set([...codes, ...rows.map((r) => r.driver_code)])];
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
        {([
          ["A", a, setA] as const,
          ["B", b, setB] as const,
          ["C", c, setC] as const,
        ]).map(([lab, val, set]) => (
          <label key={lab} style={{ fontFamily: T.mono, fontSize: 11, color: C.mist }}>
            DRIVER {lab}{" "}
            <select value={val} onChange={(e) => set(e.target.value)} style={sel}>
              {all.map((code) => (
                <option key={code} value={code}>{code}</option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <Panel title="3-WAY PACE">
        <div style={{ padding: 14, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12 }}>
          {[a, b, c].map((code) => {
            const row = rows.find((r) => r.driver_code === code);
            return (
              <div key={code} style={{ background: C.panel2, padding: 12, borderRadius: 4 }}>
                <div style={{ fontFamily: T.display, fontSize: 22, fontWeight: 800 }}>{code}</div>
                <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, marginTop: 6 }}>
                  P{row?.position ?? "—"} · gap {row?.gap_to_leader_s != null ? `+${row.gap_to_leader_s.toFixed(1)}s` : "—"}
                </div>
                <div style={{ fontFamily: T.mono, fontSize: 11, color: C.faint }}>
                  last {row?.last_lap_ms != null ? (row.last_lap_ms / 1000).toFixed(3) : "—"} · {row?.compound ?? "—"}
                </div>
              </div>
            );
          })}
        </div>
      </Panel>
    </div>
  );
}

function TelemetryPane({ config, codes, rows }: { config: SessionConfig; codes: string[]; rows: LiveTimingRow[] }) {
  const all = [...new Set([...codes, ...rows.map((r) => r.driver_code)])];
  const rival =
    rows.find((r) => r.driver_code !== config.driver && Math.abs(r.position - (rows.find((x) => x.driver_code === config.driver)?.position ?? 99)) === 1)
      ?.driver_code || all.find((c) => c !== config.driver);
  const [a, setA] = useState(config.driver);
  const [b, setB] = useState(rival || "");
  const [thrDriver, setThrDriver] = useState(config.driver);
  const [ta, setTA] = useState<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] } | null>(null);
  const [tb, setTB] = useState<{ distance: number[]; speed: number[] } | null>(null);
  const [thr, setThr] = useState<{ distance: number[]; throttle: number[]; brake: number[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setTA(null);
    apiGet<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] }>(
      `/api/session/${config.year}/${config.round.round_number}/R/telemetry/${a}`,
      { timeout: 120_000 },
    )
      .then((d) => setTA(d))
      .catch((e) => setErr(String(e)));
    if (b) {
      apiGet<{ distance: number[]; speed: number[] }>(
        `/api/session/${config.year}/${config.round.round_number}/R/telemetry/${b}`,
        { timeout: 120_000 },
      )
        .then((d) => setTB(d))
        .catch(() => undefined);
    }
  }, [config, a, b]);
  useEffect(() => {
    apiGet<{ distance: number[]; throttle: number[]; brake: number[] }>(
      `/api/session/${config.year}/${config.round.round_number}/R/telemetry/${thrDriver}`,
      { timeout: 120_000 },
    )
      .then((d) => setThr(d))
      .catch(() => undefined);
  }, [config, thrDriver]);
  if (err) return <PanelError message={err} onRetry={() => setErr(null)} />;
  if (!ta) return <div style={{ padding: 14 }}><Skeleton height={220} /></div>;
  const speedRows = ta.distance.map((d, i) => ({
    dist: Math.round(d),
    [a]: ta.speed[i],
    ...(tb ? { [b]: tb.speed[i] } : {}),
  }));
  const thrRows = (thr ?? ta).distance.map((d, i) => ({
    dist: Math.round(d),
    throttle: (thr ?? ta).throttle[i],
    brake: (thr ?? ta).brake[i],
  }));
  return (
    <div style={{ overflow: "auto", padding: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      <Panel title={`SPEED TRACE — ${a}${b ? ` vs ${b}` : ""}`}>
        <div style={{ padding: "8px 12px", display: "flex", gap: 8 }}>
          <select value={a} onChange={(e) => setA(e.target.value)} style={sel}>
            {all.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={b} onChange={(e) => setB(e.target.value)} style={sel}>
            {all.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={speedRows}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="dist" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
            <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
            <Line dataKey={a} stroke={C.signal} dot={false} isAnimationActive={false} />
            {b && <Line dataKey={b} stroke={C.blue} dot={false} isAnimationActive={false} />}
          </LineChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title={`THROTTLE vs BRAKE — ${thrDriver}`}>
        <div style={{ padding: "8px 12px" }}>
          <select value={thrDriver} onChange={(e) => setThrDriver(e.target.value)} style={sel}>
            {all.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={thrRows}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="dist" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
            <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
            <Area dataKey="throttle" stroke={C.green} fill={C.greenDim} isAnimationActive={false} />
            <Area dataKey="brake" stroke={C.caution} fill={C.cautionDim} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}

function OpsPane() {
  const [msgs, setMsgs] = useState<{ utc_time: string | null; category: string | null; message: string }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const poll = () => {
      apiGet<{ messages: typeof msgs }>("/api/live/race-control", { timeout: 60_000 })
        .then((d) => setMsgs(d.messages))
        .catch((e) => setErr(String(e)));
    };
    poll();
    const id = window.setInterval(poll, 5000);
    return () => window.clearInterval(id);
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
const sel: CSSProperties = { background: C.raised, border: `1px solid ${C.border}`, color: C.paper, padding: "4px 8px", fontFamily: T.mono, fontSize: 11 };

function TyreAnalysis({
  config,
  rec,
  rows,
}: {
  config: SessionConfig;
  rec: RecommendResponse | null;
  rows: LiveTimingRow[];
}) {
  const [driver, setDriver] = useState(config.driver);
  const [stints, setStints] = useState<
    { driver_code: string; stint_number: number; compound: string | null; lap_start: number; lap_end: number; total_laps: number; average_lap_ms: number | null; deg_rate_ms_per_lap: number | null; fresh_tyre: boolean | null }[] | null
  >(null);
  const [laps, setLaps] = useState<LapsResponse | null>(null);
  useEffect(() => {
    apiGet<{ stints: NonNullable<typeof stints> }>(
      `/api/session/${config.year}/${config.round.round_number}/R/stints`,
      { timeout: 120_000 },
    )
      .then((d) => setStints(d.stints))
      .catch(() => setStints([]));
    apiGet<LapsResponse>(`/api/session/${config.year}/${config.round.round_number}/R/laps`, { timeout: 120_000 })
      .then(setLaps)
      .catch(() => undefined);
  }, [config.year, config.round.round_number]);
  const codes = [...new Set((stints || []).map((s) => s.driver_code))];
  const mine = (stints || []).filter((s) => s.driver_code === driver);
  const wearByStint = new Map<number, { age: number; delta: number }[]>();
  for (const l of laps?.laps || []) {
    if (l.driver_code !== driver || l.lap_time_ms == null || l.tyre_life == null) continue;
    const stint = l.stint_number ?? 1;
    const list = wearByStint.get(stint) ?? [];
    list.push({ age: l.tyre_life, delta: l.lap_time_ms / 1000 });
    wearByStint.set(stint, list);
  }
  const ages = [...new Set([...wearByStint.values()].flat().map((x) => x.age))].sort((a, b) => a - b);
  const wearRows = ages.map((age) => {
    const row: Record<string, number> = { age };
    for (const [st, pts] of wearByStint) {
      const base = pts[0]?.delta ?? 0;
      const hit = pts.find((p) => p.age === age);
      if (hit) row[`s${st}`] = hit.delta - base;
    }
    return row;
  });
  const windowAges = (() => {
    const first = wearByStint.get(mine[0]?.stint_number ?? 1) || [];
    if (!first.length) return null;
    const base = first[0].delta;
    const good = first.filter((p) => Math.abs(p.delta - base) <= 0.4).map((p) => p.age);
    if (!good.length) return null;
    return [Math.min(...good), Math.max(...good)] as [number, number];
  })();
  const degAccel = mine.map((s) => s.deg_rate_ms_per_lap || 0);
  const grain = degAccel.some((d) => d > 80) ? "HIGH" : degAccel.some((d) => d > 40) ? "MEDIUM" : "LOW";
  const field = [...(stints || [])].sort((a, b) => {
    const pa = rows.find((r) => r.driver_code === a.driver_code)?.position ?? 99;
    const pb = rows.find((r) => r.driver_code === b.driver_code)?.position ?? 99;
    return pa - pb || a.stint_number - b.stint_number;
  });
  const grouped = new Map<string, typeof field>();
  for (const s of field) {
    grouped.set(s.driver_code, [...(grouped.get(s.driver_code) || []), s]);
  }
  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginBottom: 12 }}>
        {codes.map((c) => (
          <button key={c} onClick={() => setDriver(c)} style={{ padding: "3px 8px", cursor: "pointer", fontFamily: T.mono, fontSize: 10, background: driver === c ? C.signalMid : "transparent", border: `1px solid ${driver === c ? C.signal : C.border}`, color: driver === c ? C.signal : C.mist }}>
            {c}
          </button>
        ))}
      </div>
      {rec && <ReasoningBar paceGain={rec.pace_gain_s} pitCost={rec.pit_cost_s} label />}
      <Panel title={`${driver} STINTS`} style={{ marginTop: 12 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 11 }}>
          <thead>
            <tr style={{ color: C.faint, fontSize: 9 }}>
              {["STINT", "COMP", "LAPS", "AVG", "DEG ms/lap", "PEAK", "ENTRY"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "6px 10px" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mine.map((s) => {
              const stintLaps = (laps?.laps || []).filter((l) => l.driver_code === driver && l.lap_number >= s.lap_start && l.lap_number <= s.lap_end && l.lap_time_ms);
              const peak = stintLaps.length ? Math.min(...stintLaps.map((l) => l.lap_time_ms as number)) : null;
              return (
                <tr key={s.stint_number} style={{ borderBottom: `1px solid ${C.border}40` }}>
                  <td style={{ padding: "6px 10px" }}>{s.stint_number}</td>
                  <td style={{ padding: "6px 10px" }}><TyreBadge compound={s.compound} size="sm" /></td>
                  <td style={{ padding: "6px 10px" }}>{s.total_laps}</td>
                  <td style={{ padding: "6px 10px" }}>{s.average_lap_ms != null ? formatMs(s.average_lap_ms) : "—"}</td>
                  <td style={{ padding: "6px 10px" }}>{s.deg_rate_ms_per_lap != null ? s.deg_rate_ms_per_lap.toFixed(1) : "—"}</td>
                  <td style={{ padding: "6px 10px" }}>{peak != null ? formatMs(peak) : "—"}</td>
                  <td style={{ padding: "6px 10px" }}>{s.fresh_tyre ? "fresh" : "used"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div style={{ padding: 12, fontFamily: T.mono, fontSize: 11, color: C.mist }}>GRAINING RISK: {grain}</div>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={wearRows}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="age" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
            <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
            {windowAges && <ReferenceArea x1={windowAges[0]} x2={windowAges[1]} fill={C.signal} fillOpacity={0.12} />}
            {[...wearByStint.keys()].map((st, i) => (
              <Line
                key={st}
                dataKey={`s${st}`}
                stroke={CHART_COLORS[i % CHART_COLORS.length]}
                dot={false}
                isAnimationActive={false}
                connectNulls
                name={`Stint ${st}`}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title="FIELD COMPARISON" style={{ marginTop: 12 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 11 }}>
          <thead>
            <tr style={{ color: C.faint, fontSize: 9 }}>
              {["POS", "DRV", "STINTS", "DEG", "STOPS"].map((h) => (
                <th key={h} style={{ textAlign: "left", padding: "6px 10px" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...grouped.entries()].map(([code, ss]) => {
              const pos = rows.find((r) => r.driver_code === code)?.position;
              return (
                <tr key={code} style={{ borderBottom: `1px solid ${C.border}30` }}>
                  <td style={{ padding: "6px 10px" }}>{pos ?? "—"}</td>
                  <td style={{ padding: "6px 10px" }}>{code}</td>
                  <td style={{ padding: "6px 10px", display: "flex", gap: 6 }}>
                    {ss.map((s) => (
                      <TyreBadge key={s.stint_number} compound={s.compound} size="sm" />
                    ))}
                  </td>
                  <td style={{ padding: "6px 10px" }}>{ss.map((s) => (s.deg_rate_ms_per_lap != null ? s.deg_rate_ms_per_lap.toFixed(0) : "—")).join(" / ")}</td>
                  <td style={{ padding: "6px 10px" }}>{Math.max(0, ss.length - 1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

function TrackInfoTab({
  config,
  circuit,
}: {
  config: SessionConfig;
  circuit: ReturnType<typeof useCircuit>;
}) {
  const cmap = useCircuitMap(config.year, config.round.round_number);
  const [tip, setTip] = useState<string | null>(null);
  return (
    <Panel title={config.round.circuit_name}>
      <div style={{ position: "relative", height: 280 }}>
        {cmap.status === "loading" && <SkeletonPanel rows={6} label="Loading circuit map…" />}
        {cmap.status === "ok" && (
          <CircuitOutline
            map={cmap.data}
            showCorners
            showSectors
            showDrs
            onCornerHover={(t) => setTip(t)}
          />
        )}
        {tip && (
          <div style={{ position: "absolute", bottom: 8, left: 12, background: C.raised, border: `1px solid ${C.border}`, padding: "4px 8px", fontFamily: T.mono, fontSize: 10 }}>
            {tip}
          </div>
        )}
      </div>
      {circuit.chars.status === "ok" && (
        <div style={{ padding: 14 }}>
          {[
            ["Length", circuit.chars.data.lap_length_km ? `${circuit.chars.data.lap_length_km} km` : "—"],
            ["Turns", String(circuit.chars.data.turns ?? "—")],
            ["Pit loss", circuit.chars.data.pit_loss_seconds != null ? `~${circuit.chars.data.pit_loss_seconds}s` : "—"],
            ["Tyre stress", circuit.chars.data.tyre_stress_rating ?? "—"],
          ].map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "7px 0" }}>
              <span style={{ color: C.mist }}>{k}</span>
              <span style={{ fontFamily: T.mono }}>{v}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}
