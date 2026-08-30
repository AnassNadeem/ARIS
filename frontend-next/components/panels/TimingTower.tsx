"use client";

import { memo, useMemo } from "react";
import { useRaceStore } from "@/store/raceStore";
import { TyreIcon } from "@/components/ui/TyreIcon";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { timingEqual } from "@/lib/mapCars";
import { driverOutOfRace, fmtGap, fmtLapTime, fmtSectorTime, sectorClass } from "@/lib/timingDisplay";
import type { CarState } from "@/lib/types";

const TOWER_COLS = "grid-cols-[28px_48px_58px_72px_72px_52px_52px_52px_28px_32px_40px]";

function fmtGhostDelta(v: number): string {
  if (v > 0) return `+${v.toFixed(1)}s ↑`;
  if (v < 0) return `${v.toFixed(1)}s ↓`;
  return "±0.0s";
}

const TimingRow = memo(function TimingRow({
  car,
  isFocus,
  onFocus,
}: {
  car: CarState;
  isFocus: boolean;
  onFocus: (code: string) => void;
}) {
  const isGhost = car.driver_code.startsWith("A_");
  const code = isGhost ? car.driver_code.replace("A_", "") : car.driver_code;
  const out = driverOutOfRace(car.status, car.is_dnf);
  return (
    <div
      onClick={() => {
        if (!isGhost) onFocus(car.driver_code);
      }}
      title={
        isGhost
          ? `ARIS from lap 1: ${car.aris_action || "strategy"}${
              car.divergence_lap ? ` · vs ${car.real_action ?? "real"}` : ""
            }`
          : undefined
      }
      className={`grid h-8 ${TOWER_COLS} items-center gap-x-2 px-2 ${
        isGhost
          ? "cursor-default border-y border-white/35"
          : `cursor-pointer border-b border-border/60 ${
              isFocus ? "border-l-2 border-l-red bg-surface" : ""
            }`
      } ${out ? "opacity-45" : ""}`}
      style={
        isGhost
          ? {
              background: "rgba(232, 236, 242, 0.16)",
              boxShadow: "inset 0 0 10px rgba(255,255,255,0.22)",
            }
          : undefined
      }
    >
      <span className="text-white">{car.position ?? "—"}</span>
      <span className="flex items-center gap-1 text-white">
        {isGhost ? (
          <>
            <span className="h-2 w-1 rounded-sm bg-white/80" />
            <span className="font-semibold tracking-wide text-white">ARIS</span>
          </>
        ) : (
          <>
            <span className="h-2 w-1 rounded-sm" style={{ background: car.team_colour }} />
            <span>{code}</span>
          </>
        )}
      </span>
      {isGhost ? (
        <span
          className={`text-right font-semibold ${
            (car.ghost_cumulative_delta ?? 0) >= 0 ? "text-green-400" : "text-red-400"
          }`}
        >
          {car.ghost_cumulative_delta != null ? fmtGhostDelta(car.ghost_cumulative_delta) : "—"}
        </span>
      ) : (
        <span className="text-right text-muted">{fmtGap(car.gap_to_leader_s, car.laps_down)}</span>
      )}
      <span className="text-right text-white">{isGhost ? "—" : fmtLapTime(car.last_lap_s)}</span>
      <span className="flex items-center justify-end gap-0.5 text-right text-white">
        {car.fastest_lap ? <span className="text-[9px] text-[#c44dff]">FL</span> : null}
        {isGhost ? "—" : fmtLapTime(car.best_lap_s)}
      </span>
      <span className={`text-right tabular-nums ${sectorClass(car.s1_colour)}`}>{isGhost ? "—" : fmtSectorTime(car.sector1_s)}</span>
      <span className={`text-right tabular-nums ${sectorClass(car.s2_colour)}`}>{isGhost ? "—" : fmtSectorTime(car.sector2_s)}</span>
      <span className={`text-right tabular-nums ${sectorClass(car.s3_colour)}`}>{isGhost ? "—" : fmtSectorTime(car.sector3_s)}</span>
      <span className="flex justify-center">
        <TyreIcon compound={car.compound} />
      </span>
      <span className="text-right text-muted">{car.tyre_life}</span>
      <span className="text-right text-muted">
        {out ? car.status : (car.laps_completed ?? car.lap_number)}
      </span>
    </div>
  );
}, (prev, next) => prev.isFocus === next.isFocus && prev.onFocus === next.onFocus && timingEqual(prev.car, next.car));

export function TimingTower() {
  const cars = useRaceStore((s) => s.cars);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const racePhase = useRaceStore((s) => s.racePhase);
  const currentLap = useRaceStore((s) => s.currentLap);
  const setFocusDriver = useRaceStore((s) => s.setFocusDriver);
  const focus = useFocusDriver("");
  const loading = usePanelFeedLoading();

  const rows = useMemo(() => {
    const list = Object.values(cars).sort((a, b) => (a.position ?? 99) - (b.position ?? 99));
    if (isARISOn && ghostCar) {
      const insertAt = Math.max(0, (ghostCar.position ?? 1) - 1);
      list.splice(insertAt, 0, ghostCar);
    }
    return list;
  }, [cars, ghostCar, isARISOn]);

  const banner =
    racePhase === "SC"
      ? `SC DEPLOYED — Lap ${currentLap}`
      : racePhase === "VSC"
        ? `VSC DEPLOYED — Lap ${currentLap}`
        : racePhase === "RED_FLAG"
          ? `RED FLAG — Lap ${currentLap}`
          : null;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-carbon font-mono-data text-[11px] [overflow-anchor:none]">
      {banner && (
        <div className="h-7 shrink-0 bg-[#FF8700]/20 px-2 py-1 text-center text-[10px] font-semibold uppercase text-[#FF8700]">
          {banner}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-auto [overflow-anchor:none]">
        <div className="min-w-[620px]">
          <div className={`grid h-8 shrink-0 ${TOWER_COLS} gap-x-2 border-b border-border px-2 py-2 font-sans text-[10px] uppercase text-muted`}>
            <span>P</span>
            <span>Drv</span>
            <span className="text-right">Gap</span>
            <span className="text-right">Last</span>
            <span className="text-right">Best</span>
            <span className="text-right">S1</span>
            <span className="text-right">S2</span>
            <span className="text-right">S3</span>
            <span className="text-center">Ty</span>
            <span className="text-right">Age</span>
            <span className="text-right">Laps</span>
          </div>
          <div>
            {loading && rows.length === 0 ? (
              <PanelSkeleton rows={12} />
            ) : rows.length === 0 ? (
              <PanelEmpty
                title="Timing tower"
                detail="Position, gap, last lap, and tyre for the field. Empty until the first timing frame arrives from replay or live."
              />
            ) : (
              rows.map((car) => (
                <TimingRow
                  key={car.driver_code}
                  car={car}
                  isFocus={!car.driver_code.startsWith("A_") && car.driver_code === focus}
                  onFocus={setFocusDriver}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
