import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { asOfFromUrl, inFlightCount, subscribeTraffic } from "./api/client";
import { GlobalNav } from "./components/GlobalNav";
import { FONT_HREF, C, T } from "./theme";
import { useCalendarState } from "./hooks/useCalendarState";
import { BriefingView } from "./views/BriefingView";
import { CircuitsView } from "./views/CircuitsView";
import { ConsoleView } from "./views/ConsoleView";
import { DebriefView } from "./views/DebriefView";
import { SetupView } from "./views/SetupView";
import { StandingsView } from "./views/StandingsView";
import { HomePage } from "./pages/HomePage";
import { LivePage } from "./pages/LivePage";
import { LiveSessionView } from "./views/LiveSessionView";
import { FlowProvider, useFlow } from "./session/FlowContext";
import { ARIS_ON_REPLAY } from "./flags";
import type { NextRace, ReplayWatchPick } from "./api/types";
import { currentSeasonYear } from "./years";

function ApiProgressBar() {
  const [active, setActive] = useState(false);
  useEffect(() => subscribeTraffic(() => setActive(inFlightCount() > 0)), []);
  if (!active) return null;
  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        height: 3,
        zIndex: 80,
        overflow: "hidden",
        background: C.signalDim,
      }}
    >
      <div
        style={{
          height: "100%",
          width: "40%",
          background: C.signal,
          animation: "arisBar 1.1s ease-in-out infinite",
        }}
      />
    </div>
  );
}

function pickToNext(pick: ReplayWatchPick): NextRace {
  const r = pick.round;
  return {
    year: pick.year,
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
    sessions_this_weekend: [],
    notes: r.notes ?? [],
    as_of: new Date().toISOString(),
    off_season: false,
  };
}

function ReplayRoutes() {
  const flow = useFlow();
  const navigate = useNavigate();
  const [watch, setWatch] = useState<ReplayWatchPick | null>(null);
  const backToSetup = () => {
    flow.setConfig(null);
    flow.setPartial(null);
    flow.setReplayStep("setup");
    setWatch(null);
    navigate("/replay");
  };
  if (!ARIS_ON_REPLAY) {
    if (watch) {
      return (
        <LiveSessionView
          next={pickToNext(watch)}
          replaySessionType={watch.sessionType}
          initialSegment={watch.segment}
          onBack={() => setWatch(null)}
        />
      );
    }
    return (
      <SetupView
        year={flow.year}
        onYear={flow.setYear}
        initialRound={flow.preselectRound}
        onWatch={setWatch}
      />
    );
  }
  if (flow.replayStep === "briefing" && flow.partial) {
    return (
      <BriefingView
        partial={flow.partial}
        onLock={(cfg) => {
          flow.setConfig(cfg);
          flow.setReplayStep("console");
        }}
      />
    );
  }
  if (flow.replayStep === "console" && flow.config) {
    return <ConsoleView config={flow.config} onDebrief={() => flow.setReplayStep("debrief")} />;
  }
  if (flow.replayStep === "debrief" && flow.config) {
    return (
      <DebriefView
        config={flow.config}
        onBack={() => flow.setReplayStep("console")}
        onRestart={backToSetup}
      />
    );
  }
  return (
    <SetupView
      year={flow.year}
      onYear={flow.setYear}
      initialRound={flow.preselectRound}
      onWatch={setWatch}
    />
  );
}

function Shell() {
  const cal = useCalendarState(currentSeasonYear());
  const live =
    cal.calendarState?.type === "LIVE_RACE" ||
    cal.calendarState?.type === "LIVE_QUALI" ||
    cal.calendarState?.type === "LIVE_PRACTICE";

  const styles = useMemo(
    () => `
    @import url('${FONT_HREF}');
    * { box-sizing: border-box; margin: 0; padding: 0; }
    html, body, #root { height: 100%; background: ${C.void}; color: ${C.paper}; }
    body { font-family: ${T.body}; }
    ::-webkit-scrollbar { width: 6px; height: 8px; }
    ::-webkit-scrollbar-track { background: ${C.void}; }
    ::-webkit-scrollbar-thumb { background: ${C.border}; }
    @keyframes ping { 75%, 100% { transform: scale(2); opacity: 0; } }
    @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    @keyframes arisBar { 0% { transform: translateX(-100%); } 100% { transform: translateX(250%); } }
    @keyframes arisSpin { to { transform: rotate(360deg); } }
    button { transition: filter 0.12s; }
    button:hover { filter: brightness(1.08); }
  `,
    [],
  );

  void asOfFromUrl;

  return (
    <div style={{ minHeight: "100vh", height: "100%", background: C.void, color: C.paper, display: "flex", flexDirection: "column" }}>
      <style>{styles}</style>
      <ApiProgressBar />
      <GlobalNav live={live} />
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/replay" element={<ReplayRoutes />} />
        <Route path="/live" element={<LivePage />} />
        <Route path="/standings" element={<StandingsView />} />
        <Route path="/circuits" element={<CircuitsView />} />
        <Route path="/circuits/:slug" element={<CircuitsView />} />
        <Route path="/analytics" element={<Navigate to="/" replace />} />
      </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <FlowProvider>
      <Shell />
    </FlowProvider>
  );
}
