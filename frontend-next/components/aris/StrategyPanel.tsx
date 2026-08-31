"use client";

import { useRaceStore } from "@/store/raceStore";
import { buildStintPlan, currentStintIndex } from "@/lib/arisRecommend";
import { TyreIcon } from "@/components/ui/TyreIcon";
import { normalizeCompound } from "@/lib/compounds";

/**
 * ARIS's recommended stint plan for the chosen driver. Always reflects the
 * ghost's actual pit laps — if this says the ghost pits on lap 28, the ghost
 * disappears from the track map on lap 28. Never a second source of truth.
 */
export function StrategyPanel() {
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const activeStrategy = useRaceStore((s) => s.activeStrategy);
  const currentLap = useRaceStore((s) => s.currentLap);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const revised = useRaceStore((s) => s.strategyRevisedAt);

  if (!isARISOn || !activeStrategy) return null;

  const segments = buildStintPlan(activeStrategy, totalLaps);
  if (!segments.length) return null;
  const curIdx = currentStintIndex(segments, currentLap);

  return (
    <div data-testid="strategy-panel" className="mb-2 rounded border border-border bg-surface/60 p-2">
      <div className="mb-1.5 flex items-center justify-between">
        <span className="font-mono-data text-[10px] uppercase tracking-wide text-muted">ARIS Strategy</span>
        <span className="font-mono-data text-[9px] text-muted-2">{activeStrategy.name}</span>
      </div>
      {revised && (
        <div
          data-testid="strategy-revised-marker"
          className="mb-1.5 rounded border border-amber/50 bg-amber/10 px-1.5 py-1 font-mono-data text-[9px] uppercase tracking-wide text-amber"
        >
          REVISED LAP {revised.lap} — {revised.reason}
        </div>
      )}
      <div className="flex flex-col gap-1">
        {segments.map((seg, i) => {
          const isCurrent = i === curIdx;
          return (
            <div
              key={seg.index}
              data-testid={isCurrent ? "strategy-current-stint" : undefined}
              className={`flex items-center gap-2 rounded px-1.5 py-1 font-mono-data text-[10px] ${
                isCurrent ? "bg-red/15 text-white ring-1 ring-red/50" : "text-muted"
              }`}
            >
              <TyreIcon compound={normalizeCompound(seg.compound)} />
              <span className="w-14">
                L{seg.startLap}
                {seg.endLap != null ? `–${seg.endLap}` : "+"}
              </span>
              <span className="flex-1">{seg.compound}</span>
              {isCurrent && <span className="text-[9px] uppercase text-red">● current</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
