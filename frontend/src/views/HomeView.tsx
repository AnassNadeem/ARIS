import { useEffect, useState } from "react";
import type { CalendarRound, CalendarState, NextRace } from "../api/types";
import { useCircuit } from "../hooks/useCircuit";
import { useStandings } from "../hooks/useStandings";
import { C, T } from "../theme";
import { Chip, EmptyState, ErrorPanel, LiveDot, Panel, SectionLabel, SkeletonPanel, Stat } from "../components/atoms";

function Countdown({ seconds }: { seconds: number }) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => {
    setLeft(seconds);
    const id = window.setInterval(() => setLeft((s) => Math.max(0, s - 1)), 1000);
    return () => window.clearInterval(id);
  }, [seconds]);
  const d = Math.floor(left / 86400);
  const h = Math.floor((left % 86400) / 3600);
  const m = Math.floor((left % 3600) / 60);
  const s = left % 60;
  const cell = (n: number, l: string) => (
    <div style={{ textAlign: "center", minWidth: 64 }}>
      <div style={{ fontFamily: T.display, fontSize: 42, fontWeight: 900, color: C.signal, lineHeight: 1 }}>
        {String(n).padStart(2, "0")}
      </div>
      <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, letterSpacing: "0.12em" }}>{l}</div>
    </div>
  );
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      {cell(d, "DAYS")}
      {cell(h, "HRS")}
      {cell(m, "MIN")}
      {cell(s, "SEC")}
    </div>
  );
}

function ReplayCards({
  rounds,
  year,
  onReplay,
}: {
  rounds: CalendarRound[];
  year: number;
  onReplay: (r: CalendarRound) => void;
}) {
  const done = rounds.filter((r) => r.status === "COMPLETED").slice(-6).reverse();
  if (!done.length) {
    return <EmptyState title="No completed races yet" body="Replay cards appear after a round is classified." />;
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
      {done.map((r) => (
        <button
          key={r.round_number}
          onClick={() => onReplay(r)}
          style={{
            textAlign: "left",
            padding: 12,
            background: C.panel2,
            border: `1px solid ${C.border}`,
            borderRadius: 4,
            cursor: "pointer",
          }}
        >
          <div style={{ fontFamily: T.body, fontSize: 13, fontWeight: 600, color: C.paper }}>{r.name}</div>
          <div style={{ fontFamily: T.mono, fontSize: 9, color: C.faint, marginTop: 4 }}>
            {year} · Rd {r.round_number} · {r.circuit_name}
          </div>
        </button>
      ))}
    </div>
  );
}

function WeekendBody({
  next,
  year,
  rounds,
  onExplore,
  onReplay,
}: {
  next: NextRace;
  year: number;
  rounds: CalendarRound[];
  onExplore: () => void;
  onReplay: (r: CalendarRound) => void;
}) {
  const circuit = useCircuit(next.circuit_key, year);
  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ fontFamily: T.mono, fontSize: 11, color: C.signal, letterSpacing: "0.14em", marginBottom: 8 }}>
        RACE WEEKEND
      </div>
      <div style={{ fontFamily: T.display, fontSize: 48, fontWeight: 900, lineHeight: 1 }}>{next.name.toUpperCase()}</div>
      <div style={{ fontFamily: T.mono, fontSize: 12, color: C.mist, margin: "8px 0 20px" }}>
        {next.circuit_name} · {next.city}
      </div>
      <Countdown seconds={next.countdown_seconds} />
      <div style={{ fontFamily: T.mono, fontSize: 11, color: C.faint, margin: "10px 0 24px" }}>
        Next session: {next.next_session_name ?? "TBC"}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 20 }}>
        <Panel title="SESSION SCHEDULE">
          <div style={{ padding: 12 }}>
            {next.sessions_this_weekend.map((s) => (
              <div
                key={s.session_type}
                style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: `1px solid ${C.border}40` }}
              >
                <span style={{ fontFamily: T.mono, fontSize: 11, color: C.paper }}>{s.session_name}</span>
                <Chip tone={s.status === "LIVE" ? "caution" : "mist"} size="xs">
                  {s.status}
                </Chip>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="CIRCUIT INFO">
          {circuit.chars.status === "loading" && (
            <SkeletonPanel
              rows={6}
              label="Loading circuit info — this may take a moment on first load as data is being cached..."
            />
          )}
          {circuit.chars.status === "error" && (
            <ErrorPanel
              message={`Could not load circuit info. ${circuit.chars.error}`}
              onRetry={circuit.chars.retry}
            />
          )}
          {circuit.chars.status === "ok" && (
            <div style={{ padding: 12 }}>
              {[
                ["Length", circuit.chars.data.lap_length_km ? `${circuit.chars.data.lap_length_km} km` : "—"],
                ["Turns", circuit.chars.data.turns != null ? String(circuit.chars.data.turns) : "—"],
                ["Pit loss", circuit.chars.data.pit_loss_seconds != null ? `~${circuit.chars.data.pit_loss_seconds}s` : "—"],
                ["DRS zones", circuit.chars.data.drs_zones != null ? String(circuit.chars.data.drs_zones) : "not in source"],
              ].map(([k, v]) => (
                <div key={k} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                  <span style={{ fontFamily: T.body, fontSize: 12, color: C.mist }}>{k}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 12, color: C.paper }}>{v}</span>
                </div>
              ))}
            </div>
          )}
        </Panel>
        <Panel title="HISTORICAL WINNERS">
          {circuit.history.status === "loading" && (
            <SkeletonPanel
              rows={5}
              label="Loading historical results — this may take a moment on first load as data is being cached..."
            />
          )}
          {circuit.history.status === "error" && (
            <ErrorPanel
              message={`Could not load historical results. ${circuit.history.error}`}
              onRetry={circuit.history.retry}
            />
          )}
          {circuit.history.status === "ok" && (
            <div style={{ padding: 12 }}>
              {circuit.history.data.years.length === 0 && (
                <EmptyState title="No history yet" body="Winners appear after FastF1 results load for prior years." />
              )}
              {circuit.history.data.years.map((h) => (
                <div key={h.year} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                  <span style={{ fontFamily: T.mono, fontSize: 12, color: C.mist }}>{h.year}</span>
                  <span style={{ fontFamily: T.mono, fontSize: 12, color: C.paper }}>
                    {h.winner ?? "—"} {h.winner_team ? `· ${h.winner_team}` : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>
      <button
        onClick={onExplore}
        style={{
          padding: "12px 22px",
          background: C.signal,
          border: "none",
          borderRadius: 4,
          color: C.ink,
          fontFamily: T.display,
          fontSize: 16,
          fontWeight: 800,
          cursor: "pointer",
          marginBottom: 24,
        }}
      >
        EXPLORE {next.name.toUpperCase()} →
      </button>
      <SectionLabel>WHILE YOU WAIT — REPLAY ANY RACE HERE</SectionLabel>
      <ReplayCards rounds={rounds} year={year} onReplay={onReplay} />
    </div>
  );
}

export function HomeView({
  year,
  calendarState,
  rounds,
  onReplay,
  onLive,
  onExplore,
  onStandings,
  onSetupLive,
  loading,
  error,
  onRetry,
}: {
  year: number;
  calendarState?: CalendarState;
  rounds: CalendarRound[];
  onReplay: (r: CalendarRound, year: number) => void;
  onLive: () => void;
  onExplore?: () => void;
  onStandings: () => void;
  onSetupLive?: () => void;
  loading?: boolean;
  error?: string;
  onRetry: () => void;
}) {
  const standings = useStandings(year);

  if (loading) {
    return (
      <div style={{ padding: 32, maxWidth: 800 }}>
        <SkeletonPanel
          rows={8}
          label="Loading calendar — this may take a moment on first load as data is being cached..."
        />
      </div>
    );
  }
  if (error) {
    return (
      <ErrorPanel message={`Could not load calendar. ${error}`} onRetry={onRetry} />
    );
  }
  if (!calendarState) return <EmptyState title="No calendar state" body="Retry loading next-race and calendar." />;

  if (calendarState.type === "LIVE_RACE" || calendarState.type === "LIVE_QUALI" || calendarState.type === "LIVE_PRACTICE") {
    const label =
      calendarState.type === "LIVE_RACE"
        ? `LIVE · ${calendarState.live.gp_name ?? calendarState.next.name} · LAP ${calendarState.live.current_lap ?? "—"} / ${calendarState.live.total_laps ?? "—"}`
        : `LIVE · ${calendarState.live.session_name ?? calendarState.type} · ${calendarState.next.name}`;
    return (
      <div style={{ padding: 40, textAlign: "center" }}>
        <div style={{ display: "flex", justifyContent: "center", gap: 10, marginBottom: 16 }}>
          <LiveDot />
          <span style={{ fontFamily: T.mono, fontSize: 14, color: C.caution, letterSpacing: "0.12em" }}>{label}</span>
        </div>
        <div style={{ fontFamily: T.display, fontSize: 56, fontWeight: 900 }}>RACE CONSOLE READY</div>
        <p style={{ fontFamily: T.body, color: C.mist, margin: "16px 0 28px" }}>
          A session is in progress. Open the live timing tower.
        </p>
        <button
          onClick={onSetupLive || onLive}
          style={{
            padding: "14px 28px",
            background: C.caution,
            border: "none",
            color: C.paper,
            fontFamily: T.display,
            fontSize: 18,
            fontWeight: 800,
            cursor: "pointer",
            borderRadius: 4,
          }}
        >
          {calendarState.type === "LIVE_RACE" ? "WATCH LIVE →" : "VIEW LIVE SESSION →"}
        </button>
      </div>
    );
  }

  if (calendarState.type === "RACE_WEEKEND") {
    return (
      <WeekendBody
        next={calendarState.next}
        year={year}
        rounds={rounds}
        onExplore={onExplore || onLive}
        onReplay={(r) => onReplay(r, year)}
      />
    );
  }

  if (calendarState.type === "POST_RACE") {
    return (
      <div style={{ padding: 32, maxWidth: 900, margin: "0 auto" }}>
        <Chip tone="signal">Race just finished {Math.round(calendarState.hoursAgo)} hours ago</Chip>
        <div style={{ fontFamily: T.display, fontSize: 42, fontWeight: 900, margin: "16px 0" }}>
          {calendarState.completed.name.toUpperCase()} DEBRIEF
        </div>
        <p style={{ fontFamily: T.body, color: C.mist, marginBottom: 20 }}>
          Load the ARIS comparison against the classified result.
        </p>
        <button
          onClick={() => onReplay(calendarState.completed, calendarState.year)}
          style={{
            padding: "12px 22px",
            background: C.signal,
            border: "none",
            borderRadius: 4,
            color: C.ink,
            fontFamily: T.display,
            fontSize: 16,
            fontWeight: 800,
            cursor: "pointer",
          }}
        >
          VIEW FULL DEBRIEF →
        </button>
      </div>
    );
  }

  if (calendarState.type === "OFF_SEASON") {
    const champ =
      standings.drivers.status === "ok" ? standings.drivers.data.champion_code || standings.drivers.data.leader_code : null;
    return (
      <div style={{ padding: 32, maxWidth: 1000, margin: "0 auto" }}>
        <div style={{ fontFamily: T.mono, color: C.signal, letterSpacing: "0.14em", marginBottom: 8 }}>OFF SEASON</div>
        <div style={{ fontFamily: T.display, fontSize: 42, fontWeight: 900 }}>YEAR IN REVIEW</div>
        <div style={{ margin: "20px 0" }}>
          <Stat label="Champion / leader" value={champ ?? "—"} sub={`Season ${year}`} />
        </div>
        <div style={{ fontFamily: T.mono, color: C.mist, marginBottom: 16 }}>
          Next season starts {calendarState.next.date_race?.slice(0, 10) ?? "TBC"}
        </div>
        <Countdown seconds={calendarState.next.countdown_seconds} />
        <div style={{ marginTop: 28 }}>
          <SectionLabel>HISTORICAL REPLAY</SectionLabel>
          <ReplayCards rounds={rounds} year={year} onReplay={(r) => onReplay(r, year)} />
        </div>
      </div>
    );
  }

  const next = calendarState.next;
  const remaining = rounds.filter((r) => r.status === "UPCOMING").length;
  const last = [...rounds].reverse().find((r) => r.status === "COMPLETED");
  const top = standings.drivers.status === "ok" ? standings.drivers.data.standings.slice(0, 5) : [];
  const cons = standings.constructors.status === "ok" ? standings.constructors.data.standings.slice(0, 3) : [];
  const leader = top[0];

  return (
    <div style={{ padding: 32, maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ fontFamily: T.mono, color: C.faint, letterSpacing: "0.12em", marginBottom: 8 }}>BETWEEN ROUNDS</div>
      {leader && (
        <div style={{ marginBottom: 24 }}>
          <Stat
            label="Championship leader"
            value={`${leader.driver_code}  ${leader.points} pts`}
            sub={top[1] ? `Gap to P2: ${top[1].gap_to_leader} · ${remaining} rounds remaining` : undefined}
            accent={C.signal}
          />
        </div>
      )}
      {standings.drivers.status === "loading" && (
        <SkeletonPanel rows={4} label="Loading standings — this may take a moment on first load as data is being cached..." />
      )}
      {standings.drivers.status === "error" && (
        <ErrorPanel message={`Could not load standings. ${standings.drivers.error}`} onRetry={standings.drivers.retry} />
      )}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        <Panel title="DRIVERS — TOP 5">
          <div style={{ padding: 12 }}>
            {top.length === 0 && standings.drivers.status === "ok" && (
              <EmptyState title="Standings unavailable" body="Jolpica returned no rows for this year." />
            )}
            {top.map((r) => (
              <div key={r.driver_code} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                <span style={{ fontFamily: T.mono, color: C.paper }}>
                  P{r.position} {r.driver_code}
                </span>
                <span style={{ fontFamily: T.mono, color: C.signal }}>{r.points}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel title="CONSTRUCTORS — TOP 3">
          <div style={{ padding: 12 }}>
            {cons.map((r) => (
              <div key={r.team_name} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0" }}>
                <span style={{ fontFamily: T.body, fontSize: 13, color: C.paper }}>{r.team_name}</span>
                <span style={{ fontFamily: T.mono, color: C.signal }}>{r.points}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title={`NEXT RACE: ${next.name}`}>
        <div style={{ padding: 14, fontFamily: T.body, color: C.mist }}>
          {next.circuit_name} · {next.date_race?.slice(0, 10) ?? "TBC"} · {next.days_until} days away
        </div>
      </Panel>
      <div style={{ display: "flex", gap: 12, marginTop: 20 }}>
        <button
          disabled={!last}
          onClick={() => last && onReplay(last, year)}
          style={{
            padding: "12px 20px",
            background: C.signal,
            border: "none",
            borderRadius: 4,
            color: C.ink,
            fontFamily: T.display,
            fontWeight: 800,
            cursor: last ? "pointer" : "not-allowed",
          }}
        >
          REPLAY LAST RACE →
        </button>
        <button
          onClick={onStandings}
          style={{
            padding: "12px 20px",
            background: "transparent",
            border: `1px solid ${C.border}`,
            borderRadius: 4,
            color: C.mist,
            fontFamily: T.mono,
            fontSize: 11,
            cursor: "pointer",
          }}
        >
          EXPLORE STANDINGS →
        </button>
      </div>
    </div>
  );
}
