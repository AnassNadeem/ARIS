"use client";

import { COMPOUND_COLOUR } from "@/lib/mockData";
import { usePanelHistory } from "@/lib/usePanelHistory";
import { useRaceStore } from "@/store/raceStore";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

export function TyreStrategyBar() {
  const { stints, drivers, totalLaps } = usePanelHistory();
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const ghostTicks = useRaceStore((s) => s.ghostTicksByLap);
  const loading = usePanelFeedLoading();
  const distance = Math.max(1, totalLaps);
  const ghostStints = Object.values(ghostTicks)
    .sort((a, b) => a.lap - b.lap)
    .reduce<Array<{ compound: string; startLap: number; endLap: number }>>((acc, tick) => {
      const last = acc[acc.length - 1];
      if (!last || last.compound !== tick.compound) {
        acc.push({ compound: tick.compound, startLap: tick.lap, endLap: tick.lap });
      } else {
        last.endLap = tick.lap;
      }
      return acc;
    }, []);

  if (loading && stints.length === 0) {
    return <PanelSkeleton rows={10} />;
  }
  if (stints.length === 0) {
    return (
      <PanelEmpty
        title="Tyre strategy"
        detail="Every driver's compounds as a bar across race distance. Empty until stint data loads from the session."
      />
    );
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-carbon p-2 font-mono-data text-xs">
      {drivers.map((d) => {
        const rows = stints.filter((s) => s.driverCode === d.driver_code);
        return (
          <div key={d.driver_code} className="mb-2 flex items-center gap-2">
            <span className="w-10 shrink-0 text-white">{d.driver_code}</span>
            <div className="relative flex h-4 flex-1 overflow-hidden rounded-sm bg-surface">
              {rows.map((s, i) => (
                <div
                  key={i}
                  className="h-full border-r border-carbon/60 transition-[filter,opacity] duration-200 hover:brightness-110"
                  style={{
                    width: `${((s.endLap - s.startLap + 1) / distance) * 100}%`,
                    background: COMPOUND_COLOUR[s.compound],
                  }}
                  title={`${s.compound} L${s.startLap}-${s.endLap}`}
                />
              ))}
            </div>
          </div>
        );
      })}
      {isARISOn && ghostStints.length > 0 && (
        <div className="mb-2 mt-1 flex items-center gap-2">
          <span className="w-10 shrink-0 text-red">ARIS</span>
          <div className="relative flex h-4 flex-1 overflow-hidden rounded-sm bg-surface ring-1 ring-red/60">
            {ghostStints.map((s, i) => (
              <div
                key={i}
                className="h-full border-r border-carbon/60 transition-[filter,opacity] duration-200 hover:brightness-110"
                style={{
                  width: `${((s.endLap - s.startLap + 1) / distance) * 100}%`,
                  background: COMPOUND_COLOUR[s.compound as keyof typeof COMPOUND_COLOUR] ?? "#e8002d",
                }}
                title={`ARIS ${s.compound} L${s.startLap}-${s.endLap}`}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
