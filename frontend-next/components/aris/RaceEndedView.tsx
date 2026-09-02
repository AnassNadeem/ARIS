"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { explainFeatureEnabled, explainSessionId, getGhostVsReal } from "@/lib/api";
import { useRaceStore } from "@/store/raceStore";
import { raceFinishSummary } from "@/lib/debriefSummary";
import type { GhostVsRealResponse } from "@/lib/types";

export function RaceEndedView() {
  const session = useRaceStore((s) => s.session);
  const arisDriver = useRaceStore((s) => s.arisDriver ?? s.focusDriver ?? session?.driverCode);
  const ghostData = useRaceStore((s) => s.ghostData);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const ghostTicks = useRaceStore((s) => s.ghostTicksByLap);
  const cars = useRaceStore((s) => s.cars);
  const field = useRaceStore((s) => s.r2RaceField);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const ghostReason = useRaceStore((s) => s.ghostReason);
  const setExplainTabRequest = useRaceStore((s) => s.setExplainTabRequest);
  const setRaceFinished = useRaceStore((s) => s.setRaceFinished);
  const [compare, setCompare] = useState<GhostVsRealResponse | null>(null);

  const sid = explainSessionId(session);

  useEffect(() => {
    if (!arisDriver) return;
    let cancelled = false;
    getGhostVsReal({ session_id: sid, driver: arisDriver }).then((payload) => {
      if (!cancelled) setCompare(payload);
    });
    return () => {
      cancelled = true;
    };
  }, [sid, arisDriver]);

  const lastDelta = ghostData?.delta_history?.at(-1)?.delta ?? ghostData?.ghost_cumulative_delta;
  const finish = useMemo(() => {
    if (!arisDriver) return null;
    return raceFinishSummary({
      driver: arisDriver,
      field,
      cars,
      ghostCar,
      ghostTicks,
    });
  }, [arisDriver, field, cars, ghostCar, ghostTicks]);
  const summary = useMemo(() => {
    if (finish && (finish.realPos != null || finish.ghostPos != null)) return finish;
    if (!compare?.real?.laps?.length) return null;
    const n = compare.real.laps.length;
    const last = n - 1;
    return {
      realPos: compare.real.position[last],
      ghostPos: compare.ghost.position[last],
      realGap: compare.real.gap_to_leader[last],
      ghostGap: compare.ghost.gap_to_leader[last],
      posDelta: compare.delta.position_delta[last],
      gapDelta: compare.delta.gap_delta[last],
    };
  }, [finish, compare]);

  return (
    <div className="absolute inset-0 z-[85] flex items-center justify-center bg-carbon/80 p-4 backdrop-blur-[2px]">
      <div className="w-full max-w-lg rounded-[12px] border border-border bg-surface-2 p-5 shadow-2xl">
        <div className="font-mono-data text-[10px] uppercase tracking-[0.2em] text-muted">Race ended</div>
        <h2 className="mt-1 text-xl font-bold text-white">
          {session?.circuitName ?? "Session"} · {session?.year}
        </h2>
        <p className="mt-1 font-mono-data text-[11px] text-muted">
          {isARISOn && arisDriver ? `ARIS for ${arisDriver} vs real ${arisDriver}` : "Replay finished."}
        </p>

        {isARISOn && ghostReason === "driver_did_not_race" && (
          <p role="alert" className="mt-4 rounded border border-amber/40 bg-amber/10 p-3 font-mono-data text-[11px] text-amber">
            {arisDriver} did not start this race (DNS). ARIS could not compute a ghost car.
          </p>
        )}

        {isARISOn && ghostReason !== "driver_did_not_race" && (
          <div className="mt-4 grid grid-cols-2 gap-3 font-mono-data text-[11px]">
            <div className="rounded border border-border bg-carbon p-3">
              <div className="text-[9px] uppercase text-muted">ARIS (timing tower)</div>
              <div className="mt-1 text-white">P{summary?.ghostPos ?? ghostData?.ghost_position ?? "—"}</div>
              <div className="text-muted">Gap {summary?.ghostGap != null ? `${summary.ghostGap.toFixed(1)}s` : "—"}</div>
            </div>
            <div className="rounded border border-border bg-carbon p-3">
              <div className="text-[9px] uppercase text-muted">Real finish</div>
              <div className="mt-1 text-white">P{summary?.realPos ?? "—"}</div>
              <div className="text-muted">Gap {summary?.realGap != null ? `${summary.realGap.toFixed(1)}s` : "—"}</div>
            </div>
          </div>
        )}

        {lastDelta != null && ghostReason !== "driver_did_not_race" && (
          <p className="mt-3 font-mono-data text-[12px] text-white">
            Estimated delta:{" "}
            <span className={lastDelta >= 0 ? "text-green-400" : "text-red-400"}>
              {lastDelta >= 0 ? "+" : ""}
              {lastDelta.toFixed(1)}s
            </span>{" "}
            {lastDelta >= 0 ? "(ARIS ahead)" : "(real ahead)"}
          </p>
        )}

        {ghostData && (
          <p className="mt-2 font-mono-data text-[10px] text-muted">
            Diverged L{ghostData.divergence_lap}: {ghostData.aris_action} vs {ghostData.real_action}
            {ghostData.outcome ? ` · ${ghostData.outcome.replaceAll("_", " ")}` : ""}
          </p>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          {explainFeatureEnabled() && (
            <button
            type="button"
            onClick={() => {
              setExplainTabRequest("debrief");
              setRaceFinished(false);
            }}
              className="rounded bg-red px-4 py-2 font-mono-data text-[11px] uppercase text-white"
            >
              Open Race Debrief
            </button>
          )}
          {isARISOn && (
            <Link
              href="/replay"
              className="rounded border border-red bg-red/10 px-4 py-2 font-mono-data text-[11px] uppercase text-red hover:bg-red/20"
            >
              Choose another race
            </Link>
          )}
          <button
            type="button"
            onClick={() => setRaceFinished(false)}
            className="rounded border border-border px-4 py-2 font-mono-data text-[11px] uppercase text-muted hover:text-white"
          >
            Dismiss
          </button>
        </div>
      </div>
    </div>
  );
}
