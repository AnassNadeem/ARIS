import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import type { CarPosition, LiveTiming, LiveWeather, NextRace } from "../api/types";
import { liveTimingSchema, liveWeatherSchema } from "../api/types";
import { C, SPEED_OPTIONS, T } from "../theme";
import { Chip, Panel } from "../components/atoms";
import { LightsOut } from "../components/LightsOut";
import { TimingTower } from "../components/TimingTower";
import { TrackMap } from "../components/TrackMap";
import { LapTimeChart } from "../components/LapTimeChart";
import { useLiveTiming } from "../hooks/useLiveTiming";
import { useLiveWeather } from "../hooks/useLiveWeather";
import { useReplayClock } from "../hooks/useReplayClock";
import { useSessionLaps } from "../hooks/useSession";
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

function fmt(n: number | null | undefined, digits = 1, unit = "") {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(digits)}${unit}`;
}

function remainingLabel(seconds: number | null | undefined) {
  if (seconds == null) return "";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function clockLabel(ms: number) {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

const SESSION_LABEL: Record<string, string> = {
  FP1: "Free Practice 1",
  FP2: "Free Practice 2",
  FP3: "Free Practice 3",
  SQ: "Sprint Qualifying",
  S: "Sprint",
  Q: "Qualifying",
  R: "Race",
};

type ReplayMeta = {
  session_key: number;
  date_start?: string | null;
  date_end?: string | null;
  session_name?: string | null;
};

type ReplayFrame = {
  session_key: number;
  as_of: string;
  elapsed_s: number;
  duration_s: number;
  date_start: string | null;
  date_end: string | null;
  timing: LiveTiming;
  weather: LiveWeather;
  positions: { positions: CarPosition[]; circuit_path?: { x: number[]; y: number[] } | null };
  source?: string;
  quali_phase?: string | null;
  quali_windows?: { id: string; label: string; start_s: number; end_s: number }[];
};

type ReplayPhase = "idle" | "lights" | "play" | "paused" | "ended";

export function LiveSessionView({
  next,
  onBack,
  replaySessionType,
}: {
  next: NextRace;
  onBack: () => void;
  replaySessionType?: string;
}) {
  const [replayMeta, setReplayMeta] = useState<ReplayMeta | null>(null);
  const [keyErr, setKeyErr] = useState<string | null>(null);
  const [phase, setPhase] = useState<ReplayPhase>("idle");
  const [speed, setSpeed] = useState<(typeof SPEED_OPTIONS)[number]>("1×");
  const [frame, setFrame] = useState<ReplayFrame | null>(null);
  const [frameErr, setFrameErr] = useState<string | null>(null);
  const [loadingFrame, setLoadingFrame] = useState(false);
  const [focusCode, setFocusCode] = useState<string | undefined>(undefined);
  const [showAnalysis, setShowAnalysis] = useState(false);
  const isReplay = Boolean(replaySessionType);
  const replayKey = replayMeta?.session_key ?? null;

  useEffect(() => {
    if (!replaySessionType) return;
    let cancelled = false;
    setReplayMeta(null);
    setKeyErr(null);
    setPhase("idle");
    setFrame(null);
    apiGet<ReplayMeta>(
      `/api/live/session-key?year=${next.year}&round_number=${next.round_number}&session_type=${replaySessionType}`,
      { timeout: 30_000, cache: false },
    )
      .then((data) => {
        if (!cancelled) setReplayMeta(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) setKeyErr(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, [replaySessionType, next.year, next.round_number]);

  const clock = useReplayClock({
    startIso: replayMeta?.date_start ?? null,
    endIso:
      replayMeta?.date_end ??
      (replayMeta?.date_start
        ? new Date(Date.parse(replayMeta.date_start) + 90 * 60_000).toISOString()
        : null),
    running: isReplay && phase === "play",
    speed,
  });
  const asOfRef = useRef(clock.asOf);
  asOfRef.current = clock.asOf;
  const frameRef = useRef(frame);
  frameRef.current = frame;
  const fetchGen = useRef(0);

  const liveActive = !isReplay;
  const { timing: liveTiming, status: liveStatus, error: liveError } = useLiveTiming(liveActive);
  const { weather: liveWeather } = useLiveWeather(liveActive);

  const fetchFrame = useCallback(
    async (asOf: string) => {
      if (replayKey == null) return;
      const id = ++fetchGen.current;
      if (!frameRef.current) setLoadingFrame(true);
      try {
        const data = await apiGet<ReplayFrame>(
          `/api/live/replay-frame?session_key=${replayKey}&as_of=${encodeURIComponent(asOf)}&year=${next.year}&round_number=${next.round_number}`,
          { timeout: 60_000, cache: false },
        );
        if (id !== fetchGen.current) return;
        liveTimingSchema.parse(data.timing);
        liveWeatherSchema.parse(data.weather);
        setFrame(data);
        setFrameErr(null);
      } catch (err) {
        if (id !== fetchGen.current) return;
        setFrameErr(err instanceof Error ? err.message : String(err));
      } finally {
        if (id === fetchGen.current) setLoadingFrame(false);
      }
    },
    [replayKey, next.year, next.round_number],
  );

  useEffect(() => {
    if (!isReplay || replayKey == null || !replayMeta?.date_start) return;
    const start = replayMeta.date_start;
    void apiGet<ReplayFrame>(
      `/api/live/replay-frame?session_key=${replayKey}&as_of=${encodeURIComponent(start)}&year=${next.year}&round_number=${next.round_number}`,
      { timeout: 120_000, cache: false },
    ).catch(() => undefined);
  }, [isReplay, replayKey, replayMeta?.date_start, next.year, next.round_number]);

  const seekKey = phase === "play" ? "run" : String(Math.round(clock.elapsedMs / 800));
  const pollMs = frame?.source === "openf1" ? 900 : frame?.source === "fastf1" ? 280 : 1000;
  useEffect(() => {
    if (!isReplay || replayKey == null) return;
    if (phase === "idle" || phase === "lights") return;
    const asOf = asOfRef.current;
    if (asOf) void fetchFrame(asOf);
    if (phase !== "play") return;
    const id = window.setInterval(() => {
      if (!frameRef.current) return;
      const nextAsOf = asOfRef.current;
      if (nextAsOf) void fetchFrame(nextAsOf);
    }, pollMs);
    return () => window.clearInterval(id);
  }, [isReplay, replayKey, phase, fetchFrame, seekKey, pollMs]);

  useEffect(() => {
    if (phase === "play" && clock.ended) setPhase("ended");
  }, [phase, clock.ended]);

  const timing = isReplay ? frame?.timing ?? null : liveTiming;
  const weather = isReplay ? frame?.weather ?? null : liveWeather;
  const rows = timing?.rows ?? [];
  const sessionType = (liveStatus?.session_type || replaySessionType || "SQ").toUpperCase();
  const quali = sessionType !== "R" && sessionType !== "S";
  const title = (
    replayMeta?.session_name ||
    liveStatus?.session_name ||
    SESSION_LABEL[replaySessionType || ""] ||
    "SESSION"
  ).toUpperCase();
  const error = isReplay ? keyErr || frameErr : liveError;
  const progress = clock.durationMs > 0 ? Math.min(100, (clock.elapsedMs / clock.durationMs) * 100) : 0;
  const remainingReplay =
    clock.durationMs > 0 ? Math.max(0, Math.round((clock.durationMs - clock.elapsedMs) / 1000)) : null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, background: C.ink }}>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 16px",
          borderBottom: `1px solid ${C.border}`,
          flexWrap: "wrap",
        }}
      >
        <button
          onClick={onBack}
          style={{
            background: "transparent",
            border: `1px solid ${C.border}`,
            color: C.mist,
            fontFamily: T.mono,
            fontSize: 10,
            padding: "6px 10px",
            cursor: "pointer",
          }}
        >
          ← BACK
        </button>
        <Chip tone={isReplay ? "blue" : "caution"}>{isReplay ? "REPLAY" : "LIVE"}</Chip>
        {isReplay && <Chip tone="blue">{(frame?.source || "FASTF1").toUpperCase()}</Chip>}
        <div style={{ fontFamily: T.display, fontWeight: 800, fontSize: 18 }}>{title}</div>
        <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist }}>
          {next.circuit_name.toUpperCase()}
          {!isReplay && remainingLabel(liveStatus?.session_remaining_seconds)
            ? ` · ${remainingLabel(liveStatus?.session_remaining_seconds)}`
            : ""}
          {isReplay && remainingReplay != null ? ` · ${remainingLabel(remainingReplay)}` : ""}
        </div>
        {isReplay && phase !== "idle" && phase !== "lights" && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: 8 }}>
            <button
              onClick={() => {
                if (phase === "ended" || clock.ended) {
                  clock.setElapsedMs(0);
                  setPhase("play");
                  return;
                }
                setPhase(phase === "play" ? "paused" : "play");
              }}
              style={{
                background: C.signal,
                border: "none",
                color: C.ink,
                fontFamily: T.display,
                fontWeight: 800,
                fontSize: 11,
                padding: "6px 12px",
                cursor: "pointer",
                letterSpacing: "0.08em",
              }}
            >
              {phase === "play" ? "PAUSE" : clock.ended ? "RESTART" : "PLAY"}
            </button>
            <span style={{ fontFamily: T.mono, fontSize: 9, color: C.faint }}>SPEED</span>
            {SPEED_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                style={{
                  padding: "3px 7px",
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
              onClick={() => setShowAnalysis((v) => !v)}
              style={{
                marginLeft: 8,
                padding: "3px 8px",
                cursor: "pointer",
                background: showAnalysis ? C.signalMid : "transparent",
                border: `1px solid ${showAnalysis ? C.signal : C.border}`,
                color: showAnalysis ? C.signal : C.faint,
                fontFamily: T.mono,
                fontSize: 10,
              }}
            >
              ANALYSIS
            </button>
          </div>
        )}
        <div style={{ marginLeft: "auto", fontFamily: T.mono, fontSize: 10, color: C.faint }}>
          {isReplay ? "REPLAY · ARIS OFF" : "VIEW ONLY · ARIS OFF"}
        </div>
      </header>

      {isReplay && phase !== "idle" && phase !== "lights" && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "6px 16px",
            borderBottom: `1px solid ${C.border}`,
          }}
        >
          <div style={{ fontFamily: T.mono, fontSize: 10, color: C.mist, minWidth: 64 }}>
            {clockLabel(clock.elapsedMs)}
          </div>
          <div
            style={{ flex: 1, height: 6, background: C.ghost, borderRadius: 3, cursor: "pointer" }}
            onClick={(ev) => {
              const rect = ev.currentTarget.getBoundingClientRect();
              const frac = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
              clock.setElapsedMs(frac * clock.durationMs);
              if (phase === "ended") setPhase("paused");
            }}
          >
            <div style={{ width: `${progress}%`, height: "100%", background: C.signal, borderRadius: 3 }} />
          </div>
          <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, minWidth: 64, textAlign: "right" }}>
            {clockLabel(clock.durationMs)}
          </div>
        </div>
      )}

      {isReplay && quali && (frame?.quali_windows?.length || 0) > 0 && phase !== "idle" && phase !== "lights" && (
        <div style={{ display: "flex", gap: 8, padding: "6px 16px", borderBottom: `1px solid ${C.border}` }}>
          {(frame?.quali_windows || []).map((win) => {
            const active = frame?.quali_phase === win.id;
            return (
              <button
                key={win.id}
                onClick={() => {
                  clock.setElapsedMs(win.start_s * 1000);
                  setPhase("paused");
                }}
                style={{
                  padding: "4px 10px",
                  cursor: "pointer",
                  background: active ? C.signalMid : "transparent",
                  border: `1px solid ${active ? C.signal : C.border}`,
                  color: active ? C.signal : C.mist,
                  fontFamily: T.mono,
                  fontSize: 11,
                  letterSpacing: "0.08em",
                }}
              >
                {win.label}
              </button>
            );
          })}
        </div>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(7, minmax(0, 1fr))",
          gap: 8,
          padding: "8px 16px",
          borderBottom: `1px solid ${C.border}`,
          fontFamily: T.mono,
          fontSize: 10,
        }}
      >
        <Wx label="AIR" value={fmt(weather?.air_temp, 1, "°")} />
        <Wx label="TRACK" value={fmt(weather?.track_temp, 1, "°")} />
        <Wx label="HUMID" value={fmt(weather?.humidity, 0, "%")} />
        <Wx label="PRESS" value={fmt(weather?.pressure, 1, " mb")} />
        <Wx label="WIND" value={`${fmt(weather?.wind_speed, 1, " m/s")} ${fmt(weather?.wind_direction, 0, "°")}`} />
        <Wx
          label="RAIN"
          value={weather?.rainfall ? "YES" : weather?.rainfall === false ? "NO" : "—"}
          alert={!!weather?.rainfall}
        />
        <Wx label="CARS" value={String(rows.length || "—")} />
      </div>

      {error && (
        <div style={{ padding: "8px 16px", color: C.signal, fontFamily: T.mono, fontSize: 11 }}>{error}</div>
      )}

      <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(320px, 420px) 1fr", gridTemplateRows: showAnalysis ? "1fr 240px" : "1fr", position: "relative" }}>
        <div style={{ borderRight: `1px solid ${C.border}`, minHeight: 0, gridRow: "1" }}>
          <TimingTower
            rows={rows}
            loading={isReplay ? loadingFrame && !frame : !liveTiming && !error}
            quali={quali}
            splitQ={quali && Boolean(rows.some((r) => r.q1_ms || r.q2_ms || r.q3_ms))}
            focus={focusCode}
            onSelect={setFocusCode}
          />
        </div>
        <div style={{ minHeight: 0, position: "relative", gridRow: "1" }}>
          <TrackMap
            year={next.year}
            round={next.round_number}
            cars={rows}
            focusCode={focusCode}
            hiddenCars={[]}
            lap={frame?.timing.current_lap ?? liveStatus?.current_lap ?? 1}
            live
            speed={isReplay ? speed : "1×"}
            replaySessionKey={isReplay ? null : replayKey}
            liveFeed={
              isReplay
                ? {
                    positions: frame?.positions.positions ?? [],
                    circuitPath: frame?.positions.circuit_path ?? null,
                  }
                : undefined
            }
          />
          {isReplay && (phase === "idle" || phase === "lights") && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(7,10,14,0.78)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 18,
                zIndex: 6,
              }}
            >
              {phase === "lights" ? (
                <LightsOut
                  play
                  onComplete={() => {
                    const start = replayMeta?.date_start;
                    if (start) void fetchFrame(start);
                    setPhase("play");
                  }}
                />
              ) : (
                <>
                  <div style={{ fontFamily: T.display, fontWeight: 900, fontSize: 28, letterSpacing: "0.08em" }}>
                    SESSION COMPLETE
                  </div>
                  <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist }}>
                    Lights out, then replay from the start · 1×–50×
                  </div>
                  <button
                    disabled={replayKey == null}
                    onClick={() => {
                      clock.setElapsedMs(0);
                      setPhase("lights");
                    }}
                    style={{
                      background: replayKey == null ? C.ghost : C.signal,
                      border: "none",
                      color: C.ink,
                      fontFamily: T.display,
                      fontWeight: 900,
                      fontSize: 18,
                      padding: "14px 36px",
                      cursor: replayKey == null ? "wait" : "pointer",
                      letterSpacing: "0.14em",
                    }}
                  >
                    {replayKey == null ? "LOADING…" : "START"}
                  </button>
                </>
              )}
            </div>
          )}
          {isReplay && loadingFrame && !frame && phase === "play" && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(7,10,14,0.45)",
                zIndex: 5,
                fontFamily: T.mono,
                fontSize: 12,
                color: C.signal,
                letterSpacing: "0.12em",
              }}
            >
              LOADING SESSION DATA…
            </div>
          )}
        </div>
        {showAnalysis && (
          <div style={{ gridColumn: "1 / -1", borderTop: `1px solid ${C.border}`, minHeight: 0, overflow: "auto" }}>
            <SessionReplayAnalysis
              year={next.year}
              round={next.round_number}
              sessionType={sessionType}
              focus={focusCode || rows[0]?.driver_code}
              codes={rows.map((r) => r.driver_code)}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function Wx({ label, value, alert }: { label: string; value: string; alert?: boolean }) {
  return (
    <div>
      <div style={{ color: C.faint, letterSpacing: "0.08em" }}>{label}</div>
      <div style={{ color: alert ? C.signal : C.paper, fontWeight: 700, marginTop: 2 }}>{value}</div>
    </div>
  );
}

function SessionReplayAnalysis({
  year,
  round,
  sessionType,
  focus,
  codes,
}: {
  year: number;
  round: number;
  sessionType: string;
  focus?: string;
  codes: string[];
}) {
  const laps = useSessionLaps(year, round, sessionType, true);
  const [driver, setDriver] = useState(focus || codes[0] || "");
  const [tel, setTel] = useState<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] } | null>(null);
  useEffect(() => {
    if (focus) setDriver(focus);
  }, [focus]);
  useEffect(() => {
    if (!driver) return;
    setTel(null);
    apiGet<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] }>(
      `/api/session/${year}/${round}/${sessionType}/telemetry/${driver}`,
      { timeout: 120_000 },
    )
      .then(setTel)
      .catch(() => setTel(null));
  }, [year, round, sessionType, driver]);
  const colourBy = new Map(codes.map((c) => [c, C.signal]));
  const upTo =
    laps.status === "ok" && laps.data
      ? Math.max(1, ...laps.data.laps.map((l) => l.lap_number))
      : 1;
  const traces =
    tel?.distance.map((d, i) => ({
      dist: Math.round(d),
      speed: tel.speed[i],
      throttle: tel.throttle[i],
      brake: tel.brake[i],
    })) ?? [];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, padding: 8, height: "100%" }}>
      <div style={{ minHeight: 0, overflow: "auto" }}>
        <LapTimeChart
          laps={laps}
          upTo={upTo}
          focus={driver}
          colourBy={colourBy}
          pitLaps={[]}
          scRanges={[]}
        />
      </div>
      <Panel title={`TELEMETRY · ${driver || "—"}`}>
        <div style={{ padding: "6px 10px", display: "flex", gap: 8, alignItems: "center" }}>
          <select
            value={driver}
            onChange={(e) => setDriver(e.target.value)}
            style={{
              background: C.panel2,
              color: C.paper,
              border: `1px solid ${C.border}`,
              fontFamily: T.mono,
              fontSize: 11,
              padding: "4px 6px",
            }}
          >
            {codes.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <span style={{ fontFamily: T.mono, fontSize: 9, color: C.faint }}>FASTEST LAP · SPEED / THROTTLE / BRAKE</span>
        </div>
        {traces.length === 0 ? (
          <div style={{ padding: 12, fontFamily: T.mono, fontSize: 11, color: C.mist }}>Loading traces…</div>
        ) : (
          <ResponsiveContainer width="100%" height={170}>
            <LineChart data={traces}>
              <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
              <XAxis dataKey="dist" tick={{ fill: C.faint, fontSize: 9 }} />
              <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
              <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
              <Line dataKey="speed" stroke={C.signal} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
        {traces.length > 0 && (
          <ResponsiveContainer width="100%" height={90}>
            <AreaChart data={traces}>
              <Area dataKey="throttle" stroke={C.green} fill={C.green} fillOpacity={0.25} isAnimationActive={false} />
              <Area dataKey="brake" stroke={C.signal} fill={C.signal} fillOpacity={0.2} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </Panel>
    </div>
  );
}
