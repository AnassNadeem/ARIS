"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { downloadDebriefExport, explainSessionId, getRaceDebrief } from "@/lib/api";
import { COMPOUND_COLOUR, MOCK_DRIVERS_2025 } from "@/lib/mockData";
import { useRaceStore } from "@/store/raceStore";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { PanelEmpty, PanelSkeleton } from "@/components/ui/PanelStates";
import type { Compound, RaceDebriefResponse } from "@/lib/types";

const SELECT =
  "rounded border border-border bg-surface px-1.5 py-0.5 font-mono-data text-[10px] text-white";

export function RaceDebriefView({
  sessionId,
  focusDriver,
}: {
  sessionId?: string;
  focusDriver?: string;
}) {
  const session = useRaceStore((s) => s.session);
  const focused = useFocusDriver();
  const [code, setCode] = useState(focusDriver ?? focused);

  useEffect(() => {
    if (!focusDriver && focused) setCode(focused);
  }, [focused, focusDriver]);
  const [data, setData] = useState<RaceDebriefResponse | null>(null);
  const [pending, setPending] = useState(false);
  const sid = sessionId ?? explainSessionId(session);

  useEffect(() => {
    let cancelled = false;
    setPending(true);
    getRaceDebrief({ session_id: sid, focus_driver: code }).then((payload) => {
      if (cancelled) return;
      setData(payload);
      setPending(false);
    });
    return () => {
      cancelled = true;
    };
  }, [sid, code]);

  const currentLap = useRaceStore((s) => s.currentLap) || 1;
  const cap = Math.max(1, currentLap);

  const pits = useMemo(() => {
    return (data?.timeline.pit_stops ?? [])
      .filter((p) => p.lap <= cap)
      .map((p) => ({
        lap: p.lap,
        y: 1,
        compound: (p.compound_out ?? "HARD") as Compound,
        label: `${p.compound_in ?? "?"}→${p.compound_out ?? "?"}`,
      }));
  }, [data, cap]);

  const storeTotal = useRaceStore((s) => s.totalLaps);
  const total = data?.metadata.total_laps ?? (storeTotal > 0 ? storeTotal : 1);

  return (
    <div className="flex h-full min-h-[280px] flex-col overflow-hidden bg-carbon p-2">
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
            {data.metadata.circuit} {data.metadata.season} · {data.metadata.total_laps} laps
          </span>
        )}
        <button
          type="button"
          onClick={() => downloadDebriefExport(sid, code)}
          className="ml-auto rounded border border-border px-2 py-0.5 text-muted hover:border-white hover:text-white"
        >
          Export
        </button>
      </div>
      {pending && !data ? (
        <PanelSkeleton />
      ) : !data ? (
        <PanelEmpty
          title="Race debrief"
          detail="Pit timeline and recommend() top-3 at each decision. Empty until this session has been ingested and debrief data is available."
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="h-[120px] min-h-[120px]">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
                <CartesianGrid stroke="#2a2a2a" strokeDasharray="2 4" />
                <XAxis type="number" dataKey="lap" domain={[1, total]} stroke="#888888" tick={{ fontFamily: "var(--font-jbmono)", fontSize: 10 }} />
                <YAxis type="number" dataKey="y" domain={[0, 2]} hide />
                {(data?.timeline.sc_vsc_periods ?? [])
                  .filter((p) => p.start_lap <= cap)
                  .map((p) => (
                  <ReferenceArea
                    key={`sc-${p.start_lap}-${p.end_lap}`}
                    x1={p.start_lap}
                    x2={Math.min(p.end_lap, cap)}
                    fill={p.kind === "VSC" ? "#FF8700" : "#FF8700"}
                    fillOpacity={p.kind === "VSC" ? 0.2 : 0.35}
                  />
                ))}
                {(data?.timeline.rain_periods ?? [])
                  .filter((p) => p.start_lap <= cap)
                  .map((p) => (
                  <ReferenceArea
                    key={`rain-${p.start_lap}-${p.end_lap}`}
                    x1={p.start_lap}
                    x2={Math.min(p.end_lap, cap)}
                    fill="#1E90FF"
                    fillOpacity={0.2}
                  />
                ))}
                <Tooltip
                  contentStyle={{ background: "#1a1a1a", border: "1px solid #2a2a2a", fontFamily: "var(--font-jbmono)", fontSize: 11 }}
                  formatter={(_v, _n, item) => {
                    const payload = item?.payload as { label?: string; lap?: number } | undefined;
                    return [`L${payload?.lap ?? ""} ${payload?.label ?? "pit"}`, "Pit"];
                  }}
                />
                <Scatter
                  data={pits}
                  isAnimationActive={false}
                  shape={(props: { cx?: number; cy?: number; payload?: { compound: Compound } }) => (
                    <circle
                      cx={props.cx}
                      cy={props.cy}
                      r={6}
                      fill={COMPOUND_COLOUR[props.payload?.compound ?? "HARD"]}
                      stroke="#0a0a0a"
                    />
                  )}
                />
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 space-y-2">
            {(data?.decisions ?? [])
              .filter((d) => d.lap <= cap)
              .map((d) => (
              <div key={`${d.lap}-${d.type}`} className="rounded border border-border bg-surface p-2">
                <div className="flex flex-wrap items-baseline gap-2 font-mono-data text-[10px]">
                  <span className="text-red">L{d.lap}</span>
                  <span className="uppercase text-muted">{d.type}</span>
                  <span className="text-white">Team {d.chosen_action}</span>
                  {d.aris_action && <span className="text-muted">ARIS {d.aris_action}</span>}
                </div>
                <table className="mt-1 w-full border-collapse font-mono-data text-[10px] text-white/90">
                  <thead>
                    <tr className="text-muted">
                      <th className="px-1 py-0.5 text-left font-normal">#</th>
                      <th className="px-1 py-0.5 text-left font-normal">recommend()</th>
                      <th className="px-1 py-0.5 text-right font-normal">Δ vs stay</th>
                      <th className="px-1 py-0.5 text-right font-normal">P(best)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.recommend_top3.map((r) => (
                      <tr key={`${r.rank}-${r.label}`}>
                        <td className="px-1 py-0.5">{r.rank}</td>
                        <td className="px-1 py-0.5">{r.label}</td>
                        <td className="px-1 py-0.5 text-right">
                          {r.delta_vs_stay_out_s == null ? "—" : `${r.delta_vs_stay_out_s.toFixed(1)}s`}
                        </td>
                        <td className="px-1 py-0.5 text-right">
                          {r.p_best == null ? "—" : r.p_best.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {d.why && (
                  <p className="mt-1 font-mono-data text-[11px] leading-relaxed text-white">
                    <span className="uppercase text-red">Why: </span>
                    {d.why}
                  </p>
                )}
                {d.explanation && (
                  <p className="mt-0.5 font-mono-data text-[10px] leading-relaxed text-white/60">{d.explanation}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}