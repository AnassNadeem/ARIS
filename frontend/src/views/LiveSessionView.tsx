import { useCallback, useEffect, useMemo, useRef, useState, type MutableRefObject } from "react";
import { apiGet } from "../api/client";
import type { CarPosition, LiveTiming, LiveTimingRow, LiveWeather, NextRace, SessionResultsResponse } from "../api/types";
import { liveTimingSchema, liveWeatherSchema, sessionResultsSchema } from "../api/types";
import { ReplayAnalytics } from "./ReplayAnalytics";
import { C, SPEED_OPTIONS, T } from "../theme";
import { Chip, Panel, formatMs } from "../components/atoms";
import { WetConditionsBadge } from "../components/WetHeuristicBadge";
import { LightsOut } from "../components/LightsOut";
import { TimingTower } from "../components/TimingTower";
import { TrackMap } from "../components/TrackMap";
import { LapTimeChart } from "../components/LapTimeChart";
import { useLiveTiming } from "../hooks/useLiveTiming";
import { useLiveWeather } from "../hooks/useLiveWeather";
import { useReplayClock } from "../hooks/useReplayClock";
import { useLiveLaps, useLiveTelemetry } from "../hooks/useLiveLaps";
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
  quali_windows?: { id: string; label: string; start_s: number; end_s: number }[];
  green_flag_s?: number | null;
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
  positions: {
    positions: CarPosition[];
    circuit_path?: { x: number[]; y: number[] } | null;
    pit_lane_x?: number[];
    pit_lane_y?: number[];
    markers?: { kind: string; x: number; y: number; label: string }[];
    drs_segments?: number[][];
  };
  source?: string;
  quali_phase?: string | null;
  quali_windows?: { id: string; label: string; start_s: number; end_s: number }[];
  green_flag_s?: number | null;
  session_flag?: string | null;
  ready?: boolean;
};

type ReplayPhase = "idle" | "lights" | "play" | "paused" | "ended";

export function LiveSessionView({
  next,
  onBack,
  replaySessionType,
  initialSegment,
}: {
  next: NextRace;
  onBack: () => void;
  replaySessionType?: string;
  initialSegment?: string | null;
}) {
  const [replayMeta, setReplayMeta] = useState<ReplayMeta | null>(null);
  const [keyErr, setKeyErr] = useState<string | null>(null);
  const [phase, setPhase] = useState<ReplayPhase>("idle");
  const [speed, setSpeed] = useState<(typeof SPEED_OPTIONS)[number]>("1×");
  const [frame, setFrame] = useState<ReplayFrame | null>(null);
  const [frameErr, setFrameErr] = useState<string | null>(null);
  const [loadingFrame, setLoadingFrame] = useState(false);
  const [focusCode, setFocusCode] = useState<string | undefined>(undefined);
  const [page, setPage] = useState<"track" | "analysis">("track");
  const [gridByCode, setGridByCode] = useState<Map<string, number>>(new Map());
  const [ff1GiveUp, setFf1GiveUp] = useState(false);
  const [segId, setSegId] = useState<string | null>(null);
  const [packReady, setPackReady] = useState(false);
  const [packMetaReady, setPackMetaReady] = useState(false);
  const [outlineOk, setOutlineOk] = useState(false);
  const [seekTick, setSeekTick] = useState(0);
  const [promoteReplay, setPromoteReplay] = useState<string | null>(null);
  const effectiveReplay = replaySessionType || promoteReplay || undefined;
  const isReplay = Boolean(effectiveReplay);
  const replayKey = replayMeta?.session_key ?? null;
  const sessionTypeUpper = (effectiveReplay || "").toUpperCase();
  const isQualiReplay = sessionTypeUpper === "Q" || sessionTypeUpper === "SQ";
  const isGrandPrixReplay = sessionTypeUpper === "R";
  const isRaceReplay = sessionTypeUpper === "R" || sessionTypeUpper === "S";
  const qualiWindows = frame?.quali_windows?.length
    ? frame.quali_windows
    : replayMeta?.quali_windows ?? [];
  const activeWin =
    qualiWindows.find((w) => w.id === (segId || frame?.quali_phase)) || qualiWindows[0] || null;

  useEffect(() => {
    let cancelled = false;
    setOutlineOk(false);
    apiGet<{ x?: number[] }>(`/api/circuit/${next.year}/${next.round_number}/map`, { timeout: 120_000 })
      .then((data) => {
        if (!cancelled) setOutlineOk((data.x?.length ?? 0) >= 2);
      })
      .catch(() => {
        if (!cancelled) setOutlineOk(false);
      });
    return () => {
      cancelled = true;
    };
  }, [next.year, next.round_number]);

  useEffect(() => {
    let cancelled = false;
    apiGet<SessionResultsResponse>(`/api/session/${next.year}/${next.round_number}/R/results`, {
      schema: sessionResultsSchema,
      timeout: 90_000,
    })
      .catch(() =>
        apiGet<SessionResultsResponse>(`/api/race/${next.year}/${next.round_number}/results`, {
          schema: sessionResultsSchema,
          timeout: 90_000,
        }),
      )
      .then((data) => {
        if (cancelled) return;
        const m = new Map<string, number>();
        for (const row of data.results) {
          if (row.grid != null) m.set(row.driver_code, row.grid);
        }
        setGridByCode(m);
      })
      .catch(() => {
        if (!cancelled) setGridByCode(new Map());
      });
    return () => {
      cancelled = true;
    };
  }, [next.year, next.round_number]);

  useEffect(() => {
    if (!effectiveReplay) return;
    let cancelled = false;
    setReplayMeta(null);
    setKeyErr(null);
    setPhase("idle");
    setFrame(null);
    setPackReady(false);
    setPackMetaReady(false);
    setSegId(null);
    const load = async () => {
      try {
        const data = await apiGet<ReplayMeta>(
          `/api/live/session-key?year=${next.year}&round_number=${next.round_number}&session_type=${effectiveReplay}`,
          { timeout: 60_000 },
        );
        if (cancelled) return;
        setReplayMeta(data);
        if (initialSegment) setSegId(initialSegment);
        else if (data.quali_windows?.length) setSegId(data.quali_windows[0].id);
        try {
          const ready = await apiGet<ReplayMeta>(
            `/api/live/replay-ready?session_key=${data.session_key}&year=${next.year}&round_number=${next.round_number}`,
            { timeout: 180_000 },
          );
          if (cancelled) return;
          setReplayMeta({
            ...data,
            ...ready,
            session_key: data.session_key,
            quali_windows: ready.quali_windows?.length ? ready.quali_windows : data.quali_windows,
            green_flag_s: ready.green_flag_s ?? data.green_flag_s,
          });
        } catch {
          /* first frame still waits on the pack */
        }
        if (!cancelled) setPackMetaReady(true);
      } catch (err: unknown) {
        if (!cancelled) setKeyErr(err instanceof Error ? err.message : String(err));
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [effectiveReplay, next.year, next.round_number, initialSegment]);

  const sessionStartMs = replayMeta?.date_start ? Date.parse(replayMeta.date_start) : Number.NaN;
  const raceStartS = frame?.green_flag_s ?? replayMeta?.green_flag_s ?? null;
  const clockStartIso =
    isQualiReplay && Number.isFinite(sessionStartMs) && activeWin
      ? new Date(sessionStartMs + activeWin.start_s * 1000).toISOString()
      : isRaceReplay && Number.isFinite(sessionStartMs) && raceStartS != null && raceStartS > 0
        ? new Date(sessionStartMs + raceStartS * 1000).toISOString()
        : replayMeta?.date_start ?? null;
  const clockEndIso =
    isQualiReplay && Number.isFinite(sessionStartMs) && activeWin
      ? new Date(sessionStartMs + activeWin.end_s * 1000).toISOString()
      : replayMeta?.date_end ??
        (replayMeta?.date_start
          ? new Date(Date.parse(replayMeta.date_start) + (isRaceReplay ? 3 * 3600_000 : 60 * 60_000)).toISOString()
          : null);
  const clock = useReplayClock({
    startIso: clockStartIso,
    endIso: clockEndIso,
    running: isReplay && phase === "play" && Boolean(frame),
    speed,
  });
  const asOfRef = useRef(clock.asOf);
  asOfRef.current = clock.asOf;
  const frameRef = useRef(frame);
  frameRef.current = frame;
  const segIdRef = useRef(segId);
  segIdRef.current = segId;
  const sessionGen = useRef(0);
  const wantAsOf = useRef<string | null>(null);
  const inFlight = useRef(false);
  const flightGen = useRef(0);

  const liveActive = !isReplay;
  const { timing: liveTiming, status: liveStatus, error: liveError } = useLiveTiming(liveActive);
  const { weather: liveWeather } = useLiveWeather(liveActive);

  useEffect(() => {
    sessionGen.current += 1;
    wantAsOf.current = null;
  }, [replayKey]);

  useEffect(() => {
    if (!isReplay) return;
    setFf1GiveUp(false);
    const id = window.setTimeout(() => setFf1GiveUp(true), 180_000);
    return () => window.clearTimeout(id);
  }, [isReplay, replayKey]);

  const fetchFrame = useCallback(
    async (asOf: string, opts?: { retry?: boolean }) => {
      if (replayKey == null) return;
      wantAsOf.current = asOf;
      if (inFlight.current) return;
      inFlight.current = true;
      const gen = sessionGen.current;
      flightGen.current = gen;
      if (!frameRef.current) setLoadingFrame(true);
      try {
        while (wantAsOf.current && gen === sessionGen.current) {
          const target = wantAsOf.current;
          wantAsOf.current = null;
          const path = `/api/live/replay-frame?session_key=${replayKey}&as_of=${encodeURIComponent(target)}&year=${next.year}&round_number=${next.round_number}`;
          const maxAttempts = opts?.retry ? 4 : 1;
          let lastErr: unknown;
          let applied = false;
          for (let attempt = 0; attempt < maxAttempts; attempt++) {
            try {
              const data = await apiGet<ReplayFrame>(path, {
                timeout: opts?.retry ? 180_000 : 45_000,
              });
              if (gen !== sessionGen.current) return;
              liveTimingSchema.parse(data.timing);
              liveWeatherSchema.parse(data.weather);
              setFrame(data);
              setFrameErr(null);
              setPackReady(true);
              if (data.quali_windows?.length && !segIdRef.current) setSegId(data.quali_windows[0].id);
              applied = true;
              lastErr = null;
              break;
            } catch (err) {
              lastErr = err;
              const msg = err instanceof Error ? err.message : String(err);
              if (
                !opts?.retry ||
                !/503|warming up|timeout|aborted|Retry shortly/i.test(msg) ||
                attempt === maxAttempts - 1
              ) {
                break;
              }
              await new Promise((r) => window.setTimeout(r, 1200 * (attempt + 1)));
            }
          }
          if (!applied && lastErr && gen === sessionGen.current && !frameRef.current) {
            setFrameErr(lastErr instanceof Error ? lastErr.message : String(lastErr));
          }
        }
      } finally {
        if (flightGen.current === gen) inFlight.current = false;
        if (gen === sessionGen.current) {
          setLoadingFrame(false);
          if (wantAsOf.current) void fetchFrame(wantAsOf.current);
        }
      }
    },
    [replayKey, next.year, next.round_number],
  );

  useEffect(() => {
    if (!isReplay || replayKey == null || !replayMeta?.date_start) return;
    setPackReady(false);
  }, [isReplay, replayKey, replayMeta?.date_start]);

  useEffect(() => {
    if (!isReplay || replayKey == null || !packMetaReady) return;
    const start = clockStartIso || replayMeta?.date_start;
    if (!start) return;
    void fetchFrame(start, { retry: true });
  }, [isReplay, replayKey, packMetaReady, clockStartIso, replayMeta?.date_start, fetchFrame]);

  const pollMs = frame?.source === "fastf1" ? 90 : frame?.source === "openf1" ? 320 : 400;
  useEffect(() => {
    if (!isReplay || replayKey == null) return;
    if (phase !== "play") return;
    const asOf = asOfRef.current;
    if (asOf) void fetchFrame(asOf);
    const id = window.setInterval(() => {
      if (!frameRef.current) return;
      const nextAsOf = asOfRef.current;
      if (nextAsOf) void fetchFrame(nextAsOf);
    }, pollMs);
    return () => window.clearInterval(id);
  }, [isReplay, replayKey, phase, fetchFrame, pollMs]);

  useEffect(() => {
    if (!isReplay || replayKey == null || seekTick === 0) return;
    if (phase === "idle" || phase === "lights") return;
    const asOf = asOfRef.current;
    if (asOf) void fetchFrame(asOf);
  }, [isReplay, replayKey, seekTick, phase, fetchFrame]);

  useEffect(() => {
    if (!isReplay || replayKey == null) return;
    if (phase !== "paused" && phase !== "ended") return;
    const asOf = asOfRef.current;
    if (asOf) void fetchFrame(asOf);
  }, [isReplay, replayKey, phase, fetchFrame]);

  useEffect(() => {
    if (phase !== "play" || !clock.ended) return;
    if (isQualiReplay && activeWin) {
      const idx = qualiWindows.findIndex((w) => w.id === activeWin.id);
      if (idx >= 0 && idx < qualiWindows.length - 1) {
        setSegId(qualiWindows[idx + 1].id);
        return;
      }
    }
    setPhase("ended");
  }, [phase, clock.ended, isQualiReplay, activeWin, qualiWindows]);

  const timing = isReplay ? frame?.timing ?? null : liveTiming;
  const weather = isReplay ? frame?.weather ?? null : liveWeather;
  const isRaining = Boolean(timing?.rainfall || weather?.rainfall);
  const rows = (timing?.rows ?? []).filter(
    (r) => !(next.year === 2026 && next.round_number === 15 && r.driver_code === "HAD"),
  );
  const sessionType = (liveStatus?.session_type || effectiveReplay || "SQ").toUpperCase();
  const quali = sessionType !== "R" && sessionType !== "S";
  const title = (
    replayMeta?.session_name ||
    liveStatus?.session_name ||
    SESSION_LABEL[effectiveReplay || ""] ||
    next.next_session_name ||
    "SESSION"
  ).toUpperCase();
  const liveEnded = !isReplay && Boolean(liveStatus?.session_ended || (liveStatus && !liveStatus.is_live && rows.length > 0));
  const waitingLive = !isReplay && !liveEnded && rows.length === 0;
  const replayFeed = useMemo(
    () =>
      isReplay
        ? {
            positions: (frame?.positions.positions ?? []).filter((p) => p.driver_code !== "HAD" || next.round_number !== 15 || next.year !== 2026),
            circuitPath: frame?.positions.circuit_path ?? null,
            pitLaneX: frame?.positions.pit_lane_x,
            pitLaneY: frame?.positions.pit_lane_y,
            markers: frame?.positions.markers,
            sessionFlag: frame?.session_flag ?? null,
          }
        : undefined,
    [isReplay, frame?.positions, frame?.session_flag, next.round_number, next.year],
  );
  const hasMap = Boolean(
    (frame?.positions.circuit_path?.x?.length ?? 0) >= 2 ||
      (frame?.positions.pit_lane_x?.length ?? 0) >= 2,
  );
  const replayLoadingHint =
    ff1GiveUp && frame?.source !== "fastf1"
      ? "FastF1 GPS is not available for this session yet. Try a completed practice, quali, or sprint."
      : frame && frame.source !== "fastf1"
        ? "Loading FastF1 GPS — replay starts when telemetry is ready…"
        : "Loading map, cars, and session pack…";
  const startReady = Boolean(
    packReady &&
      packMetaReady &&
      replayKey != null &&
      frame &&
      frame.source === "fastf1" &&
      (hasMap || outlineOk) &&
      ((frame.timing.rows?.length ?? 0) > 0 || (frame.positions.positions?.length ?? 0) > 0) &&
      !loadingFrame,
  );
  const fastest = rows.find((r) => r.fastest_lap) ?? null;
  const error = isReplay
    ? keyErr || frameErr
    : liveEnded || (liveError && /502|503/.test(liveError))
      ? null
      : liveError;
  const progress = clock.durationMs > 0 ? Math.min(100, (clock.elapsedMs / clock.durationMs) * 100) : 0;
  const remainingReplay =
    clock.durationMs > 0 ? Math.max(0, Math.round((clock.durationMs - clock.elapsedMs) / 1000)) : null;

  const startReplay = () => {
    if (!startReady) return;
    clock.setElapsedMs(0);
    setPhase("lights");
  };

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
        {isRaining && <WetConditionsBadge />}
        {isReplay && <Chip tone="blue">{(frame?.source || "FASTF1").toUpperCase()}</Chip>}
        {!isReplay && <Chip tone="caution">OPENF1</Chip>}
        <div style={{ fontFamily: T.display, fontWeight: 800, fontSize: 18 }}>{title}</div>
        <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist }}>
          {next.circuit_name.toUpperCase()}
          {!isReplay && remainingLabel(liveStatus?.session_remaining_seconds)
            ? ` · ${remainingLabel(liveStatus?.session_remaining_seconds)}`
            : ""}
          {isReplay && remainingReplay != null ? ` · ${remainingLabel(remainingReplay)}` : ""}
          {` · LAP ${timing?.current_lap ?? (rows.reduce((m, r) => Math.max(m, r.lap_number ?? 0), 0) || "—")}`}
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
          </div>
        )}
        {isReplay && (
        <div style={{ marginLeft: 8, display: "flex", gap: 0, border: `1px solid ${C.border}` }}>
          {(["track", "analysis"] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              style={{
                padding: "3px 10px",
                cursor: "pointer",
                background: page === p ? C.signalMid : "transparent",
                border: "none",
                color: page === p ? C.signal : C.faint,
                fontFamily: T.mono,
                fontSize: 10,
                letterSpacing: "0.08em",
              }}
            >
              {p === "track" ? "TRACK" : "ANALYTICS"}
            </button>
          ))}
        </div>
        )}
        <div style={{ marginLeft: "auto", fontFamily: T.mono, fontSize: 10, color: C.faint }}>
          {isGrandPrixReplay ? "RACE REPLAY · ARIS OFF" : isReplay ? "SESSION REPLAY · ARIS OFF" : "VIEW ONLY · ARIS OFF"}
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
              setSeekTick((n) => n + 1);
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
            const active = (segId || frame?.quali_phase) === win.id;
            return (
              <button
                key={win.id}
                onClick={() => {
                  setSegId(win.id);
                  clock.setElapsedMs(0);
                  setSeekTick((n) => n + 1);
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
          gridTemplateColumns: "repeat(8, minmax(0, 1fr))",
          gap: 8,
          padding: "6px 16px",
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
        <Wx
          label="FL"
          value={
            fastest
              ? `${fastest.driver_code} ${formatMs(fastest.best_lap_ms ?? fastest.last_lap_ms)}`
              : "—"
          }
        />
      </div>

      {error && (
        <div style={{ padding: "8px 16px", color: C.signal, fontFamily: T.mono, fontSize: 11 }}>{error}</div>
      )}

      <div
        style={{
          flex: 1,
          minHeight: 0,
          display: "grid",
          gridTemplateColumns:
            page === "analysis"
              ? "1fr"
              : isRaceReplay
                ? "minmax(0, 1fr) minmax(360px, 460px)"
                : "minmax(220px, 260px) 1fr",
          gridTemplateRows: "1fr",
          position: "relative",
        }}
      >
        {page === "analysis" && isGrandPrixReplay && isReplay ? (
          <div style={{ minHeight: 0, overflow: "auto" }}>
            <ReplayAnalytics
              year={next.year}
              round={next.round_number}
              focus={focusCode || rows[0]?.driver_code}
              codes={rows.map((r) => r.driver_code)}
              colours={new Map(rows.map((r) => [r.driver_code, r.team_colour || C.signal]))}
            />
          </div>
        ) : page === "analysis" ? (
          <div style={{ minHeight: 0, overflow: "auto" }}>
            <SessionReplayAnalysis
              year={next.year}
              round={next.round_number}
              sessionType={sessionType}
              focus={focusCode || rows[0]?.driver_code}
              codes={rows.map((r) => r.driver_code)}
              colours={new Map(rows.map((r) => [r.driver_code, r.team_colour || C.signal]))}
              live={!isReplay}
              replayKey={isReplay ? replayKey : null}
              asOfRef={asOfRef}
              rows={rows}
            />
          </div>
        ) : (
          <>
        {isRaceReplay ? (
          <div style={{ minHeight: 0, position: "relative", gridRow: "1", borderRight: `1px solid ${C.border}` }}>
            <TrackMap
              year={next.year}
              round={next.round_number}
              cars={rows}
              focusCode={focusCode}
              hiddenCars={next.year === 2026 && next.round_number === 15 ? ["HAD"] : []}
              lap={frame?.timing.current_lap ?? liveStatus?.current_lap ?? 1}
              live={!isReplay}
              playing={!isReplay || phase === "play"}
              speed={isReplay ? speed : "1×"}
              replaySessionKey={isReplay ? replayKey : null}
              replaySource={frame?.source}
              replayClock={
                isReplay && clockStartIso
                  ? {
                      startMs: Date.parse(clockStartIso),
                      elapsedRef: clock.elapsedRef,
                      playing: phase === "play",
                    }
                  : undefined
              }
              liveFeed={replayFeed}
              onSelect={setFocusCode}
            />
            {(isReplay
              ? frame?.session_flag === "SC" || frame?.session_flag === "VSC" || frame?.session_flag === "YELLOW" || frame?.session_flag === "RED"
              : liveStatus?.session_flag === "SC" ||
                liveStatus?.session_flag === "VSC" ||
                liveStatus?.session_flag === "YELLOW" ||
                liveStatus?.session_flag === "RED") && (
              <div
                style={{
                  position: "absolute",
                  top: 10,
                  left: "50%",
                  transform: "translateX(-50%)",
                  zIndex: 8,
                  background: C.cautionDim,
                  border: `1px solid ${C.caution}`,
                  color: C.caution,
                  fontFamily: T.display,
                  fontWeight: 900,
                  fontSize: 14,
                  letterSpacing: "0.14em",
                  padding: "6px 14px",
                }}
              >
                {((isReplay ? frame?.session_flag : liveStatus?.session_flag) === "VSC" && "VIRTUAL SAFETY CAR") ||
                  ((isReplay ? frame?.session_flag : liveStatus?.session_flag) === "YELLOW" && "YELLOW FLAG") ||
                  ((isReplay ? frame?.session_flag : liveStatus?.session_flag) === "RED" && "RED FLAG") ||
                  "SAFETY CAR"}
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
            {isReplay && (phase === "idle" || phase === "lights") && (
              <ReplayStartOverlay
                phase={phase}
                startReady={startReady}
                loadingHint={replayLoadingHint}
                readyHint={isRaceReplay ? "Lights out, then lap 1." : "Replay from the start"}
                onStart={startReplay}
                onLightsDone={() => {
                  if (frameRef.current) setPhase("play");
                }}
              />
            )}
          </div>
        ) : null}
        <div style={{ borderLeft: isRaceReplay ? `1px solid ${C.border}` : undefined, borderRight: isRaceReplay ? undefined : `1px solid ${C.border}`, minHeight: 0, gridRow: "1" }}>
          <TimingTower
            rows={rows}
            loading={isReplay ? loadingFrame && !frame : !liveTiming && !error}
            quali={quali}
            splitQ={quali && Boolean(rows.some((r) => r.q1_ms || r.q2_ms || r.q3_ms))}
            focus={focusCode}
            onSelect={setFocusCode}
            gridByCode={gridByCode}
          />
        </div>
        {!isRaceReplay && (
        <div style={{ minHeight: 0, position: "relative", gridRow: "1" }}>
          <TrackMap
            year={next.year}
            round={next.round_number}
            cars={rows}
            focusCode={focusCode}
            hiddenCars={next.year === 2026 && next.round_number === 15 ? ["HAD"] : []}
            lap={frame?.timing.current_lap ?? liveStatus?.current_lap ?? 1}
            live={!isReplay}
            playing={!isReplay || phase === "play"}
            speed={isReplay ? speed : "1×"}
            replaySessionKey={isReplay ? replayKey : null}
            replaySource={frame?.source}
            replayClock={
              isReplay && clockStartIso
                ? {
                    startMs: Date.parse(clockStartIso),
                    elapsedRef: clock.elapsedRef,
                    playing: phase === "play",
                  }
                : undefined
            }
            liveFeed={replayFeed}
            onSelect={setFocusCode}
          />
          {(isReplay
            ? frame?.session_flag === "SC" || frame?.session_flag === "VSC" || frame?.session_flag === "YELLOW" || frame?.session_flag === "RED"
            : liveStatus?.session_flag === "SC" ||
              liveStatus?.session_flag === "VSC" ||
              liveStatus?.session_flag === "YELLOW" ||
              liveStatus?.session_flag === "RED") && (
            <div
              style={{
                position: "absolute",
                top: 10,
                left: "50%",
                transform: "translateX(-50%)",
                zIndex: 8,
                background: C.cautionDim,
                border: `1px solid ${C.caution}`,
                color: C.caution,
                fontFamily: T.display,
                fontWeight: 900,
                fontSize: 14,
                letterSpacing: "0.14em",
                padding: "6px 14px",
              }}
            >
              {((isReplay ? frame?.session_flag : liveStatus?.session_flag) === "VSC" && "VIRTUAL SAFETY CAR") ||
                ((isReplay ? frame?.session_flag : liveStatus?.session_flag) === "YELLOW" && "YELLOW FLAG") ||
                ((isReplay ? frame?.session_flag : liveStatus?.session_flag) === "RED" && "RED FLAG") ||
                "SAFETY CAR"}
            </div>
          )}
          {liveEnded && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(7,10,14,0.78)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 14,
                zIndex: 7,
                textAlign: "center",
                padding: 24,
              }}
            >
              <div style={{ fontFamily: T.display, fontWeight: 900, fontSize: 28, letterSpacing: "0.08em" }}>
                {title} HAS ENDED
              </div>
              <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, maxWidth: 440 }}>
                LIVE IS OVER. CACHING REPLAY — THE CLOCK WILL START WHEN THE PACK IS READY.
              </div>
              <button
                onClick={() => setPromoteReplay(liveStatus?.ended_session_type || liveStatus?.session_type || "S")}
                style={{
                  background: C.signal,
                  border: "none",
                  color: C.ink,
                  fontFamily: T.display,
                  fontWeight: 900,
                  fontSize: 16,
                  padding: "12px 28px",
                  cursor: "pointer",
                  letterSpacing: "0.12em",
                }}
              >
                OPEN REPLAY
              </button>
            </div>
          )}
          {waitingLive && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: "rgba(7,10,14,0.72)",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: 12,
                zIndex: 6,
                textAlign: "center",
                padding: 24,
              }}
            >
              <div style={{ fontFamily: T.display, fontWeight: 900, fontSize: 26, letterSpacing: "0.08em" }}>
                {title} WILL START AS THE DATA COMES IN
              </div>
              <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, maxWidth: 440 }}>
                OPENF1 LIVE · POSITIONS UPDATE AS CARS APPEAR ON THE FEED
              </div>
            </div>
          )}
          {isReplay && (phase === "idle" || phase === "lights") && (
            <ReplayStartOverlay
              phase={phase}
              startReady={startReady}
              loadingHint={replayLoadingHint}
              readyHint={
                isQualiReplay && activeWin
                  ? `${activeWin.label} · ${Math.round((activeWin.end_s - activeWin.start_s) / 60)} min`
                  : "Lights out, then replay from the start"
              }
              onStart={startReplay}
              onLightsDone={() => {
                if (frameRef.current) setPhase("play");
              }}
            />
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
        )}
          </>
        )}
      </div>
    </div>
  );
}

function ReplayStartOverlay({
  phase,
  startReady,
  loadingHint,
  readyHint,
  onStart,
  onLightsDone,
}: {
  phase: ReplayPhase;
  startReady: boolean;
  loadingHint: string;
  readyHint: string;
  onStart: () => void;
  onLightsDone: () => void;
}) {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "rgba(7,10,14,0.62)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 16,
        zIndex: 6,
        textAlign: "center",
        padding: 20,
      }}
    >
      {phase === "lights" ? (
        <LightsOut play onComplete={onLightsDone} />
      ) : (
        <>
          <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, maxWidth: 360 }}>
            {startReady ? readyHint : loadingHint}
          </div>
          <button
            type="button"
            disabled={!startReady}
            onClick={onStart}
            style={{
              background: startReady ? C.signal : C.ghost,
              border: "none",
              color: C.ink,
              fontFamily: T.display,
              fontWeight: 900,
              fontSize: 20,
              padding: "14px 40px",
              cursor: startReady ? "pointer" : "not-allowed",
              letterSpacing: "0.16em",
              display: "inline-flex",
              alignItems: "center",
              gap: 12,
              opacity: startReady ? 1 : 0.7,
            }}
          >
            {!startReady && (
              <span
                style={{
                  width: 16,
                  height: 16,
                  border: `2px solid ${C.ink}`,
                  borderTopColor: "transparent",
                  borderRadius: "50%",
                  animation: "arisSpin 0.7s linear infinite",
                }}
              />
            )}
            {startReady ? "START" : "LOADING…"}
          </button>
        </>
      )}
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
  colours,
  live,
  replayKey,
  asOfRef,
  rows,
}: {
  year: number;
  round: number;
  sessionType: string;
  focus?: string;
  codes: string[];
  colours?: Map<string, string>;
  live?: boolean;
  replayKey?: number | null;
  asOfRef?: MutableRefObject<string | null>;
  rows?: LiveTimingRow[];
}) {
  const sessionLaps = useSessionLaps(year, round, sessionType, !live && replayKey == null);
  const liveLaps = useLiveLaps(Boolean(live) || replayKey != null, replayKey, asOfRef);
  const laps = live || replayKey != null ? liveLaps : sessionLaps;
  const [driver, setDriver] = useState(focus || codes[0] || "");
  const [histTel, setHistTel] = useState<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] } | null>(null);
  const liveTel = useLiveTelemetry(driver, (Boolean(live) || replayKey != null) && Boolean(driver), replayKey, asOfRef);
  useEffect(() => {
    if (focus) setDriver(focus);
  }, [focus]);
  useEffect(() => {
    if (live || replayKey != null || !driver) return;
    setHistTel(null);
    apiGet<{ distance: number[]; speed: number[]; throttle: number[]; brake: number[] }>(
      `/api/session/${year}/${round}/${sessionType}/telemetry/${driver}`,
      { timeout: 120_000 },
    )
      .then(setHistTel)
      .catch(() => setHistTel(null));
  }, [year, round, sessionType, driver, live, replayKey]);
  const tel = live || replayKey != null ? liveTel : histTel;
  const colourBy = colours && colours.size ? colours : new Map(codes.map((c) => [c, C.signal]));
  const upTo =
    laps.status === "ok" && laps.data
      ? Math.max(1, ...laps.data.laps.map((l) => l.lap_number))
      : 1;
  const flLap =
    laps.status === "ok" && laps.data
      ? laps.data.laps.reduce<(typeof laps.data.laps)[number] | null>((best, lap) => {
          if (lap.lap_time_ms == null) return best;
          if (best == null || lap.lap_time_ms < best.lap_time_ms!) return lap;
          return best;
        }, null)
      : null;
  const traces =
    tel?.distance.map((d, i) => ({
      dist: Math.round(d * 10) / 10,
      speed: tel.speed[i],
      throttle: tel.throttle[i],
      brake: tel.brake[i],
    })) ?? [];
  const liveRow = rows?.find((r) => r.driver_code === driver);
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gridTemplateRows: "auto 1fr",
        gap: 10,
        padding: 12,
        height: "100%",
        minHeight: 0,
      }}
    >
      <div style={{ gridColumn: "1 / -1", display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <select
          value={driver}
          onChange={(e) => setDriver(e.target.value)}
          style={{
            background: C.panel2,
            color: C.paper,
            border: `1px solid ${C.border}`,
            fontFamily: T.mono,
            fontSize: 12,
            padding: "6px 8px",
          }}
        >
          {codes.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <Wx label="THROTTLE" value={liveRow?.throttle_pct != null ? `${Math.round(liveRow.throttle_pct)}%` : "—"} />
        <Wx label="BRAKE" value={liveRow?.brake_pct != null ? `${Math.round(liveRow.brake_pct)}%` : "—"} />
        <Wx label="SPEED" value={liveRow?.speed_kph != null ? `${Math.round(liveRow.speed_kph)} km/h` : "—"} />
        <Wx label="DRS" value={liveRow?.drs_open ? "OPEN" : liveRow ? "CLOSED" : "—"} />
        <span style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, marginLeft: "auto" }}>
          {live
            ? "LIVE · SPEED / THROTTLE / BRAKE"
            : replayKey != null
              ? "FASTF1 REPLAY · SPEED / THROTTLE / BRAKE"
              : "FASTEST LAP · SPEED / THROTTLE / BRAKE"}
        </span>
      </div>
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
      <Panel
        title={`TELEMETRY · ${driver || "—"}`}
        right={
          flLap ? (
            <span style={{ fontFamily: T.mono, fontSize: 10, color: C.purple }}>
              FASTEST {flLap.driver_code} {formatMs(flLap.lap_time_ms)} L{flLap.lap_number}
            </span>
          ) : null
        }
      >
        {traces.length === 0 ? (
          <div style={{ padding: 12, fontFamily: T.mono, fontSize: 11, color: C.mist }}>Loading traces…</div>
        ) : (
          <>
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={traces}>
                <CartesianGrid stroke={C.ghost} strokeDasharray="2 4" vertical={false} />
                <XAxis dataKey="dist" tick={{ fill: C.faint, fontSize: 9 }} />
                <YAxis tick={{ fill: C.faint, fontSize: 9 }} />
                <Tooltip contentStyle={{ background: C.panel2, border: `1px solid ${C.border}` }} />
                <Line dataKey="speed" stroke={C.signal} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
            <ResponsiveContainer width="100%" height={140}>
              <AreaChart data={traces}>
                <Area dataKey="throttle" stroke={C.green} fill={C.green} fillOpacity={0.25} isAnimationActive={false} />
                <Area dataKey="brake" stroke={C.signal} fill={C.signal} fillOpacity={0.2} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </>
        )}
      </Panel>
    </div>
  );
}
