"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { explainSessionId, getGhostVsReal } from "@/lib/api";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { useRaceStore } from "@/store/raceStore";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { PanelEmpty, PanelSkeleton } from "@/components/ui/PanelStates";
import { ghostVsRealFromField } from "@/lib/debriefSummary";
import type { GhostVsRealResponse } from "@/lib/types";

const SELECT =
  "rounded border border-border bg-surface px-1.5 py-0.5 font-mono-data text-[10px] text-white";

export function GhostVsRealChart({
  sessionId,
  driver,
}: {
  sessionId?: string;
  driver?: string;
}) {
  const session = useRaceStore((s) => s.session);
  const focused = useFocusDriver();
  const [code, setCode] = useState(driver ?? focused);

  useEffect(() => {
    if (!driver && focused) setCode(focused);
  }, [focused, driver]);
  const [data, setData] = useState<GhostVsRealResponse | null>(null);
  const [pending, setPending] = useState(false);
  const sid = sessionId ?? explainSessionId(session);
  const field = useRaceStore((s) => s.r2RaceField);
  const ticks = useRaceStore((s) => s.ghostTicksByLap);
  const local = useMemo(
    () => (field && Object.keys(ticks).length ? ghostVsRealFromField(field, code, ticks) : null),
    [field, ticks, code],
  );

  useEffect(() => {
    if (local) {
      setData(local);
      setPending(false);
      return;
    }
    let cancelled = false;
    setPending(true);
    getGhostVsReal({ session_id: sid, driver: code }).then((payload) => {
      if (cancelled) return;
      setData(payload);
      setPending(false);
    });
    return () => {
      cancelled = true;
    };
  }, [sid, code, local]);

  const currentLap = useRaceStore((s) => s.currentLap) || 1;

  const chart = useMemo(() => {
    if (!data) return [];
    const cap = Math.max(1, currentLap);
    return data.real.laps
      .map((lap, i) => ({
        lap,
        ghostPos: data.ghost.position[i],
        realPos: data.real.position[i],
        ghostGap: data.ghost.gap_to_leader[i],
        realGap: data.real.gap_to_leader[i],
        posDelta: data.delta.position_delta[i],
        gapDelta: data.delta.gap_delta[i],
        ghostCompound: data.ghost.compound[i],
        realCompound: data.real.compound[i],
      }))
      .filter((row) => row.lap <= cap);
  }, [data, currentLap]);

  return (
    <div className="flex h-full min-h-[280px] flex-col bg-carbon p-2">
      <div className="mb-2 flex flex-wrap items-center gap-2 font-mono-data text-[10px]">
        <span className="text-muted">Driver</span>
        <select value={code} onChange={(e) => setCode(e.target.value)} className={SELECT}>
          {MOCK_DRIVERS_2025.map((d) => (
            <option key={d.driver_code} value={d.driver_code}>
              {d.driver_code}
            </option>
          ))}
        </select>
        {data && (
          <span className="text-muted">
            Ghost pits {data.ghost.pit_laps.join(",") || "—"} · Real pits {data.real.pit_laps.join(",") || "—"}
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1">
        {pending && !data ? (
          <PanelSkeleton />
        ) : chart.length === 0 ? (
          <PanelEmpty
            title="Ghost vs real"
            detail="ARIS ghost position and gap versus the real driver from lap 1. Empty until the lights-out plan is scored."
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ top: 8, right: 36, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
              <XAxis
                dataKey="lap"
                stroke="#888888"
                tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
                label={{ value: "Lap", position: "insideBottom", offset: -2, fill: "#888888", fontSize: 10 }}
              />
              <YAxis
                yAxisId="pos"
                reversed
                domain={[1, 20]}
                stroke="#888888"
                tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
                width={28}
                label={{ value: "P", angle: -90, position: "insideLeft", fill: "#888888", fontSize: 10 }}
              />
              <YAxis
                yAxisId="gap"
                orientation="right"
                stroke="#888888"
                tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
                width={36}
                label={{ value: "Gap (s)", angle: 90, position: "insideRight", fill: "#888888", fontSize: 10 }}
              />
              <Tooltip
                contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              />
              {/* Ghost is always dashed, real is always solid — the same convention as the
                  track map dot and the timing tower row, so a viewer never has to relearn it. */}
              <Line yAxisId="pos" type="stepAfter" dataKey="realPos" name="Real P" stroke="#ffffff" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line yAxisId="pos" type="stepAfter" dataKey="ghostPos" name="Ghost P" stroke="#e8002d" dot={false} strokeWidth={1.5} strokeDasharray="5 4" isAnimationActive={false} />
              <Line yAxisId="gap" type="monotone" dataKey="realGap" name="Real gap" stroke="#888888" dot={false} strokeOpacity={0.7} isAnimationActive={false} />
              <Line yAxisId="gap" type="monotone" dataKey="ghostGap" name="Ghost gap" stroke="#e8002d" dot={false} strokeDasharray="5 4" strokeOpacity={0.55} isAnimationActive={false} />
              <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      {data?.explanation && (
        <p className="mt-1 shrink-0 font-mono-data text-[10px] text-muted">{data.explanation}</p>
      )}
    </div>
  );
}