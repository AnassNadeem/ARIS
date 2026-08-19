import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { asOfFromUrl } from "../api/client";
import type { CalendarRound, SessionConfig } from "../api/types";

export type ReplayStep = "setup" | "briefing" | "console" | "debrief";

function yearFromAsOf(): number {
  const raw = asOfFromUrl();
  if (!raw) return 2026;
  const y = new Date(raw).getUTCFullYear();
  return y === 2024 || y === 2025 || y === 2026 ? y : 2026;
}

type Flow = {
  year: number;
  setYear: (y: number) => void;
  replayStep: ReplayStep;
  setReplayStep: (s: ReplayStep) => void;
  partial: Omit<SessionConfig, "arisMode" | "planId"> | null;
  setPartial: (p: Omit<SessionConfig, "arisMode" | "planId"> | null) => void;
  config: SessionConfig | null;
  setConfig: (c: SessionConfig | null) => void;
  preselectRound: CalendarRound | null;
  setPreselectRound: (r: CalendarRound | null) => void;
  startReplay: (round: CalendarRound, year: number, driver?: string) => void;
  enterLive: (round: CalendarRound, driver: string) => void;
};

const Ctx = createContext<Flow | null>(null);

export function FlowProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [year, setYear] = useState(yearFromAsOf);
  const [replayStep, setReplayStep] = useState<ReplayStep>("setup");
  const [partial, setPartial] = useState<Omit<SessionConfig, "arisMode" | "planId"> | null>(null);
  const [config, setConfig] = useState<SessionConfig | null>(null);
  const [preselectRound, setPreselectRound] = useState<CalendarRound | null>(null);

  const value = useMemo<Flow>(
    () => ({
      year,
      setYear,
      replayStep,
      setReplayStep,
      partial,
      setPartial,
      config,
      setConfig,
      preselectRound,
      setPreselectRound,
      startReplay: (round, y, driver) => {
        setYear(y);
        if (driver) {
          setPartial({ mode: "replay", year: y, round, driver });
          setReplayStep("briefing");
        } else {
          setPartial(null);
          setPreselectRound(round);
          setReplayStep("setup");
        }
        navigate("/replay");
      },
      enterLive: (round, driver) => {
        setYear(2026);
        setConfig({
          mode: "live",
          year: 2026,
          round,
          driver,
          arisMode: "assisted",
          planId: "A",
        });
        navigate("/live");
      },
    }),
    [year, replayStep, partial, config, preselectRound, navigate],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useFlow(): Flow {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useFlow must be used within FlowProvider");
  return ctx;
}
