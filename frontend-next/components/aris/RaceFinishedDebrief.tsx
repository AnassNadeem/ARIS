"use client";

import { useEffect, useMemo, useState } from "react";
import { explainFeatureEnabled, explainSessionId, getGhostVsReal } from "@/lib/api";
import { useRaceStore } from "@/store/raceStore";
import { GhostVsRealChart } from "@/components/aris/GhostVsRealChart";
import { RaceDebriefView } from "@/components/aris/RaceDebriefView";
import { raceFinishSummary } from "@/lib/debriefSummary";
import type { GhostVsRealResponse } from "@/lib/types";

/**
 * Post-race banner + optional modal. Triggered when the replay ends.
 * Dismissible; re-open from Explain → Race Debrief or the banner button.
 */
export function RaceFinishedDebrief() {
  const session = useRaceStore((s) => s.session);
  const raceFinished = useRaceStore((s) => s.raceFinished);
  const currentLap = useRaceStore((s) => s.currentLap);
  const totalLaps = useRaceStore((s) => s.totalLaps);
  const consolePlayState = useRaceStore((s) => s.consolePlayState);
  const debriefDismissed = useRaceStore((s) => s.debriefDismissed);
  const debriefOpen = useRaceStore((s) => s.debriefOpen);
  const setDebriefOpen = useRaceStore((s) => s.setDebriefOpen);
  const setDebriefDismissed = useRaceStore((s) => s.setDebriefDismissed);
  const setExplainTabRequest = useRaceStore((s) => s.setExplainTabRequest);
  const arisDriver = useRaceStore((s) => s.arisDriver ?? s.focusDriver ?? session?.driverCode);
  const ghostData = useRaceStore((s) => s.ghostData);
  const ghostCar = useRaceStore((s) => s.ghostCar);
  const ghostTicks = useRaceStore((s) => s.ghostTicksByLap);
  const cars = useRaceStore((s) => s.cars);
  const field = useRaceStore((s) => s.r2RaceField);
  const isARISOn = useRaceStore((s) => s.isARISOn);
  const [compare, setCompare] = useState<GhostVsRealResponse | null>(null);

  const ended =
    raceFinished ||
    (consolePlayState === "racing" && totalLaps > 0 && currentLap >= totalLaps);
  const showBanner = ended && !debriefDismissed && !debriefOpen;
  const sid = explainSessionId(session);

  useEffect(() => {
    if (!ended || !arisDriver) return;
    let cancelled = false;
    getGhostVsReal({ session_id: sid, driver: arisDriver }).then((payload) => {
      if (!cancelled) setCompare(payload);
    });
    return () => {
      cancelled = true;
    };
  }, [ended, sid, arisDriver]);

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
    const last = compare.real.laps.length - 1;
    return {
      realPos: compare.real.position[last],
      ghostPos: compare.ghost.position[last],
      realGap: compare.real.gap_to_leader[last],
      ghostGap: compare.ghost.gap_to_leader[last],
    };
  }, [finish, compare]);

  if (!ended && !debriefOpen) return null;

  return (
    <>
      {showBanner && (
        <div className="pointer-events-auto absolute bottom-4 left-1/2 z-[70] w-[min(36rem,calc(100%-2rem))] -translate-x-1/2 rounded-[10px] border border-border bg-surface-2/95 p-3 shadow-2xl backdrop-blur-sm">
          <div className="flex flex-wrap items-center gap-2">
            <div className="min-w-0 flex-1">
              <div className="font-mono-data text-[10px] uppercase tracking-[0.18em] text-muted">
                Race finished
              </div>
              <p className="font-sans text-sm text-white">View post-race debrief — ghost vs real.</p>
            </div>
            <button
              type="button"
              onClick={() => setDebriefOpen(true)}
              className="rounded bg-red px-3 py-1.5 font-mono-data text-[11px] uppercase text-white"
            >
              View debrief
            </button>
            <button
              type="button"
              onClick={() => setDebriefDismissed(true)}
              className="rounded border border-border px-3 py-1.5 font-mono-data text-[11px] uppercase text-muted hover:text-white"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      {debriefOpen && (
        <div className="absolute inset-0 z-[80] flex items-center justify-center bg-carbon/70 p-4 backdrop-blur-[2px]">
          <div className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-[12px] border border-border bg-surface-2 shadow-2xl">
            <div className="flex shrink-0 items-start justify-between gap-3 border-b border-border p-4">
              <div>
                <div className="font-mono-data text-[10px] uppercase tracking-[0.2em] text-muted">
                  Post-race debrief
                </div>
                <h2 className="mt-1 text-lg font-bold text-white">
                  {session?.circuitName ?? "Session"} · {session?.year}
                </h2>
                <p className="mt-1 font-mono-data text-[11px] text-muted">
                  {isARISOn && arisDriver
                    ? `Ghost (ARIS) vs real ${arisDriver}`
                    : "Replay finished."}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setDebriefOpen(false);
                  setDebriefDismissed(true);
                }}
                className="rounded border border-border px-2 py-1 font-mono-data text-[11px] uppercase text-muted hover:text-white"
              >
                Close
              </button>
            </div>

            {isARISOn && (
              <div className="grid shrink-0 grid-cols-2 gap-3 px-4 pt-3 font-mono-data text-[11px]">
                <div className="rounded border border-border bg-carbon p-3">
                  <div className="text-[9px] uppercase text-muted">ARIS (timing tower)</div>
                  <div className="mt-1 text-white">P{summary?.ghostPos ?? ghostData?.ghost_position ?? "—"}</div>
                  <div className="text-muted">
                    Gap {summary?.ghostGap != null ? `${summary.ghostGap.toFixed(1)}s` : "—"}
                  </div>
                </div>
                <div className="rounded border border-border bg-carbon p-3">
                  <div className="text-[9px] uppercase text-muted">Real finish</div>
                  <div className="mt-1 text-white">P{summary?.realPos ?? "—"}</div>
                  <div className="text-muted">
                    Gap {summary?.realGap != null ? `${summary.realGap.toFixed(1)}s` : "—"}
                  </div>
                </div>
              </div>
            )}

            {lastDelta != null && (
              <p className="px-4 pt-2 font-mono-data text-[12px] text-white">
                Estimated delta:{" "}
                <span className={lastDelta >= 0 ? "text-green-400" : "text-red-400"}>
                  {lastDelta >= 0 ? "+" : ""}
                  {lastDelta.toFixed(1)}s
                </span>{" "}
                {lastDelta >= 0 ? "(ARIS ahead)" : "(real ahead)"}
              </p>
            )}

            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <div className="mb-3 h-[220px] overflow-hidden rounded border border-border">
                <GhostVsRealChart sessionId={sid} driver={arisDriver ?? undefined} />
              </div>
              <div className="h-[320px] overflow-hidden rounded border border-border">
                <RaceDebriefView sessionId={sid} focusDriver={arisDriver ?? undefined} />
              </div>
            </div>

            {explainFeatureEnabled() && (
              <div className="shrink-0 border-t border-border p-3">
                <button
                  type="button"
                  onClick={() => {
                    setDebriefOpen(false);
                    setDebriefDismissed(true);
                    setExplainTabRequest("debrief");
                  }}
                  className="rounded border border-border px-3 py-1.5 font-mono-data text-[11px] uppercase text-muted hover:text-white"
                >
                  Open in Explain tab
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
