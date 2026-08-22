import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import type { CalendarRound, Driver, DriverStandings, NextRace, RecommendResponse, StratPlan, WeekendSession } from "../api/types";
import { useCalendarState } from "../hooks/useCalendarState";
import { useDrivers } from "../hooks/useDrivers";
import { useStandings } from "../hooks/useStandings";
import { useCircuit } from "../hooks/useCircuit";
import { C, T } from "../theme";
import { Chip, ErrorPanel, initials, ReasoningBar, SkeletonPanel, TyreBadge } from "../components/atoms";
import { RaceBrief } from "../components/RaceBrief";
import { ConsoleView } from "../views/ConsoleView";
import { LiveSessionView } from "../views/LiveSessionView";
import { useFlow } from "../session/FlowContext";
import { compoundLetter } from "../theme";

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

export function LivePage() {
  const flow = useFlow();
  const cal = useCalendarState(2026);
  const [viewData, setViewData] = useState(false);
  const [replayType, setReplayType] = useState<string | null>(null);
  const next = cal.calendarState && "next" in cal.calendarState ? cal.calendarState.next : undefined;
  const liveKind = cal.calendarState?.type;
  const sessionLive =
    liveKind === "LIVE_RACE" ||
    liveKind === "LIVE_QUALI" ||
    liveKind === "LIVE_PRACTICE" ||
    Boolean(next?.sessions_this_weekend.some((s) => s.status === "LIVE"));
  const viewOnly = liveKind === "LIVE_QUALI" || liveKind === "LIVE_PRACTICE";

  if (replayType && next) {
    return (
      <LiveSessionView next={next} replaySessionType={replayType} onBack={() => setReplayType(null)} />
    );
  }

  if (viewData && sessionLive && next) {
    return <LiveSessionView next={next} onBack={() => setViewData(false)} />;
  }

  if (sessionLive && flow.config?.mode === "live" && !viewOnly) {
    return <ConsoleView config={flow.config} onDebrief={() => undefined} />;
  }

  if (cal.status === "loading") {
    return (
      <div style={{ padding: 32 }}>
        <SkeletonPanel rows={8} label="Loading live session state…" />
      </div>
    );
  }
  if (cal.status === "error") {
    return <ErrorPanel message={`Could not load live state. ${cal.error}`} onRetry={cal.retry} />;
  }

  const hoursUntil = next?.hours_until ?? 999;
  const raceWeekend = !!(next && (next.is_this_weekend || next.days_until <= 7 || hoursUntil <= 96));

  if ((sessionLive || raceWeekend) && next) {
    return (
      <LiveWeekendBoard
        next={next}
        sessionLive={sessionLive}
        viewOnly={viewOnly}
        onViewData={() => setViewData(true)}
        onReplay={(stype) => setReplayType(stype)}
        onEnter={(round, driver) => flow.enterLive(round, driver)}
      />
    );
  }
  return <StateA next={next} calendarYear={cal.calendarState && "year" in cal.calendarState ? 2026 : 2026} />;
}

function StateA({ next }: { next?: NextRace; calendarYear: number }) {
  const navigate = useNavigate();
  const flow = useFlow();
  const cal = useCalendarState(next?.year ?? 2026);
  const rounds = cal.status === "ok" ? cal.data.calendar.rounds : [];
  const last = [...rounds].reverse().find((r) => r.status === "COMPLETED");
  return (
    <div style={{ flex: 1, overflow: "auto", padding: "48px 24px", maxWidth: 900, margin: "0 auto" }}>
      <div style={{ fontFamily: T.display, fontSize: 56, fontWeight: 900, lineHeight: 1 }}>NO LIVE SESSION</div>
      <div style={{ fontFamily: T.mono, fontSize: 13, color: C.mist, marginTop: 16 }}>
        Next session: {next?.next_session_name ?? "TBC"} · {next?.circuit_name ?? "—"} ·{" "}
        {next?.date_race?.slice(0, 10) ?? "TBC"}
        {next ? (
          <>
            {" "}
            · <Countdown seconds={next.countdown_seconds} />
          </>
        ) : null}
      </div>
      <p style={{ fontFamily: T.body, color: C.mist, marginTop: 16 }}>
        While you wait, explore the circuit or replay a recent race.
      </p>
      <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
        <button
          onClick={() => next && navigate(`/circuits/${next.circuit_key}`)}
          style={cta(true)}
        >
          VIEW CIRCUIT
        </button>
        <button
          disabled={!last}
          onClick={() => last && flow.startReplay(last, next?.year ?? 2026)}
          style={cta(!!last)}
        >
          REPLAY LAST RACE
        </button>
      </div>
    </div>
  );
}

function StateB({ next, embedded }: { next: NextRace; embedded?: boolean }) {
  const [driver, setDriver] = useState<string | null>(null);
  const drivers = useDrivers(2026);
  const standings = useStandings(2026);
  const circuit = useCircuit(next.circuit_key, 2026);
  const pts = new Map(
    standings.drivers.status === "ok" ? standings.drivers.data.standings.map((s) => [s.driver_code, s]) : [],
  );
  const hours = next.hours_until;
  const session = next.next_session_name ?? "FP1";

  return (
    <div style={embedded ? undefined : { flex: 1, overflow: "auto", padding: "28px 24px", maxWidth: 1100, margin: "0 auto" }}>
      {!embedded && (
        <>
          <div style={{ fontFamily: T.mono, fontSize: 12, color: C.signal, letterSpacing: "0.12em" }}>
            {next.circuit_name.toUpperCase()} · {next.name.toUpperCase()}
          </div>
          <div style={{ fontFamily: T.display, fontSize: 42, fontWeight: 800, marginTop: 8 }}>
            {session.toUpperCase()} STARTS IN <Countdown seconds={next.countdown_seconds} />
          </div>
          {hours > 0 && hours <= 3 && (
            <div style={{ fontFamily: T.mono, fontSize: 12, color: C.mist, marginTop: 6 }}>
              Session window &lt; 3 hours
            </div>
          )}
        </>
      )}
      {!embedded && (
      <div style={{ marginTop: 20, padding: 14, background: C.panel, border: `1px solid ${C.border}`, borderRadius: 6 }}>
        {next.sessions_this_weekend.map((s) => (
          <div key={s.session_type} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
            <span style={{ fontFamily: T.mono, fontSize: 11 }}>{s.session_name}</span>
            <Chip tone={s.status === "LIVE" ? "caution" : "mist"} size="xs">
              {s.status}
            </Chip>
          </div>
        ))}
      </div>
      )}
      <div style={{ fontFamily: T.display, fontSize: 22, fontWeight: 800, margin: "28px 0 8px" }}>
        Set up your strategy for this race
      </div>
      <p style={{ fontFamily: T.body, fontSize: 13, color: C.mist, marginBottom: 16 }}>
        ARIS will build an initial strategy from historical data at this circuit. As FP1, Sprint, and
        Qualifying data comes in, the strategy will update automatically.
      </p>
      {drivers.status === "loading" && <SkeletonPanel rows={8} label="Loading 2026 drivers…" />}
      {drivers.status === "ok" && (
        <DriverPicker
          drivers={drivers.data.drivers}
          standings={pts}
          selected={driver}
          onSelect={setDriver}
        />
      )}
      {driver && (
        <>
          <div style={{ marginTop: 28 }}>
            <RaceBrief
              circuitKey={next.circuit_key}
              year={next.year}
              circuitName={next.circuit_name}
              driver={driver}
            />
          </div>
          <InitialStrategy
            circuitKey={next.circuit_key}
            year={2026}
            round={next.round_number}
            driver={driver}
            historyN={circuit.history.status === "ok" ? circuit.history.data.years.length : 0}
            circuitName={next.circuit_name}
            sessions={next.sessions_this_weekend}
          />
        </>
      )}
    </div>
  );
}

function secondsUntil(iso?: string | null): number {
  if (!iso) return 0;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  return Math.max(0, Math.floor((t - Date.now()) / 1000));
}

function LiveWeekendBoard({
  next,
  sessionLive,
  viewOnly,
  onViewData,
  onReplay,
  onEnter,
}: {
  next: NextRace;
  sessionLive: boolean;
  viewOnly: boolean;
  onViewData: () => void;
  onReplay: (sessionType: string) => void;
  onEnter: (round: CalendarRound, driver: string) => void;
}) {
  const liveSession = next.sessions_this_weekend.find((s) => s.status === "LIVE");
  const nextUp = next.sessions_this_weekend.find((s) => s.status === "UPCOMING");
  const upcoming = ["S", "Q", "R"]
    .map((t) => next.sessions_this_weekend.find((s) => s.session_type === t && s.status === "UPCOMING"))
    .filter((s): s is WeekendSession => Boolean(s));
  const headline = liveSession
    ? `${liveSession.session_name.toUpperCase()} IN PROGRESS`
    : nextUp
      ? `${nextUp.session_name.toUpperCase()} NEXT`
      : "WEEKEND";
  return (
    <div style={{ flex: 1, overflow: "auto", padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <Chip tone={sessionLive ? "caution" : "mist"}>{sessionLive ? "LIVE SESSION" : "RACE WEEKEND"}</Chip>
      <div style={{ fontFamily: T.display, fontSize: 36, fontWeight: 900, margin: "12px 0" }}>
        {next.name.toUpperCase()}
      </div>
      <div style={{ fontFamily: T.mono, fontSize: 12, color: C.mist, marginBottom: 16 }}>
        {next.circuit_name.toUpperCase()} · {headline}
        {nextUp?.datetime_utc && !liveSession ? (
          <>
            {" "}
            · <Countdown seconds={secondsUntil(nextUp.datetime_utc)} />
          </>
        ) : null}
      </div>
      <div style={{ padding: 14, background: C.panel, border: `1px solid ${C.border}`, borderRadius: 6, marginBottom: 20 }}>
        {next.sessions_this_weekend.map((s) => (
          <div
            key={s.session_type}
            style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", alignItems: "center", gap: 12 }}
          >
            <span style={{ fontFamily: T.mono, fontSize: 12 }}>{s.session_name}</span>
            <span style={{ fontFamily: T.mono, fontSize: 11, color: C.mist, flex: 1, textAlign: "right" }}>
              {s.status === "UPCOMING" && s.datetime_utc ? <Countdown seconds={secondsUntil(s.datetime_utc)} /> : null}
            </span>
            {s.status === "COMPLETED" ? (
              <button
                onClick={() => onReplay(s.session_type)}
                style={{
                  background: "transparent",
                  border: `1px solid ${C.border}`,
                  color: C.paper,
                  fontFamily: T.mono,
                  fontSize: 10,
                  padding: "5px 10px",
                  cursor: "pointer",
                }}
              >
                REPLAY
              </button>
            ) : null}
            <Chip
              tone={s.status === "LIVE" ? "caution" : s.status === "COMPLETED" ? "green" : "mist"}
              size="xs"
            >
              {s.status}
            </Chip>
          </div>
        ))}
      </div>
      {upcoming.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${upcoming.length}, minmax(0, 1fr))`, gap: 10, marginBottom: 24 }}>
          {upcoming.map((s) => (
            <div key={s.session_type} style={{ padding: 14, background: C.panel2, border: `1px solid ${C.border}`, borderRadius: 6 }}>
              <div style={{ fontFamily: T.mono, fontSize: 10, color: C.faint }}>{s.session_name.toUpperCase()}</div>
              <div style={{ fontFamily: T.display, fontSize: 22, fontWeight: 800, marginTop: 6 }}>
                <Countdown seconds={secondsUntil(s.datetime_utc)} />
              </div>
            </div>
          ))}
        </div>
      )}
      {sessionLive && viewOnly ? (
        <>
          <p style={{ fontFamily: T.body, fontSize: 13, color: C.mist, marginBottom: 16 }}>
            This session is view-only. ARIS strategy is for Sprint and Race.
          </p>
          <button onClick={onViewData} style={cta(true)}>
            VIEW SESSION DATA →
          </button>
        </>
      ) : null}
      {sessionLive && !viewOnly ? <LiveDriverGate next={next} onEnter={onEnter} /> : null}
      {!sessionLive ? <StateB next={next} embedded /> : null}
    </div>
  );
}

function LiveDriverGate({
  next,
  onEnter,
}: {
  next?: NextRace;
  onEnter: (round: CalendarRound, driver: string) => void;
}) {
  const [driver, setDriver] = useState<string | null>(null);
  const drivers = useDrivers(next?.year ?? 2026);
  const standings = useStandings(next?.year ?? 2026);
  const pts = new Map(
    standings.drivers.status === "ok" ? standings.drivers.data.standings.map((s) => [s.driver_code, s]) : [],
  );
  if (!next) return <div style={{ padding: 24 }}>Live session detected but next-race payload is empty.</div>;
  const round: CalendarRound = {
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
  };
  return (
    <div style={{ flex: 1, overflow: "auto", padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <Chip tone="caution">LIVE</Chip>
      <div style={{ fontFamily: T.display, fontSize: 36, fontWeight: 900, margin: "12px 0" }}>{next.name.toUpperCase()}</div>
      <p style={{ color: C.mist, marginBottom: 16 }}>Select your driver to open the live console.</p>
      {drivers.status === "ok" && (
        <DriverPicker drivers={drivers.data.drivers} standings={pts} selected={driver} onSelect={setDriver} />
      )}
      {driver && (
        <div style={{ marginTop: 24 }}>
          <RaceBrief
            circuitKey={next.circuit_key}
            year={next.year}
            circuitName={next.circuit_name}
            driver={driver}
          />
        </div>
      )}
      <button
        disabled={!driver}
        onClick={() => driver && onEnter(round, driver)}
        style={{ ...cta(!!driver), marginTop: 20 }}
      >
        {driver ? "LOCK BRIEF & ENTER LIVE CONSOLE →" : "SELECT DRIVER TO CONTINUE"}
      </button>
    </div>
  );
}

function InitialStrategy({
  circuitKey,
  year,
  round,
  driver,
  historyN,
  circuitName,
  sessions,
}: {
  circuitKey: string;
  year: number;
  round: number;
  driver: string;
  historyN: number;
  circuitName: string;
  sessions: NextRace["sessions_this_weekend"];
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
        if (!cancelled) setPlans(d.plans);
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
          setBadge(done ? `UPDATED AFTER ${done.session_name.toUpperCase()}` : null);
        }
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [year, round, driver, sessions]);
  return (
    <div style={{ marginTop: 28 }}>
      <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal, marginBottom: 10 }}>
        ARIS INITIAL STRATEGY — based on {historyN || "historical"} races at {circuitName}
        {badge && (
          <Chip tone="signal" size="xs">
            {badge}
          </Chip>
        )}
      </div>
      <p style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginBottom: 12 }}>
        This strategy will be refined as FP1 data becomes available.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 10 }}>
        {(plans || []).slice(0, 3).map((p) => (
          <div key={p.id} style={{ padding: 14, background: C.panel, border: `1px solid ${p.recommended ? C.signal : C.border}`, borderRadius: 4 }}>
            <div style={{ fontFamily: T.display, fontSize: 18, fontWeight: 800 }}>PLAN {p.id}</div>
            {p.recommended && <Chip tone="signal" size="xs">⭐ ARIS RECOMMENDED</Chip>}
            <div style={{ display: "flex", gap: 6, margin: "8px 0" }}>
              <TyreBadge compound={compoundLetter(p.start_compound)} size="sm" />
              {p.pit_compounds.map((c, i) => (
                <TyreBadge key={i} compound={compoundLetter(c)} size="sm" />
              ))}
            </div>
            <p style={{ fontFamily: T.body, fontSize: 11, color: C.mist }}>{p.description}</p>
            {p.pit_cost_s != null && <ReasoningBar paceGain={p.pace_gain_s ?? 0} pitCost={p.pit_cost_s} label />}
          </div>
        ))}
      </div>
      {rec && <p style={{ fontFamily: T.body, fontSize: 12, color: C.mist, marginTop: 10 }}>{rec.reasoning}</p>}
      <span style={{ display: "none" }}>{circuitKey}</span>
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

