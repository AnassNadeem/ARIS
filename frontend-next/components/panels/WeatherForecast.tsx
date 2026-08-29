"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRaceStore } from "@/store/raceStore";
import { mockWeatherForecast } from "@/lib/mockData";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

const CONDITION_ICON: Record<string, string> = { sun: "☀", cloud: "⛅", rain: "🌧" };

export function WeatherForecast() {
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const currentLap = useRaceStore((s) => s.currentLap);
  const loading = usePanelFeedLoading();
  const { sessions, trend } = useMemo(
    () => mockWeatherForecast(Math.max(1, totalLaps)),
    [totalLaps],
  );

  if (loading && totalLaps <= 0) {
    return <PanelSkeleton />;
  }
  if (totalLaps <= 0) {
    return (
      <PanelEmpty
        title="Weather forecast"
        detail="Session-by-session air/track temperature and rain chance over race distance. Empty until total laps arrive from the session payload."
      />
    );
  }

  return (
    <div className="flex h-full flex-col bg-carbon p-2">
      <div className="mb-2 grid shrink-0 grid-cols-5 gap-1.5">
        {sessions.map((s) => (
          <div key={s.session} className="flex flex-col items-center gap-0.5 rounded border border-border bg-surface py-1.5">
            <span className="font-sans text-[10px] uppercase text-muted">{s.session}</span>
            <span className="text-base leading-none">{CONDITION_ICON[s.condition]}</span>
            <span className="font-mono-data text-xs text-white">{s.airTempC}°C</span>
            <span className="font-mono-data text-[10px] text-muted-2">{s.rainChancePct}% rain</span>
          </div>
        ))}
      </div>
      <div className="min-h-0 flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={trend} margin={{ top: 4, right: 8, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
            <XAxis dataKey="lap" stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 9 }} />
            <YAxis stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 9 }} width={32} />
            <Tooltip
              contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
            />
            <Area
              type="monotone"
              dataKey="trackTempC"
              name="Track °C"
              stroke="#E8002D"
              fill="#E8002D"
              fillOpacity={0.12}
              isAnimationActive={false}
            />
            <Line type="monotone" dataKey="airTempC" name="Air °C" stroke="#39FF14" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            <Line type="monotone" dataKey="rainChancePct" name="Rain %" stroke="#4FA8E0" dot={false} strokeWidth={1.5} isAnimationActive={false} />
            <ReferenceLine x={currentLap} stroke="#888888" strokeDasharray="3 3" />
            <Legend wrapperStyle={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
