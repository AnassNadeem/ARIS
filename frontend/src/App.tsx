import { useMemo, useState } from "react";
import type { CalendarRound, SessionConfig } from "./api/types";
import { asOfFromUrl } from "./api/client";
import { GlobalNav, type NavId } from "./components/GlobalNav";
import { FONT_HREF, C, T } from "./theme";
import { useCalendarState } from "./hooks/useCalendarState";
import { AnalyticsView } from "./views/AnalyticsView";
import { BriefingView } from "./views/BriefingView";
import { CircuitsView } from "./views/CircuitsView";
import { ConsoleView } from "./views/ConsoleView";
import { DebriefView } from "./views/DebriefView";
import { HomeView } from "./views/HomeView";
import { SetupView } from "./views/SetupView";
import { StandingsView } from "./views/StandingsView";

type View =
  | "home"
  | "setup"
  | "briefing"
  | "console"
  | "debrief"
  | "standings"
  | "circuits"
  | "analytics";

function yearFromAsOf(): number {
  const raw = asOfFromUrl();
  if (!raw) return 2026;
  const y = new Date(raw).getUTCFullYear();
  return y === 2024 || y === 2025 || y === 2026 ? y : 2026;
}

export default function App() {
  const [year, setYear] = useState(yearFromAsOf);
  const [view, setView] = useState<View>("home");
  const [nav, setNav] = useState<NavId>("home");
  const [partial, setPartial] = useState<Omit<SessionConfig, "arisMode" | "planId"> | null>(null);
  const [config, setConfig] = useState<SessionConfig | null>(null);
  const [entered, setEntered] = useState(() => localStorage.getItem("aris-v3-entered") === "1");
  const cal = useCalendarState(year);

  const rounds = cal.status === "ok" ? cal.data.calendar.rounds : [];
  const live =
    cal.calendarState?.type === "LIVE_RACE" ||
    cal.calendarState?.type === "LIVE_QUALI" ||
    cal.calendarState?.type === "LIVE_PRACTICE";

  const startReplay = (round: CalendarRound, y: number, driver = "NOR") => {
    setYear(y);
    setPartial({ mode: "replay", year: y, round, driver });
    setView("briefing");
    setNav("replay");
  };

  const goNav = (id: NavId) => {
    setNav(id);
    if (id === "home") setView("home");
    if (id === "replay") setView("setup");
    if (id === "live") {
      setView("home");
    }
    if (id === "analytics") setView("analytics");
    if (id === "standings") setView("standings");
    if (id === "circuits") setView("circuits");
  };

  const styles = useMemo(
    () => `
    @import url('${FONT_HREF}');
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body, #root { height: 100%; background: ${C.void}; color: ${C.paper}; }
    body { font-family: ${T.body}; }
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: ${C.void}; }
    ::-webkit-scrollbar-thumb { background: ${C.border}; }
    @keyframes ping { 75%, 100% { transform: scale(2); opacity: 0; } }
    @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    button { transition: filter 0.12s; }
    button:hover { filter: brightness(1.08); }
  `,
    [],
  );

  return (
    <div style={{ minHeight: "100vh", background: C.void, color: C.paper, display: "flex", flexDirection: "column" }}>
      <style>{styles}</style>
      {!entered && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 40,
            background: C.void,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 16,
          }}
        >
          <div style={{ fontFamily: T.display, fontSize: 96, fontWeight: 900, letterSpacing: "-2px" }}>ARIS</div>
          <div style={{ fontFamily: T.mono, fontSize: 12, color: C.mist, letterSpacing: "0.18em" }}>
            ALWAYS-ON RACE INTELLIGENCE SYSTEM
          </div>
          <button
            onClick={() => {
              localStorage.setItem("aris-v3-entered", "1");
              setEntered(true);
            }}
            style={{
              marginTop: 12,
              padding: "12px 28px",
              background: C.signal,
              border: "none",
              borderRadius: 4,
              color: C.ink,
              fontFamily: T.display,
              fontSize: 18,
              fontWeight: 800,
              cursor: "pointer",
            }}
          >
            ENTER →
          </button>
        </div>
      )}
      <GlobalNav active={nav} year={year} onNav={goNav} onYear={setYear} live={live} />
      {view === "home" && (
        <HomeView
          year={year}
          calendarState={cal.calendarState}
          rounds={rounds}
          loading={cal.status === "loading"}
          error={cal.status === "error" ? cal.error : undefined}
          onRetry={cal.retry}
          onReplay={startReplay}
          onLive={() => goNav("live")}
          onExplore={() => goNav("circuits")}
          onStandings={() => goNav("standings")}
          onSetupLive={() => {
            setNav("replay");
            setView("setup");
          }}
        />
      )}
      {view === "setup" && (
        <SetupView
          year={year}
          onYear={setYear}
          onProceed={(cfg) => {
            setPartial(cfg);
            setView("briefing");
          }}
        />
      )}
      {view === "briefing" && partial && (
        <BriefingView
          partial={partial}
          onLock={(cfg) => {
            setConfig(cfg);
            setView("console");
          }}
        />
      )}
      {view === "console" && config && (
        <ConsoleView config={config} onDebrief={() => setView("debrief")} />
      )}
      {view === "debrief" && config && (
        <DebriefView
          config={config}
          onBack={() => setView("console")}
          onRestart={() => {
            setConfig(null);
            setPartial(null);
            setView("setup");
            setNav("replay");
          }}
        />
      )}
      {view === "standings" && <StandingsView year={year} />}
      {view === "circuits" && <CircuitsView year={year} />}
      {view === "analytics" && <AnalyticsView year={year} />}
    </div>
  );
}
