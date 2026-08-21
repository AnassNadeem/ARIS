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
import { FlowProvider, useFlow } from "./session/FlowContext";

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

function ReplayRoutes() {
  const flow = useFlow();
  const navigate = useNavigate();
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
        onRestart={() => {
          flow.setConfig(null);
          flow.setPartial(null);
          flow.setReplayStep("setup");
          navigate("/replay");
        }}
      />
    );
  }
  return (
    <SetupView
      year={flow.year}
      onYear={flow.setYear}
      initialRound={flow.preselectRound}
      onProceed={(cfg) => {
        flow.setPartial(cfg);
        flow.setReplayStep("briefing");
      }}
    />
  );
}

function Shell() {
  const cal = useCalendarState(2026);
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
