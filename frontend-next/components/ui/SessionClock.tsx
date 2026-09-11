"use client";

import { useEffect, useState } from "react";
import { formatSessionClock, sessionRemainingMs } from "@/lib/formatLap";
import { isTimedSession, sessionClockDurationMs, sessionLabel } from "@/lib/sessionFlow";

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

  useEffect(() => {
    if (!timed) return;
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [timed]);

  if (!timed) return null;
  const remaining = sessionRemainingMs(startIso, sessionClockDurationMs(sessionType), now);
  const clock = formatSessionClock(remaining);
  if (compact) return <span data-testid="session-clock">{clock}</span>;
  return (
    <span data-testid="session-clock">
      {sessionLabel(sessionType)} {clock}
    </span>
  );
}
