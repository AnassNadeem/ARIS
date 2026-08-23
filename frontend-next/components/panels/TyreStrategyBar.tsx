"use client";

import { getRaceHistoryMock, TOTAL_LAPS_MOCK } from "@/lib/mockRaceHistory";
import { COMPOUND_COLOUR, MOCK_DRIVERS_2025 } from "@/lib/mockData";

export function TyreStrategyBar() {
  const { stints } = getRaceHistoryMock();

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-carbon p-2 font-mono-data text-[10px]">
      {MOCK_DRIVERS_2025.map((d) => {
        const rows = stints.filter((s) => s.driverCode === d.driver_code);
        return (
          <div key={d.driver_code} className="mb-1.5 flex items-center gap-2">
            <span className="w-10 shrink-0 text-white">{d.driver_code}</span>
            <div className="relative flex h-4 flex-1 overflow-hidden rounded-sm bg-surface">
              {rows.map((s, i) => (
                <div
                  key={i}
                  className="h-full border-r border-carbon/60"
                  style={{
                    width: `${((s.endLap - s.startLap + 1) / TOTAL_LAPS_MOCK) * 100}%`,
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
