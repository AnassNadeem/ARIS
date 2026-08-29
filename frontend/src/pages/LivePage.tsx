import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { apiGet, apiPost } from "../api/client";
import type {
  CalendarRound,
  Driver,
  DriverStandings,
  NextRace,
  RecommendResponse,
  StratPlan,
  WeekendSession,
} from "../api/types";
import { useCalendarState } from "../hooks/useCalendarState";
import { useCircuit } from "../hooks/useCircuit";
import { useDrivers } from "../hooks/useDrivers";
import { useStandings } from "../hooks/useStandings";
import { C, T, compoundLetter } from "../theme";
import { Chip, ErrorPanel, initials, ReasoningBar, SkeletonPanel, TyreBadge } from "../components/atoms";
import { RaceBrief } from "../components/RaceBrief";
import { ConsoleView } from "../views/ConsoleView";
import { LiveSessionView } from "../views/LiveSessionView";
import { useFlow } from "../session/FlowContext";
import { currentSeasonYear } from "../years";

const SESSION_ORDER = ["FP1", "FP2", "FP3", "SQ", "S", "Q"] as const;

function formatCompact(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (d > 0) return `${d}D ${h}H ${m}M`;
  if (h > 0) return `${h}H ${m}M`;
  return `${m}M ${s}S`;
}

function Countdown({ seconds }: { seconds: number }) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    setLeft(seconds);
    const id = window.setInterval(() => setLeft((n) => Math.max(0, n - 1)), 1000);
    return () => window.clearInterval(id);
  }, [seconds]);
  return <span>{formatCompact(left)}</span>;
}

function secondsUntil(iso?: string | null): number {
  if (!iso) return 0;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  return Math.max(0, Math.floor((t - Date.now()) / 1000));
}

function roundToNext(year: number, r: CalendarRound, sessions: WeekendSession[]): NextRace {
  return {
    year,
    round_number: r.round_number,
    name: r.name,
    circuit_name: r.circuit_name,
    circuit_key: r.circuit_key,
    country: r.country,
    city: r.city,
    date_race: r.date_race,
    status: r.status === "CANCELLED" ? "CANCELLED" : r.status,
    is_sprint_weekend: r.is_sprint_weekend,
    is_this_weekend: false,
    countdown_seconds: 0,
    days_until: 0,
    hours_until: 0,
    sessions_this_weekend: sessions,
    notes: r.notes ?? [],
    as_of: new Date().toISOString(),
    off_season: false,
  };
}

export function LivePage() {
  const flow = useFlow();
  const cal = useCalendarState(currentSeasonYear());
  const [replay, setReplay] = useState<{ year: number; round: CalendarRound; sessionType: string } | null>(null);
  const next = cal.calendarState && "next" in cal.calendarState ? cal.calendarState.next : undefined;
  const liveKind = cal.calendarState?.type;
  const liveStatus = cal.calendarState && "live" in cal.calendarState ? cal.calendarState.live : undefined;
  const weekendStillOpen = Boolean(
    next?.sessions_this_weekend.some((s) => s.status === "UPCOMING" || s.status === "LIVE"),
  );
  const sessionEnded = Boolean(liveStatus?.session_ended) && !weekendStillOpen;
  const sessionLive =
    liveKind === "LIVE_RACE" ||
    liveKind === "LIVE_QUALI" ||
    liveKind === "LIVE_PRACTICE" ||
    Boolean(next?.sessions_this_weekend.some((s) => s.status === "LIVE") && liveStatus?.is_live);

  if (replay) {
    const target = next && next.year === replay.year && next.round_number === replay.round.round_number
      ? next
      : roundToNext(replay.year, replay.round, []);
    return (
      <LiveSessionView
        next={target}
        replaySessionType={replay.sessionType}
        onBack={() => setReplay(null)}
      />
    );
  }

  if (flow.config?.mode === "live") {
    return <ConsoleView config={flow.config} onDebrief={() => flow.setConfig(null)} />;
  }

  if (cal.status === "loading") {
    return (
      <div style={{ padding: 32 }}>
        <SkeletonPanel rows={8} label="Loading live board…" />
      </div>
    );
  }

  if (cal.status === "error" && !next) {
    return (
      <div style={{ padding: 32 }}>
        <ErrorPanel message={cal.error || "Could not load the live board."} onRetry={cal.retry} />
      </div>
    );
  }

  return (
    <LiveHub
      next={next}
      sessionLive={sessionLive}
      sessionEnded={sessionEnded}
      weekendStillOpen={weekendStillOpen}
      lastSessionEnded={Boolean(liveStatus?.session_ended)}
      endedName={liveStatus?.ended_session_name || liveStatus?.session_name}
      onReplay={(year, round, sessionType) => setReplay({ year, round, sessionType })}
      onEnter={(round, driver, planId) =>
        flow.enterLive(round, driver, { year: next?.year ?? currentSeasonYear(), planId })
      }
    />
  );
}

function LiveHub({
  next,
  sessionLive,
  sessionEnded,
  weekendStillOpen,
  lastSessionEnded,
  endedName,
  onReplay,
  onEnter,
}: {
  next?: NextRace;
  sessionLive: boolean;
  sessionEnded?: boolean;
  weekendStillOpen: boolean;
  lastSessionEnded?: boolean;
  endedName?: string | null;
  onReplay: (year: number, round: CalendarRound, sessionType: string) => void;
  onEnter: (round: CalendarRound, driver: string, planId: string) => void;
}) {
  const year = next?.year ?? currentSeasonYear();
  const [driver, setDriver] = useState<string | null>(null);
  const [planId, setPlanId] = useState("A");
  useEffect(() => {
    if (driver) return;
    if (next?.year === 2026 && next.round_number === 15) setDriver("HAM");
  }, [driver, next?.year, next?.round_number]);
  const drivers = useDrivers(year);
  const standings = useStandings(year);
  const circuit = useCircuit(next?.circuit_key, year);
  const pts = new Map(
    standings.drivers.status === "ok" ? standings.drivers.data.standings.map((s) => [s.driver_code, s]) : [],
  );

  const thisSessions = next?.sessions_this_weekend ?? [];

  const nextRound: CalendarRound | null = next
    ? {
        round_number: next.round_number,
        name: next.name,
        circuit_name: next.circuit_name,
        circuit_key: next.circuit_key,
        country: next.country,
        city: next.city,
        date_race: next.date_race,
        status: next.status,
        is_sprint_weekend: next.is_sprint_weekend,
        notes: next.notes,
      }
    : null;

  const canLock = Boolean(driver && nextRound);

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "28px 24px 48px", maxWidth: 1180, margin: "0 auto" }}>
      <div
        style={{
          padding: "22px 22px 20px",
          marginBottom: 28,
          background: `linear-gradient(135deg, ${C.signalDim} 0%, ${C.panel} 55%, ${C.ink} 100%)`,
          border: `1px solid ${C.borderHi}`,
          borderRadius: 8,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Chip tone={sessionLive ? "caution" : sessionEnded ? "green" : weekendStillOpen ? "signal" : "signal"}>
            {sessionLive ? "LIVE WEEKEND" : sessionEnded ? "SESSION ENDED" : weekendStillOpen ? "RACE WEEKEND" : "LIVE BOARD"}
          </Chip>
          {endedName && (lastSessionEnded || sessionEnded) ? (
            <Chip tone="mist">{endedName.toUpperCase()} CACHED</Chip>
          ) : null}
          <Chip tone="mist" size="xs">
            FP / QUALI / SPRINT REPLAYS
          </Chip>
        </div>
        <div style={{ fontFamily: T.display, fontSize: 46, fontWeight: 900, margin: "12px 0 8px", lineHeight: 0.95 }}>
          {(next?.name ?? "NEXT RACE").toUpperCase()}
        </div>
        <div style={{ fontFamily: T.mono, fontSize: 13, color: C.mist }}>
          {next ? (
            <>
              {next.circuit_name.toUpperCase()} · {next.city ? `${next.city.toUpperCase()} · ` : ""}
              {next.next_session_name ?? "RACE"}
              {next.date_race ? ` · ${next.date_race.slice(0, 10)}` : ""}
            </>
          ) : (
            "Waiting for the next Grand Prix window"
          )}
        </div>
        {next && (
          <div
            style={{
              marginTop: 16,
              display: "inline-flex",
              alignItems: "baseline",
              gap: 10,
              padding: "10px 14px",
              background: C.ink,
              border: `1px solid ${C.border}`,
              borderRadius: 4,
            }}
          >
            <span style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, letterSpacing: "0.12em" }}>
              NEXT SESSION
            </span>
            <span style={{ fontFamily: T.display, fontSize: 28, fontWeight: 800, color: C.signal, letterSpacing: "0.04em" }}>
              <Countdown seconds={next.countdown_seconds} />
            </span>
          </div>
        )}
      </div>

      <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint, letterSpacing: "0.12em", marginBottom: 8 }}>
        THIS WEEKEND · FP / QUALI / SPRINT
      </div>
      <SessionStrip
        sessions={thisSessions}
        year={year}
        round={nextRound}
        onReplay={onReplay}
      />

      <div style={{ fontFamily: T.display, fontSize: 24, fontWeight: 800, margin: "32px 0 8px" }}>
        RUN ARIS FOR THE RACE
      </div>
      <p style={{ fontFamily: T.body, fontSize: 13, color: C.mist, marginBottom: 16, maxWidth: 720 }}>
        Qualifying and practice set the grid. Pick a driver, lock a strategy from 2018–now at this circuit, then sit
        on the pit wall in AUTO. You do not wait for lights out to prepare.
      </p>

      {drivers.status === "loading" && <SkeletonPanel rows={8} label="Loading drivers…" />}
      {drivers.status === "ok" && (
        <DriverPicker drivers={drivers.data.drivers} standings={pts} selected={driver} onSelect={setDriver} />
      )}

      {driver && next && (
        <>
          <div style={{ marginTop: 28 }}>
            <RaceBrief
              circuitKey={next.circuit_key}
              year={next.year}
              circuitName={next.circuit_name}
              driver={driver}
            />
          </div>
          <StrategyPicker
            year={next.year}
            round={next.round_number}
            driver={driver}
            historyN={circuit.history.status === "ok" ? circuit.history.data.years.length : 0}
            circuitName={next.circuit_name}
            sessions={thisSessions}
            selected={planId}
            onSelect={setPlanId}
          />
        </>
      )}

      <button
        disabled={!canLock}
        onClick={() => driver && nextRound && onEnter(nextRound, driver, planId)}
        style={{ ...cta(canLock), width: "100%", marginTop: 24, padding: "16px 24px", fontSize: 18 }}
      >
        {driver ? `LOCK ${driver} · PLAN ${planId} · CONTINUE →` : "SELECT A DRIVER TO CONTINUE"}
      </button>
    </div>
  );
}

function SessionStrip({
  sessions,
  year,
  round,
  onReplay,
}: {
  sessions: WeekendSession[];
  year: number;
  round: CalendarRound | null;
  onReplay: (year: number, round: CalendarRound, sessionType: string) => void;
}) {
  const list = SESSION_ORDER.map((code) => sessions.find((s) => s.session_type === code)).filter(
    (s): s is WeekendSession => Boolean(s),
  );
  if (list.length === 0) {
    return (
      <div style={{ padding: 14, background: C.panel, border: `1px solid ${C.border}`, borderRadius: 6, fontFamily: T.mono, fontSize: 11, color: C.mist }}>
        No practice, qualifying, or sprint sessions listed yet for this weekend.
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(list.length, 6)}, minmax(0, 1fr))`, gap: 8 }}>
      {list.map((s) => {
        const playable = s.status === "COMPLETED" || s.status === "LIVE";
        return (
          <div
            key={`${year}-${s.session_type}`}
            style={{
              padding: 12,
              background: C.panel,
              border: `1px solid ${s.status === "LIVE" ? C.caution : C.border}`,
              borderRadius: 6,
              display: "flex",
              flexDirection: "column",
              gap: 8,
              minHeight: 110,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 700 }}>{s.session_name.toUpperCase()}</span>
              <Chip
                tone={s.status === "LIVE" ? "caution" : s.status === "COMPLETED" ? "green" : "mist"}
                size="xs"
              >
                {s.status}
              </Chip>
            </div>
            <div style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, flex: 1 }}>
              {s.status === "UPCOMING" && s.datetime_utc ? <Countdown seconds={secondsUntil(s.datetime_utc)} /> : s.status === "COMPLETED" ? "Replay ready" : s.status === "LIVE" ? "In progress" : "—"}
            </div>
            <button
              disabled={!playable || !round}
              onClick={() => round && onReplay(year, round, s.session_type)}
              style={{
                padding: "7px 8px",
                cursor: playable && round ? "pointer" : "not-allowed",
                background: playable ? C.signalMid : "transparent",
                border: `1px solid ${playable ? C.signal : C.border}`,
                color: playable ? C.signal : C.faint,
                fontFamily: T.mono,
                fontSize: 10,
                letterSpacing: "0.08em",
              }}
            >
              {s.status === "LIVE" ? "WATCH LIVE" : playable ? "REPLAY" : "WAITING"}
            </button>
          </div>
        );
      })}
    </div>
  );
}

function StrategyPicker({
  year,
  round,
  driver,
  historyN,
  circuitName,
  sessions,
  selected,
  onSelect,
}: {
  year: number;
  round: number;
  driver: string;
  historyN: number;
  circuitName: string;
  sessions: WeekendSession[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  const [plans, setPlans] = useState<StratPlan[] | null>(null);
  const [badge, setBadge] = useState<string | null>(null);
  const [rec, setRec] = useState<RecommendResponse | null>(null);
  useEffect(() => {
    let cancelled = false;
    apiGet<{ plans: StratPlan[] }>(
      `/api/aris/plans?year=${year}&round_number=${round}&driver_code=${driver}`,
      { timeout: 60_000 },
    )
      .then((d) => {
        if (cancelled) return;
        setPlans(d.plans);
        const recPlan = d.plans.find((p) => p.recommended) || d.plans[0];
        if (recPlan) onSelect(recPlan.id);
      })
      .catch(() => {
        if (!cancelled) setPlans([]);
      });
    apiPost<RecommendResponse>(
      "/api/aris/recommend",
      {
        year,
        round_number: round,
        session_type: "R",
        driver_code: driver,
        current_lap: 1,
        mode: "pre_race",
      },
      { timeout: 60_000 },
    )
      .then((r) => {
        if (!cancelled) {
          setRec(r);
          const done = [...sessions].reverse().find((s) => s.status === "COMPLETED");
          setBadge(done ? `UPDATED AFTER ${done.session_name.toUpperCase()}` : "2018–NOW CIRCUIT SAMPLE");
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, round, driver]);

  return (
    <div style={{ marginTop: 28 }}>
      <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal, marginBottom: 10, display: "flex", gap: 8, alignItems: "center" }}>
        POSSIBLE STRATEGIES · {historyN || "historical"} races at {circuitName}
        {badge && (
          <Chip tone="signal" size="xs">
            {badge}
          </Chip>
        )}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
        {(plans || []).slice(0, 3).map((p) => (
          <button
            key={p.id}
            onClick={() => onSelect(p.id)}
            style={{
              padding: 14,
              textAlign: "left",
              cursor: "pointer",
              background: C.panel,
              border: `1px solid ${selected === p.id || p.recommended && selected === p.id ? C.signal : p.recommended ? C.signal : selected === p.id ? C.signal : C.border}`,
              borderRadius: 4,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontFamily: T.display, fontSize: 18, fontWeight: 800 }}>PLAN {p.id}</div>
              {p.recommended && (
                <Chip tone="signal" size="xs">
                  ARIS RECOMMENDED
                </Chip>
              )}
            </div>
            <div style={{ display: "flex", gap: 6, margin: "8px 0" }}>
              <TyreBadge compound={compoundLetter(p.start_compound)} size="sm" />
              {p.pit_compounds.map((c, i) => (
                <TyreBadge key={i} compound={compoundLetter(c)} size="sm" />
              ))}
            </div>
            <p style={{ fontFamily: T.body, fontSize: 11, color: C.mist }}>{p.description}</p>
            {p.pit_cost_s != null && <ReasoningBar paceGain={p.pace_gain_s ?? 0} pitCost={p.pit_cost_s} label />}
          </button>
        ))}
      </div>
      {rec && <p style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginTop: 10 }}>{rec.reasoning}</p>}
    </div>
  );
}

function DriverPicker({
  drivers,
  standings,
  selected,
  onSelect,
}: {
  drivers: Driver[];
  standings: Map<string, DriverStandings["standings"][number]>;
  selected: string | null;
  onSelect: (code: string) => void;
}) {
  const byTeam = useMemo(() => {
    const m = new Map<string, Driver[]>();
    for (const d of drivers) {
      const list = m.get(d.team_name) ?? [];
      list.push(d);
      m.set(d.team_name, list);
    }
    return [...m.entries()];
  }, [drivers]);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 8 }}>
      {byTeam.map(([team, pair]) => (
        <div key={team} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {pair.map((d) => {
            const st = standings.get(d.driver_code);
            return (
              <button
                key={d.driver_code}
                onClick={() => onSelect(d.driver_code)}
                style={{
                  padding: 10,
                  textAlign: "left",
                  cursor: "pointer",
                  display: "flex",
                  gap: 8,
                  alignItems: "center",
                  background: selected === d.driver_code ? C.signalMid : C.panel2,
                  border: `1px solid ${selected === d.driver_code ? C.signal : C.border}`,
                  borderRadius: 4,
                }}
              >
                <div style={{ width: 3, height: 36, background: d.team_colour || C.mist, borderRadius: 2 }} />
                {d.headshot_url ? (
                  <img src={d.headshot_url} alt="" width={28} height={28} style={{ borderRadius: "50%", objectFit: "cover" }} />
                ) : (
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: C.raised,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: T.mono,
                      fontSize: 9,
                      color: C.mist,
                    }}
                  >
                    {initials(d.full_name)}
                  </div>
                )}
                <div>
                  <div style={{ fontFamily: T.mono, fontSize: 12, fontWeight: 700 }}>{d.driver_code}</div>
                  <div style={{ fontFamily: T.body, fontSize: 10, color: C.paper }}>{d.full_name}</div>
                  <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint }}>
                    {d.team_name}
                    {st ? ` · P${st.position}` : ""}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      ))}
    </div>
  );
}

function cta(enabled: boolean): CSSProperties {
  return {
    padding: "12px 20px",
    background: enabled ? C.signal : C.ghost,
    border: "none",
    borderRadius: 4,
    color: enabled ? C.ink : C.faint,
    fontFamily: T.display,
    fontWeight: 800,
    cursor: enabled ? "pointer" : "not-allowed",
  };
}
