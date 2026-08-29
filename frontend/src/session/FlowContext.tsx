import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { asOfFromUrl } from "../api/client";
import type { CalendarRound, SessionConfig } from "../api/types";
import { ARIS_ON_REPLAY } from "../flags";
import { clampReplayYear } from "../years";

export type ReplayStep = "setup" | "briefing" | "console" | "debrief";

function yearFromAsOf(): number {
  const raw = asOfFromUrl();
  if (!raw) return clampReplayYear(new Date().getUTCFullYear());
  return clampReplayYear(new Date(raw).getUTCFullYear());
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
  enterLive: (round: CalendarRound, driver: string, opts?: { year?: number; planId?: string }) => void;
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
        if (driver && ARIS_ON_REPLAY) {
          setPartial({ mode: "replay", year: y, round, driver });
          setReplayStep("briefing");
        } else if (driver && !ARIS_ON_REPLAY) {
          setConfig({
            mode: "replay",
            year: y,
            round,
            driver,
            arisMode: "assisted",
            planId: "A",
          });
          setReplayStep("console");
        } else {
          setPartial(null);
          setPreselectRound(round);
          setReplayStep("setup");
        }
        navigate("/replay");
      },
      enterLive: (round, driver, opts) => {
        const y = opts?.year ?? year;
        setYear(y);
        setConfig({
          mode: "live",
          year: y,
          round,
          driver,
          arisMode: "auto",
          planId: opts?.planId ?? "A",
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
