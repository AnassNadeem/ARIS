"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { useRaceStore } from "@/store/raceStore";
import { TyreIcon } from "@/components/ui/TyreIcon";
import { PanelEmpty, PanelSkeleton, usePanelFeedLoading } from "@/components/ui/PanelStates";
import { useFocusDriver } from "@/lib/useFocusDriver";
import { isGhostRow, orderTimingTower, timingEqual } from "@/lib/mapCars";
import { driverOutOfRace, fmtGap, fmtLapTime, fmtSectorTime, sectorClass } from "@/lib/timingDisplay";
import type { CarState } from "@/lib/types";

const TOWER_COLS = "grid-cols-[28px_82px_60px_72px_72px_52px_52px_52px_28px_32px_40px]";
const PIT_CHURN_MS = 2000;

export type TowerFlashKind = "gain" | "loss" | "pit";

function fmtGhostDelta(v: number): string {
  if (v > 0) return `+${v.toFixed(1)}s`;
  if (v < 0) return `${v.toFixed(1)}s`;
  return "±0.0s";
}

function useTowerFlashes(rows: CarState[]): Record<string, { kind: TowerFlashKind; at: number }> {
  const [flashes, setFlashes] = useState<Record<string, { kind: TowerFlashKind; at: number }>>({});
  const prevRef = useRef<Map<string, { position: number; is_pitted: boolean }>>(new Map());
  const pitChurnUntil = useRef(0);

  useEffect(() => {
    const now = performance.now();
    const prev = prevRef.current;
    const next = new Map<string, { position: number; is_pitted: boolean }>();
    const pitEntered = rows.some((c) => {
      const before = prev.get(c.driver_code);
      return Boolean(c.is_pitted || c.ghost_in_pits) && before?.is_pitted === false;
    });
    if (pitEntered) pitChurnUntil.current = now + PIT_CHURN_MS;
    const churn = now < pitChurnUntil.current;
    const patch: Record<string, { kind: TowerFlashKind; at: number }> = {};
    for (const car of rows) {
      const pos = car.position != null && car.position > 0 ? car.position : 99;
      const pitted = Boolean(car.is_pitted || car.ghost_in_pits);
      const before = prev.get(car.driver_code);
      next.set(car.driver_code, { position: pos, is_pitted: pitted });
      if (!before) continue;
      if (pitted && !before.is_pitted) {
        patch[car.driver_code] = { kind: "pit", at: now };
        continue;
      }
      if (churn || pitted) continue;
      if (pos < before.position) patch[car.driver_code] = { kind: "gain", at: now };
      else if (pos > before.position) patch[car.driver_code] = { kind: "loss", at: now };
    }
    prevRef.current = next;
    if (Object.keys(patch).length) {
      setFlashes((cur) => ({ ...cur, ...patch }));
    }
  }, [rows]);

  return flashes;
}

const TimingRow = memo(function TimingRow({
  car,
  isFocus,
  onFocus,
  flash,
}: {
  car: CarState;
  isFocus: boolean;
  onFocus: (code: string) => void;
  flash: { kind: TowerFlashKind; at: number } | null;
}) {
  const isGhost = isGhostRow(car);
  const code = isGhost ? car.driver_code.replace("A_", "") : car.driver_code;
  const out = driverOutOfRace(car.status, car.is_dnf);
  const ghostDelta = car.ghost_delta_s;
  return (
    <div
      data-testid={isGhost ? "ghost-tower-row" : `tower-row-${car.driver_code}`}
      data-dnf={car.is_dnf ? "true" : "false"}
      data-position={car.position ?? ""}
      data-flash={flash?.kind ?? ""}
      data-is-ghost={isGhost ? "true" : "false"}
      data-ghost-delta={ghostDelta != null ? String(ghostDelta) : ""}
      data-delta-vs={car.ghost_delta_vs ?? ""}
      onClick={() => {
        if (!isGhost) onFocus(car.driver_code);
      }}
      title={
        isGhost
          ? `ARIS from lap 1: ${car.aris_action || "strategy"}${
              car.divergence_lap ? ` · vs ${car.real_action ?? "real"}` : ""
            }${
              car.ghost_delta_vs && ghostDelta != null
                ? ` · ${fmtGhostDelta(ghostDelta)} vs ${car.ghost_delta_vs}`
                : ""
            }`
          : undefined
      }
      className={`relative grid h-8 ${TOWER_COLS} items-center gap-x-2 px-2 ${
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
      {flash ? <span key={flash.at} className={`tower-flash-${flash.kind}`} /> : null}
      <span className="text-white">{car.position ?? "—"}</span>
      <span className="flex items-center gap-1 text-white">
        {isGhost ? (
          <>
            <span className="h-2 w-1 rounded-sm bg-white/80" />
            <span className="font-semibold tracking-wide text-white">ARIS</span>
            {car.ghost_delta_s != null && (
              <span
                className={`text-[9px] font-semibold ${
                  car.ghost_delta_s >= 0 ? "text-green-400" : "text-red-400"
                }`}
                title={
                  car.ghost_delta_vs
                    ? `Gap to ${car.ghost_delta_vs} (adjacent classified car)`
                    : "Gap to adjacent classified car"
                }
              >
                {car.ghost_delta_s >= 0 ? "▲" : "▼"}
                {fmtGhostDelta(car.ghost_delta_s)}
              </span>
            )}
          </>
        ) : (
          <>
            <span className="h-2 w-1 rounded-sm" style={{ background: car.team_colour }} />
            <span>{code}</span>
          </>
        )}
      </span>
      <span className="text-right text-muted">
        {isGhost && car.ghost_in_pits ? (
          <span className="font-semibold text-white">IN PITS</span>
        ) : (
          fmtGap(car.gap_to_leader_s, car.laps_down)
        )}
      </span>
      <span className="text-right text-white">{isGhost ? "—" : fmtLapTime(car.last_lap_s)}</span>
      <span className="flex items-center justify-end gap-0.5 text-right text-white">
        {car.fastest_lap ? <span className="text-[9px] text-[#c44dff]">FL</span> : null}
        {isGhost ? "—" : fmtLapTime(car.best_lap_s)}
      </span>
      <span className={`text-right tabular-nums ${sectorClass(car.s1_colour)}`}>{isGhost ? "—" : fmtSectorTime(car.sector1_s)}</span>
      <span className={`text-right tabular-nums ${sectorClass(car.s2_colour)}`}>{isGhost ? "—" : fmtSectorTime(car.sector2_s)}</span>
      <span className={`text-right tabular-nums ${sectorClass(car.s3_colour)}`}>{isGhost ? "—" : fmtSectorTime(car.sector3_s)}</span>
      <span className="flex justify-center">
        <TyreIcon compound={isGhost && car.ghost_in_pits && car.ghost_pit_compound ? car.ghost_pit_compound : car.compound} />
      </span>
      <span className="text-right text-muted">{isGhost && car.ghost_in_pits ? "—" : car.tyre_life}</span>
      <span className="text-right text-muted">
        {isGhost && car.ghost_in_pits
          ? "PIT"
          : out
            ? car.status
            : (car.laps_completed ?? car.lap_number)}
      </span>
    </div>
  );
}, (prev, next) =>
  prev.isFocus === next.isFocus &&
  prev.onFocus === next.onFocus &&
  prev.flash?.kind === next.flash?.kind &&
  prev.flash?.at === next.flash?.at &&
  timingEqual(prev.car, next.car),
);

export function TimingTower() {
  const cars = useRaceStore((s) => s.cars);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const racePhase = useRaceStore((s) => s.racePhase);
  const currentLap = useRaceStore((s) => s.currentLap);
  const consolePlayState = useRaceStore((s) => s.consolePlayState);
  const consoleMode = useRaceStore((s) => s.consoleMode);
  const setFocusDriver = useRaceStore((s) => s.setFocusDriver);
  const focus = useFocusDriver("");
  const loading = usePanelFeedLoading();

  const preRace = consoleMode !== "live" && consolePlayState !== "racing";

  const rows = useMemo(() => {
    // Tower ghost is independent of NEXT_PUBLIC_ARIS_GHOST_MAP (map-dot only).
    const list = Object.values(cars).filter((c) => !isGhostRow(c));
    const ghost = isARISOn && ghostCar ? { ...ghostCar, is_ghost: true as const } : null;
    return orderTimingTower(ghost ? [...list, ghost] : list);
  }, [cars, ghostCar, isARISOn]);

  const flashes = useTowerFlashes(rows);

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
        <div className="min-w-[660px]">
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
                detail={
                  preRace && rows.length === 0
                    ? "Grid order appears once the race pack loads. Last-lap and sector times stay blank until you click Start Race."
                    : "Position, gap, last lap, and tyre for the field. Empty until the first timing frame arrives from replay or live."
                }
              />
            ) : (
              rows.map((car) => (
                <TimingRow
                  key={car.driver_code}
                  car={car}
                  flash={flashes[car.driver_code] ?? null}
                  isFocus={!isGhostRow(car) && car.driver_code === focus}
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
