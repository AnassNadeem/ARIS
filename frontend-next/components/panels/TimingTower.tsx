"use client";

import { useMemo } from "react";
import { useRaceStore } from "@/store/raceStore";
import { TyreIcon } from "@/components/ui/TyreIcon";
import type { CarState } from "@/lib/types";

function fmtGap(v: number | null): string {
  if (v == null) return "—";
  return v === 0 ? "LEADER" : `+${v.toFixed(1)}s`;
}

function fmtLap(v: number | null): string {
  if (v == null) return "—";
  const m = Math.floor(v / 60);
  const s = (v % 60).toFixed(3);
  return `${m}:${s.padStart(6, "0")}`;
}

export function TimingTower() {
  const cars = useRaceStore((s) => s.cars);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const arisDriver = useRaceStore((s) => s.arisDriver);

  const rows = useMemo(() => {
    const list = Object.values(cars).sort((a, b) => (a.position ?? 99) - (b.position ?? 99));
    if (isARISOn && ghostCar) {
      const insertAt = Math.max(0, (ghostCar.position ?? 1) - 1);
      list.splice(insertAt, 0, ghostCar);
    }
    return list;
  }, [cars, ghostCar, isARISOn]);

  const focus = arisDriver ?? "VER";

  return (
    <div className="flex h-full flex-col overflow-hidden bg-carbon font-mono-data text-[11px]">
      <div className="grid shrink-0 grid-cols-[28px_56px_1fr_64px_84px_28px_36px_44px] gap-2 border-b border-border px-2 py-1.5 text-[10px] uppercase text-muted">
        <span>P</span>
        <span>Driver</span>
        <span />
        <span className="text-right">Gap</span>
        <span className="text-right">Last Lap</span>
        <span className="text-center">Tyre</span>
        <span className="text-right">Age</span>
        <span className="text-right">Stops</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {rows.map((car: CarState) => {
          const isGhost = car.driver_code.startsWith("A_");
          const code = isGhost ? car.driver_code.replace("A_", "") : car.driver_code;
          const isFocus = !isGhost && car.driver_code === focus;
          return (
            <div
              key={car.driver_code}
              className={`grid grid-cols-[28px_56px_1fr_64px_84px_28px_36px_44px] items-center gap-2 border-b border-border/60 px-2 py-1.5 ${
                isGhost ? "bg-surface/60" : isFocus ? "border-l-2 border-l-red bg-surface" : ""
              }`}
            >
              <span className="text-white">{car.position ?? "—"}</span>
              <span className="flex items-center gap-1.5 text-white">
                <span className="h-2 w-1 rounded-sm" style={{ background: car.team_colour }} />
                {isGhost ? <span className="text-amber">[A]</span> : null}
                {code}
              </span>
              <span />
              <span className="text-right text-muted">{fmtGap(car.gap_to_leader_s)}</span>
              <span className="text-right text-white">{fmtLap(car.last_lap_s)}</span>
              <span className="flex justify-center">
                <TyreIcon compound={car.compound} />
              </span>
              <span className="text-right text-muted">{car.tyre_life}</span>
              <span className="text-right text-muted">{car.pit_stops}</span>
            </div>
          );
        })}
        {rows.length === 0 && (
          <div className="p-4 text-center text-muted">Waiting for timing data…</div>
        )}
      </div>
    </div>
  );
}
