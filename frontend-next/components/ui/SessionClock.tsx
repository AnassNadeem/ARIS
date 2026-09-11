"use client";

import { useEffect, useState } from "react";
import { formatSessionClock, liveSessionRemainingMs } from "@/lib/formatLap";
import { isTimedSession, sessionClockDurationMs, sessionLabel } from "@/lib/sessionFlow";
import { useRaceStore } from "@/store/raceStore";
import type { RacePhase } from "@/lib/types";

export function flagLabel(phase: RacePhase): string {
  if (phase === "RED_FLAG") return "RED FLAG";
  if (phase === "YELLOW") return "YELLOW FLAG";
  if (phase === "SC") return "SAFETY CAR";
  if (phase === "VSC") return "VSC";
  if (phase === "STANDING_START") return "STANDING START";
  return "GREEN FLAG";
}

export function SessionFlagBadge({ compact = false }: { compact?: boolean }) {
  const phase = useRaceStore((s) => s.racePhase);
  const tone =
    phase === "RED_FLAG"
      ? "bg-[#E8002D]/20 text-[#E8002D]"
      : phase === "YELLOW"
        ? "bg-[#FFE14A]/20 text-[#FFE14A]"
        : phase === "GREEN"
          ? "bg-[#00D26A]/15 text-[#00D26A]"
          : "bg-[#FF8700]/20 text-[#FF8700]";
  return (
    <span
      data-testid="session-flag"
      className={`rounded px-1.5 py-0.5 font-mono-data text-[10px] uppercase tracking-wide ${tone}`}
    >
      {compact ? phase.replace("_", " ") : flagLabel(phase)}
    </span>
  );
}

export function SessionClockLabel({
  startIso,
  sessionType,
  compact = false,
}: {
  startIso: string | null | undefined;
  sessionType: string | null | undefined;
  compact?: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());
  const timed = isTimedSession(sessionType);
  const remainingS = useRaceStore((s) => s.sessionRemainingSeconds);
  const remainingAtMs = useRaceStore((s) => s.sessionRemainingAtMs);
  const phase = useRaceStore((s) => s.racePhase);

  useEffect(() => {
    if (!timed) return;
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [timed]);

  if (!timed) return null;
  const remaining = liveSessionRemainingMs({
    remainingS,
    remainingAtMs,
    frozen: phase === "RED_FLAG",
    now,
    startIso,
    durationMs: sessionClockDurationMs(sessionType),
  });
  const clock = formatSessionClock(remaining);
  if (compact) return <span data-testid="session-clock">{clock}</span>;
  return (
    <span data-testid="session-clock">
      {sessionLabel(sessionType)} {clock}
    </span>
  );
}
