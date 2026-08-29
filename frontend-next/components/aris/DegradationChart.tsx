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
import { explainSessionId, getDegradationCurve } from "@/lib/api";
import { MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { useRaceStore } from "@/store/raceStore";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { PanelEmpty, PanelSkeleton } from "@/components/ui/PanelStates";
import type { DegradationCurveResponse } from "@/lib/types";

const SELECT =
  "rounded border border-border bg-surface px-1.5 py-0.5 font-mono-data text-[10px] text-white";

export function DegradationChart({
  sessionId,
  driver,
}: {
  sessionId?: string;
  driver?: string;
}) {
  const session = useRaceStore((s) => s.session);
  const focused = useFocusDriver();
  const [code, setCode] = useState(driver ?? focused);
  const [stintId, setStintId] = useState<number | "current">(1);
  const [data, setData] = useState<DegradationCurveResponse | null>(null);
  const [pending, setPending] = useState(false);
  const sid = sessionId ?? explainSessionId(session);

  useEffect(() => {
    if (!driver && focused) setCode(focused);
  }, [focused, driver]);

  useEffect(() => {
    let cancelled = false;
    setPending(true);
    const stint = stintId === "current" ? undefined : stintId;
    getDegradationCurve({ session_id: sid, driver: code, stint_id: stint }).then((payload) => {
      if (cancelled) return;
      setData(payload);
      setPending(false);
    });
    return () => {
      cancelled = true;
    };
  }, [sid, code, stintId]);

  const chart = useMemo(() => {
    if (!data) return [];
    return data.tyre_age.map((age, i) => ({
      age,
      predicted: data.predicted_deg_s[i],
      actual: data.actual_deg_s[i],
    }));
  }, [data]);

  const stints = data?.available_stints ?? [];

  return (
    <div className="flex h-full min-h-[240px] flex-col bg-carbon p-2">
      <div className="mb-2 flex flex-wrap items-center gap-2 font-mono-data text-[10px]">
        <span className="text-muted">Driver</span>
        <select value={code} onChange={(e) => setCode(e.target.value)} className={SELECT}>
          {MOCK_DRIVERS_2025.map((d) => (
            <option key={d.driver_code} value={d.driver_code}>
              {d.driver_code}
            </option>
          ))}
        </select>
        <span className="text-muted">Stint</span>
        <select
          value={stintId}
          onChange={(e) => {
            const v = e.target.value;
            setStintId(v === "current" ? "current" : Number(v));
          }}
          className={SELECT}
        >
          <option value="current">Current stint</option>
          {(stints.length ? stints : [{ stint_id: 1, compound: "MEDIUM", start_lap: 1, end_lap: 20 }]).map((s) => (
            <option key={s.stint_id} value={s.stint_id}>
              {s.stint_id} {s.compound} (L{s.start_lap}–{s.end_lap})
            </option>
          ))}
        </select>
        {data && (
          <span className="text-muted">
            {data.compound} · {data.circuit}
          </span>
        )}
      </div>
      <div className="min-h-0 flex-1">
        {pending && !data ? (
          <PanelSkeleton />
        ) : chart.length === 0 ? (
          <PanelEmpty
            title="Degradation curves"
            detail="Predicted versus actual deg over tyre age for the selected stint. Empty until this session has been ingested and explain data is available."
          />
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chart} margin={{ top: 8, right: 12, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
              <XAxis
                dataKey="age"
                stroke="#888888"
                tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
                label={{ value: "Tyre age (laps)", position: "insideBottom", offset: -2, fill: "#888888", fontSize: 10 }}
              />
              <YAxis
                stroke="#888888"
                tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }}
                width={44}
                label={{ value: "Deg (s)", angle: -90, position: "insideLeft", fill: "#888888", fontSize: 10 }}
              />
              <Tooltip
                contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
              />
              <Line type="monotone" dataKey="predicted" name="Predicted" stroke="#e8002d" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Line type="monotone" dataKey="actual" name="Actual" stroke="#f5a623" dot={false} strokeWidth={2} isAnimationActive={false} />
              <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}