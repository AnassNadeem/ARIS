"use client";

import { COMPOUND_COLOUR } from "@/lib/mockData";
import { usePanelHistory } from "@/lib/usePanelHistory";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";

export function TyreStrategyBar() {
  const { stints, drivers, totalLaps } = usePanelHistory();
  const loading = usePanelFeedLoading();
  const distance = Math.max(1, totalLaps);

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
                  className="h-full border-r border-carbon/60"
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
    </div>
  );
}
