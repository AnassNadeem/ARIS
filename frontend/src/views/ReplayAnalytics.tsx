import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiGet } from "../api/client";
import type {
  LapsResponse,
  SessionResultsResponse,
  TyreStrategyResponse,
} from "../api/types";
import { lapsSchema, sessionResultsSchema, tyreStrategySchema } from "../api/types";
import { Chip, Panel, SkeletonPanel, TyreBadge, formatMs } from "../components/atoms";
import { C, T, compoundLetter } from "../theme";

const CHART = [C.signal, C.blue, C.green, C.purple, C.caution, "#FF8000", "#E8ECF0", "#4A5560"];

function ChartTip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string | number }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: C.panel2, border: `1px solid ${C.border}`, padding: "8px 10px", fontFamily: T.mono, fontSize: 10 }}>
      <div style={{ color: C.faint, marginBottom: 4 }}>{label}</div>
      {payload.slice(0, 8).map((p) => (
        <div key={p.name} style={{ color: p.color }}>
          {p.name} {typeof p.value === "number" ? p.value.toFixed(3) : p.value}
        </div>
      ))}
    </div>
  );
}

export function ReplayAnalytics({
  year,
  round,
  focus,
  codes,
  colours,
}: {
  year: number;
  round: number;
  focus?: string;
  codes: string[];
  colours: Map<string, string>;
}) {
  const [laps, setLaps] = useState<LapsResponse | null>(null);
  const [pos, setPos] = useState<{ lap: number; [k: string]: number }[] | null>(null);
  const [gaps, setGaps] = useState<{ lap: number; [k: string]: number }[] | null>(null);
  const [tyres, setTyres] = useState<TyreStrategyResponse | null>(null);
  const [race, setRace] = useState<SessionResultsResponse | null>(null);
  const [quali, setQuali] = useState<SessionResultsResponse | null>(null);
  const [sector, setSector] = useState<1 | 2 | 3>(1);
  const [telMode, setTelMode] = useState<"speed" | "throttle" | "gear">("speed");
  const [telDriver, setTelDriver] = useState(focus || codes[0] || "");
  const [tel, setTel] = useState<{ dist: number; speed: number; throttle: number; gear: number }[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (focus) setTelDriver(focus);
  }, [focus]);

  useEffect(() => {
    let cancelled = false;
    setErr(null);
    const load = async () => {
      try {
        const [lapData, posData, gapData, tyreData, raceData, qualiData] = await Promise.all([
          apiGet<LapsResponse>(`/api/session/${year}/${round}/R/laps`, { schema: lapsSchema, timeout: 120_000 }),
          apiGet<{ laps: { lap: number; positions: Record<string, number> }[] }>(
            `/api/race/${year}/${round}/position-history`,
            { timeout: 120_000 },
          ).catch(() => ({ laps: [] })),
          apiGet<{ laps: { lap: number; gaps: Record<string, number> }[] }>(
            `/api/race/${year}/${round}/gap-history`,
            { timeout: 120_000 },
          ).catch(() => ({ laps: [] })),
          apiGet<TyreStrategyResponse>(`/api/race/${year}/${round}/tyre-strategy`, {
            schema: tyreStrategySchema,
            timeout: 120_000,
          }).catch(() => null),
          apiGet<SessionResultsResponse>(`/api/session/${year}/${round}/R/results`, {
            schema: sessionResultsSchema,
            timeout: 90_000,
          }).catch(() =>
            apiGet<SessionResultsResponse>(`/api/race/${year}/${round}/results`, {
              schema: sessionResultsSchema,
              timeout: 90_000,
            }).catch(() => null),
          ),
          apiGet<SessionResultsResponse>(`/api/session/${year}/${round}/Q/results`, {
            schema: sessionResultsSchema,
            timeout: 90_000,
          }).catch(() => null),
        ]);
        if (cancelled) return;
        setLaps(lapData);
        setPos(posData.laps.map((x) => ({ lap: x.lap, ...x.positions })));
        setGaps(gapData.laps.map((x) => ({ lap: x.lap, ...x.gaps })));
        setTyres(tyreData);
        setRace(raceData);
        setQuali(qualiData);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [year, round]);

  useEffect(() => {
    if (!telDriver) return;
    let cancelled = false;
    setTel([]);
    apiGet<{ distance: number[]; speed: number[]; throttle: number[]; gear?: number[] }>(
      `/api/session/${year}/${round}/R/telemetry/${telDriver}`,
      { timeout: 120_000 },
    )
      .then((d) => {
        if (cancelled) return;
        setTel(
          d.distance.map((dist, i) => ({
            dist: Math.round(dist),
            speed: d.speed[i] ?? 0,
            throttle: d.throttle[i] ?? 0,
            gear: d.gear?.[i] ?? 0,
          })),
        );
      })
      .catch(() => {
        if (!cancelled) setTel([]);
      });
    return () => {
      cancelled = true;
    };
  }, [year, round, telDriver]);

  const colour = (code: string, i: number) => colours.get(code) || CHART[i % CHART.length];
  const series = codes.slice(0, 12);
  const cleanLaps = useMemo(
    () =>
      (laps?.laps ?? []).filter(
        (l) => l.lap_time_ms != null && !l.pit_in_lap && !l.pit_out_lap && l.lap_time_ms > 40_000 && l.lap_time_ms < 180_000,
      ),
    [laps],
  );

  const lapRows = useMemo(() => {
    const byLap = new Map<number, Record<string, number>>();
    for (const lap of cleanLaps) {
      const row = byLap.get(lap.lap_number) ?? { lap: lap.lap_number };
      row[lap.driver_code] = (lap.lap_time_ms as number) / 1000;
      byLap.set(lap.lap_number, row);
    }
    return [...byLap.values()].sort((a, b) => a.lap - b.lap);
  }, [cleanLaps]);

  const sectorRows = useMemo(() => {
    const key = sector === 1 ? "sector1_ms" : sector === 2 ? "sector2_ms" : "sector3_ms";
    const byLap = new Map<number, Record<string, number>>();
    for (const lap of cleanLaps) {
      const ms = lap[key];
      if (ms == null) continue;
      const row = byLap.get(lap.lap_number) ?? { lap: lap.lap_number };
      row[lap.driver_code] = ms / 1000;
      byLap.set(lap.lap_number, row);
    }
    return [...byLap.values()].sort((a, b) => a.lap - b.lap);
  }, [cleanLaps, sector]);

  const fastest = useMemo(() => {
    const best = new Map<string, { ms: number; lap: number }>();
    for (const lap of cleanLaps) {
      const prev = best.get(lap.driver_code);
      if (!prev || (lap.lap_time_ms as number) < prev.ms) {
        best.set(lap.driver_code, { ms: lap.lap_time_ms as number, lap: lap.lap_number });
      }
    }
    return [...best.entries()]
      .map(([code, v]) => ({ code, ...v }))
      .sort((a, b) => a.ms - b.ms);
  }, [cleanLaps]);

  const distribution = useMemo(() => {
    const by = new Map<string, number[]>();
    for (const lap of cleanLaps) {
      const list = by.get(lap.driver_code) ?? [];
      list.push((lap.lap_time_ms as number) / 1000);
      by.set(lap.driver_code, list);
    }
    return [...by.entries()]
      .map(([code, times]) => {
        const sorted = [...times].sort((a, b) => a - b);
        const mean = times.reduce((s, n) => s + n, 0) / times.length;
        const variance = times.reduce((s, n) => s + (n - mean) ** 2, 0) / times.length;
        return {
          code,
          median: sorted[Math.floor(sorted.length / 2)],
          mean,
          std: Math.sqrt(variance),
          n: times.length,
        };
      })
      .sort((a, b) => a.std - b.std);
  }, [cleanLaps]);

  const deltaRows = useMemo(() => {
    const qPos = new Map((quali?.results ?? []).map((r) => [r.driver_code, r.position ?? r.grid ?? null]));
    return (race?.results ?? [])
      .map((r) => {
        const q = qPos.get(r.driver_code);
        const racePos = r.position ?? null;
        const grid = r.grid ?? q;
        const from = q ?? grid;
        return {
          code: r.driver_code,
          quali: from,
          race: racePos,
          delta: from != null && racePos != null ? from - racePos : null,
        };
      })
      .filter((r) => r.delta != null)
      .sort((a, b) => (b.delta ?? 0) - (a.delta ?? 0));
  }, [quali, race]);

  const maxLap = useMemo(() => {
    const fromStints = Math.max(0, ...(tyres?.stints.map((s) => s.lap_end) ?? [0]));
    const fromLaps = Math.max(0, ...cleanLaps.map((l) => l.lap_number));
    return Math.max(fromStints, fromLaps, 1);
  }, [tyres, cleanLaps]);

  const stintsByDriver = useMemo(() => {
    const m = new Map<string, NonNullable<TyreStrategyResponse["stints"]>>();
    for (const s of tyres?.stints ?? []) {
      m.set(s.driver_code, [...(m.get(s.driver_code) ?? []), s]);
    }
    const order = race?.results.map((r) => r.driver_code) ?? [...m.keys()];
    return order.filter((c) => m.has(c)).map((c) => ({ code: c, stints: m.get(c)! }));
  }, [tyres, race]);

  if (err && !laps) {
    return <div style={{ padding: 20, fontFamily: T.mono, color: C.caution }}>{err}</div>;
  }
  if (!laps) {
    return <SkeletonPanel rows={10} label="Loading race analytics…" />;
  }

  return (
    <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 14 }}>
      <Panel title="POSITION CHANGE">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={pos ?? []}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis reversed domain={[1, 20]} tick={{ fill: C.faint, fontSize: 9 }} width={28} />
            <Tooltip content={<ChartTip />} />
            {series.map((c, i) => (
              <Line
                key={c}
                type="stepAfter"
                dataKey={c}
                stroke={colour(c, i)}
                strokeWidth={c === focus ? 2.4 : 1.2}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="LAP TIME COMPARISON">
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={lapRows}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis domain={["dataMin - 0.3", "dataMax + 0.4"]} tick={{ fill: C.faint, fontSize: 9 }} width={42} />
            <Tooltip content={<ChartTip />} />
            {series.map((c, i) => (
              <Line
                key={c}
                type="monotone"
                dataKey={c}
                stroke={colour(c, i)}
                strokeWidth={c === focus ? 2.4 : 1.2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel title="TYRE STRATEGY">
        <div style={{ padding: "10px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
          {stintsByDriver.map(({ code, stints }) => (
            <div key={code} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontFamily: T.mono, fontSize: 11, width: 36, color: code === focus ? C.signal : C.paper }}>
                {code}
              </span>
              <div style={{ flex: 1, height: 16, background: C.ghost, position: "relative", borderRadius: 2 }}>
                {stints.map((s, i) => {
                  const left = ((s.lap_start - 1) / maxLap) * 100;
                  const width = Math.max(1.2, ((s.lap_end - s.lap_start + 1) / maxLap) * 100);
                  const letter = compoundLetter(s.compound);
                  const col = letter === "S" ? C.soft : letter === "M" ? C.medium : letter === "H" ? C.hard : letter === "I" ? C.inter : C.wet;
                  return (
                    <div
                      key={`${code}-${i}`}
                      title={`${code} ${letter} L${s.lap_start}–${s.lap_end}`}
                      style={{
                        position: "absolute",
                        left: `${left}%`,
                        width: `${width}%`,
                        top: 0,
                        bottom: 0,
                        background: col,
                        opacity: 0.85,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontFamily: T.mono,
                        fontSize: 8,
                        color: C.ink,
                        fontWeight: 700,
                      }}
                    >
                      {letter}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="GAP TO RACE LEADER">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={gaps ?? []}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis tick={{ fill: C.faint, fontSize: 9 }} width={36} />
            <Tooltip content={<ChartTip />} />
            {series.map((c, i) => (
              <Line
                key={c}
                type="monotone"
                dataKey={c}
                stroke={colour(c, i)}
                strokeWidth={c === focus ? 2.4 : 1.2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <Panel
        title={`SECTOR TIMES · S${sector}`}
        right={
          <div style={{ display: "flex", gap: 4 }}>
            {([1, 2, 3] as const).map((n) => (
              <button
                key={n}
                onMouseEnter={() => setSector(n)}
                onFocus={() => setSector(n)}
                onClick={() => setSector(n)}
                style={{
                  padding: "3px 8px",
                  cursor: "pointer",
                  background: sector === n ? C.signalMid : "transparent",
                  border: `1px solid ${sector === n ? C.signal : C.border}`,
                  color: sector === n ? C.signal : C.mist,
                  fontFamily: T.mono,
                  fontSize: 10,
                }}
              >
                S{n}
              </button>
            ))}
          </div>
        }
      >
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={sectorRows}>
            <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
            <XAxis dataKey="lap" tick={{ fill: C.faint, fontSize: 9 }} />
            <YAxis domain={["dataMin - 0.15", "dataMax + 0.2"]} tick={{ fill: C.faint, fontSize: 9 }} width={42} />
            <Tooltip content={<ChartTip />} />
            {series.map((c, i) => (
              <Line
                key={c}
                type="monotone"
                dataKey={c}
                stroke={colour(c, i)}
                strokeWidth={c === focus ? 2.4 : 1.2}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Panel title="FASTEST LAP">
          <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: T.mono, fontSize: 12 }}>
            <thead>
              <tr style={{ color: C.faint, fontSize: 9 }}>
                {["#", "DRV", "TIME", "LAP"].map((h) => (
                  <th key={h} style={{ textAlign: "left", padding: "8px 10px" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {fastest.slice(0, 12).map((r, i) => (
                <tr key={r.code} style={{ borderBottom: `1px solid ${C.border}40`, background: r.code === focus ? C.signalMid : "transparent" }}>
                  <td style={{ padding: "7px 10px", color: i === 0 ? C.purple : C.mist }}>{i + 1}</td>
                  <td style={{ padding: "7px 10px", color: i === 0 ? C.purple : C.paper, fontWeight: 700 }}>{r.code}</td>
                  <td style={{ padding: "7px 10px" }}>{formatMs(r.ms)}</td>
                  <td style={{ padding: "7px 10px", color: C.faint }}>{r.lap}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="PACE CONSISTENCY">
          <div style={{ padding: "8px 12px 4px", fontFamily: T.mono, fontSize: 9, color: C.faint }}>
            STANDARD DEVIATION OF CLEAN LAPS · LOWER IS STEADIER
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={distribution.slice(0, 12)} layout="vertical" margin={{ left: 8 }}>
              <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" horizontal={false} />
              <XAxis type="number" tick={{ fill: C.faint, fontSize: 9 }} />
              <YAxis type="category" dataKey="code" tick={{ fill: C.faint, fontSize: 10 }} width={36} />
              <Tooltip content={<ChartTip />} />
              <Bar dataKey="std" isAnimationActive={false}>
                {distribution.slice(0, 12).map((d, i) => (
                  <Cell key={d.code} fill={colour(d.code, i)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel
        title={`FASTEST LAP TRACE · ${telDriver || "—"}`}
        right={
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <select
              value={telDriver}
              onChange={(e) => setTelDriver(e.target.value)}
              style={{ background: C.raised, color: C.paper, border: `1px solid ${C.border}`, fontFamily: T.mono, fontSize: 11, padding: "3px 6px" }}
            >
              {(codes.length ? codes : fastest.map((f) => f.code)).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            {(["speed", "throttle", "gear"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setTelMode(m)}
                style={{
                  padding: "3px 8px",
                  cursor: "pointer",
                  background: telMode === m ? C.signalMid : "transparent",
                  border: `1px solid ${telMode === m ? C.signal : C.border}`,
                  color: telMode === m ? C.signal : C.mist,
                  fontFamily: T.mono,
                  fontSize: 10,
                  textTransform: "uppercase",
                }}
              >
                {m}
              </button>
            ))}
          </div>
        }
      >
        {tel.length === 0 ? (
          <div style={{ padding: 16, fontFamily: T.mono, fontSize: 11, color: C.mist }}>Loading speed / throttle / gear…</div>
        ) : (
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={tel}>
              <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="dist" tick={{ fill: C.faint, fontSize: 9 }} />
              <YAxis tick={{ fill: C.faint, fontSize: 9 }} width={40} />
              <Tooltip content={<ChartTip />} />
              <Line dataKey={telMode} stroke={telMode === "throttle" ? C.green : telMode === "gear" ? C.blue : C.signal} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </Panel>

      <Panel title="QUALI → RACE DELTA">
        {deltaRows.length === 0 ? (
          <div style={{ padding: 16, fontFamily: T.mono, fontSize: 11, color: C.mist }}>Qualifying results are still loading or unavailable for this weekend.</div>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={deltaRows}>
              <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="code" tick={{ fill: C.faint, fontSize: 9 }} />
              <YAxis tick={{ fill: C.faint, fontSize: 9 }} width={28} />
              <Tooltip content={<ChartTip />} />
              <Bar dataKey="delta" isAnimationActive={false}>
                {deltaRows.map((d) => (
                  <Cell key={d.code} fill={(d.delta ?? 0) > 0 ? C.green : (d.delta ?? 0) < 0 ? C.caution : C.mist} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </Panel>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {fastest.slice(0, 6).map((r) => (
          <Chip key={r.code} tone={r.code === focus ? "signal" : "mist"} size="xs">
            {r.code} {formatMs(r.ms)}
          </Chip>
        ))}
        {stintsByDriver[0] && <TyreBadge compound={stintsByDriver[0].stints[0]?.compound} size="sm" />}
      </div>
    </div>
  );
}
